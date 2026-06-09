"""Model client — talks to a chat-completions backend (OpenAI-compatible).

Two interchangeable backends behind one `call_model()`:

  local  — the resident llama-server on 127.0.0.1:PORT (default). Blocking calls,
           cache_prompt enabled, no auth, server's own loaded model.
  api    — any external OpenAI-compatible endpoint (OpenAI, OpenRouter, Together,
           vLLM, LM Studio, …): base_url + bearer api_key + a model name, with a
           real request timeout.

Pick the backend with configure_backend() (the CLI wires this from flags/env:
LK_API_BASE / LK_API_KEY / LK_API_MODEL). Everything downstream — turns, proactive,
compaction, journal — is unchanged; only the transport differs.

Multimodal content (images, audio) is passed as base64 content blocks:
  {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
  {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,..."}}

call_model() always returns {"text": <content>} with thinking blocks stripped.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import server as _server


# ── backend selection ─────────────────────────────────────────────────────────

@dataclass
class Backend:
    kind:     str = "local"          # "local" | "api"
    base_url: str = ""               # api only, e.g. "https://api.openai.com/v1"
    api_key:  str | None = None      # api only (bearer token)
    model:    str | None = None      # api only — the served model name


_backend = Backend()


def configure_backend(
    *,
    kind: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> None:
    """Update the active backend. Unspecified fields are left unchanged."""
    if kind is not None:
        _backend.kind = kind
    if base_url is not None:
        _backend.base_url = base_url
    if api_key is not None:
        _backend.api_key = api_key
    if model is not None:
        _backend.model = model


def backend() -> Backend:
    return _backend


def backend_from_env() -> bool:
    """Configure an API backend if LK_API_BASE is set in the environment.
    Returns True if an API backend was activated."""
    base = os.environ.get("LK_API_BASE", "").strip()
    if not base:
        return False
    configure_backend(
        kind="api",
        base_url=base,
        api_key=os.environ.get("LK_API_KEY") or None,
        model=os.environ.get("LK_API_MODEL") or None,
    )
    return True


def describe_backend() -> str:
    if _backend.kind == "api":
        return f"api: {_backend.model or '(no model set)'} @ {_backend.base_url}"
    return f"local: {_server.server_url()}"


# ── content block builders ────────────────────────────────────────────────────

def text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def image_block(path: Path) -> dict[str, Any]:
    data = base64.b64encode(path.read_bytes()).decode()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def audio_block(path: Path) -> dict[str, Any]:
    data   = base64.b64encode(path.read_bytes()).decode()
    suffix = path.suffix.lower().lstrip(".")
    mime   = f"audio/{suffix}" if suffix in ("wav", "mp3", "ogg", "flac") else "audio/wav"
    return {"type": "audio_url", "audio_url": {"url": f"data:{mime};base64,{data}"}}


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _endpoint() -> str:
    if _backend.kind == "api" and _backend.base_url:
        return _backend.base_url.rstrip("/") + "/chat/completions"
    return f"{_server.server_url()}/v1/chat/completions"


def _post(payload: dict[str, Any], timeout: float | None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if _backend.kind == "api" and _backend.api_key:
        headers["Authorization"] = f"Bearer {_backend.api_key}"
    req = urllib.request.Request(
        _endpoint(), data=json.dumps(payload).encode(), headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        raise RuntimeError(f"{_backend.kind} backend HTTP {e.code}: {body}") from None


_RETRY_DELAYS = (1.0, 2.0, 4.0)
_RETRYABLE_CODES = {429, 500, 502, 503, 504}


def _post_with_retry(
    payload: dict[str, Any],
    timeout: float | None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Call _post with exponential backoff on transient failures.

    Retries on HTTP 429/500/502/503/504. Non-retryable 4xx errors propagate
    immediately. Connection errors are also retried.
    """
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return _post(payload, timeout)
        except RuntimeError as exc:
            m = re.search(r"HTTP (\d+)", str(exc))
            code = int(m.group(1)) if m else 0
            if 400 <= code < 500 and code not in _RETRYABLE_CODES:
                raise  # non-retryable client error (400, 401, 403, 404, …)
            last_err = exc
        except OSError as exc:
            last_err = RuntimeError(str(exc))
        if attempt < max_retries:
            time.sleep(_RETRY_DELAYS[attempt])
    raise last_err  # type: ignore[misc]


def health(timeout: float = 4.0) -> bool:
    """Backend-aware reachability check. Local → server /health. API → GET /models
    (any non-5xx response, including 401, means the endpoint is reachable)."""
    if _backend.kind != "api":
        return _server.health_check(timeout=timeout)
    if not _backend.base_url:
        return False
    url = _backend.base_url.rstrip("/") + "/models"
    headers = {}
    if _backend.api_key:
        headers["Authorization"] = f"Bearer {_backend.api_key}"
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500          # 401/403/404 still means "reachable"
    except Exception:
        return False


# ── inference ─────────────────────────────────────────────────────────────────

def call_model(
    messages: list[dict[str, Any]],
    *,
    max_tokens:        int         = 800,
    temperature:       float       = 0.2,
    timeout:           int         = 600,
<<<<<<< HEAD
    top_p:             float | None = None,
    min_p:             float | None = None,
    top_k:             int   | None = None,
    repeat_penalty:    float | None = None,
    presence_penalty:  float | None = None,
    frequency_penalty: float | None = None,
    seed:              int   | None = None,
    stop:              list[str] | None = None,
=======
    top_p:              float | None = None,
    min_p:              float | None = None,
    top_k:              int   | None = None,
    typical_p:          float | None = None,
    tfs_z:              float | None = None,
    repeat_penalty:     float | None = None,
    repeat_last_n:      int   | None = None,
    presence_penalty:   float | None = None,
    frequency_penalty:  float | None = None,
    mirostat:           int   | None = None,
    mirostat_tau:       float | None = None,
    mirostat_eta:       float | None = None,
    dry_multiplier:     float | None = None,
    dry_base:           float | None = None,
    dry_allowed_length: int   | None = None,
    seed:               int   | None = None,
    stop:               list[str] | None = None,
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
) -> dict[str, Any]:
    """Returns {"text": stripped_content}. JSON extraction is the caller's job."""
    payload: dict[str, Any] = {
        "messages":    messages,
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "stream":      False,
    }
    # Optional sampling fields — only included when caller explicitly set them
    # (None = leave to backend default). Both llama-server and OpenAI-compatible
    # endpoints silently ignore fields they don't recognise, so this is safe.
    _opt: dict[str, Any] = {
<<<<<<< HEAD
        "top_p":             top_p,
        "min_p":             min_p,
        "top_k":             top_k,
        "repeat_penalty":    repeat_penalty,
        "presence_penalty":  presence_penalty,
        "frequency_penalty": frequency_penalty,
        "seed":              seed,
        "stop":              stop or None,
=======
        "top_p":              top_p,
        "min_p":              min_p,
        "top_k":              top_k,
        "typical_p":          typical_p,
        "tfs_z":              tfs_z,
        "repeat_penalty":     repeat_penalty,
        "repeat_last_n":      repeat_last_n,
        "presence_penalty":   presence_penalty,
        "frequency_penalty":  frequency_penalty,
        "mirostat":           mirostat,
        "mirostat_tau":       mirostat_tau,
        "mirostat_eta":       mirostat_eta,
        "dry_multiplier":     dry_multiplier,
        "dry_base":           dry_base,
        "dry_allowed_length": dry_allowed_length,
        "seed":               seed,
        "stop":               stop or None,
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
    }
    payload.update({k: v for k, v in _opt.items() if v is not None})

    if _backend.kind == "api":
        if not _backend.model:
            raise RuntimeError("API backend selected but no model set (LK_API_MODEL / --api-model)")
        payload["model"] = _backend.model
        req_timeout: float | None = timeout          # APIs must not block forever
    else:
        payload["cache_prompt"] = True               # llama-server KV reuse
        req_timeout = None                           # local CPU gens can run long

    resp = _post_with_retry(payload, req_timeout)
    raw  = resp["choices"][0]["message"]["content"]
    return {"text": _strip_thinking(raw)}


def _strip_thinking(text: str) -> str:
    # Complete thought→answer block (normal Gemma 4 output)
    text = re.sub(r"<\|channel>thought.*?<\|channel>answer\s*", "", text, flags=re.DOTALL)
    # Unclosed thought block (thinking ran to end of output with no answer tag)
    text = re.sub(r"<\|channel>thought.*", "", text, flags=re.DOTALL)
    # Standard <think>…</think> (other model formats)
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    return text.strip()
