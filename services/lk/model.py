"""Model client — talks to a chat-completions backend.

Three interchangeable backends behind one `call_model()`:

  local      — the resident llama-server on 127.0.0.1:PORT (default). Blocking
               or streaming calls, cache_prompt enabled, no auth.
  api        — any OpenAI-compatible endpoint (OpenAI, OpenRouter, POE,
               Together, vLLM, LM Studio, …): base_url + bearer api_key +
               model name, with a real request timeout.
  anthropic  — the native Claude Messages API via the official `anthropic` SDK
               (optional extra: pip install -e ".[api]"). Adds structured
               outputs and proper streaming; reads ANTHROPIC_API_KEY.

Pick the backend with configure_backend() (the CLI wires this from flags/env:
LK_API_BASE / LK_API_KEY / LK_API_MODEL, or LK_BACKEND=anthropic). Everything
downstream — turns, proactive, compaction, journal — is unchanged; only the
transport differs.

New in this revision (provider logic stays in THIS file — invariant I3):

  schema=     constrained decoding. local/api: response_format json_schema →
              fallback json_object+schema → plain (working mode cached).
              anthropic: output_config.format. Guarantees valid JSON envelopes.
  stream_fn=  real token streaming. Called with each text delta as it decodes.
  priority=   local inference is single-slot (--parallel 1); calls serialize
              through a priority gate (turn 0 < compact 1 < proactive 2).
              Proactive-priority calls are droppable: if the gate is busy they
              return {"text": "", "skipped": True} instead of queueing.

Multimodal content (images, audio) is passed as base64 content blocks:
  {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
  {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,..."}}
(The anthropic backend converts image blocks to its native shape and drops
audio blocks — Claude has no audio input; transcription stays local.)

call_model() always returns {"text": <content>} with thinking blocks stripped.
"""
from __future__ import annotations

import base64
import heapq
import itertools
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import server as _server


# ── backend selection ─────────────────────────────────────────────────────────

@dataclass
class Backend:
    kind:     str = "local"          # "local" | "api" | "anthropic"
    base_url: str = ""               # api only, e.g. "https://api.openai.com/v1"
    api_key:  str | None = None      # api/anthropic (anthropic falls back to ANTHROPIC_API_KEY)
    model:    str | None = None      # served model name (api/anthropic)


_backend = Backend()                     # default backend (query path)
_routing: dict[str, Backend] = {}        # role → Backend (background work routing)
_active = threading.local()              # per-thread currently-active backend


def _current_backend() -> Backend:
    """The backend this thread's in-flight call is using (set by call_model from
    the role), falling back to the default. Thread-local so background extraction
    on Gemini and a local query can run concurrently without racing a global."""
    return getattr(_active, "backend", None) or _backend


def configure_routing(role: str, *, kind: str = "local", base_url: str = "",
                      api_key: str | None = None, model: str | None = None) -> None:
    """Route a role (extract/proactive/compact/journal/study/…) to a specific
    backend. Roles with no route use the default backend."""
    _routing[role] = Backend(kind=kind, base_url=base_url or "", api_key=api_key, model=model)


def clear_routing() -> None:
    _routing.clear()


def routing_summary() -> dict[str, str]:
    return {role: (b.model or b.kind) for role, b in _routing.items()}


_ANTHROPIC_DEFAULT_MODEL = "claude-opus-4-8"
# These models reject ALL sampling params (temperature/top_p/top_k → HTTP 400).
_ANTHROPIC_NO_SAMPLING_PREFIXES = ("claude-opus-4-7", "claude-opus-4-8", "claude-fable")

# Local thinking control. Gemma-4 (and other reasoning GGUFs) spend hundreds of
# tokens in a thought block before answering — on CPU that's ~100x slower
# (≈128s vs ≈1s for a short reply) and, with a small max_tokens, eats the whole
# budget and returns nothing. Our JSON envelopes are schema-constrained, so deep
# thinking buys little. Default OFF for responsiveness; LK_THINKING=on restores
# it for harder reasoning. Sent as chat_template_kwargs (Jinja templates that
# don't define enable_thinking just ignore it).
_THINKING_ON = os.environ.get("LK_THINKING", "off").strip().lower() in ("1", "true", "yes", "on")
# Ceiling on local generation length (see call_model) — bounds CPU runaways.
_LOCAL_MAX_TOKENS = int(os.environ.get("LK_LOCAL_MAX_TOKENS", "1024"))


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
    """Configure a remote backend from the environment. Returns True if one
    was activated. LK_BACKEND=anthropic selects the native Claude backend;
    LK_API_BASE selects the OpenAI-compatible backend."""
    if os.environ.get("LK_BACKEND", "").strip().lower() == "anthropic":
        configure_backend(
            kind="anthropic",
            api_key=os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LK_API_KEY") or None,
            model=os.environ.get("LK_API_MODEL") or _ANTHROPIC_DEFAULT_MODEL,
        )
        return True
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
    if _backend.kind == "anthropic":
        return f"anthropic: {_backend.model or _ANTHROPIC_DEFAULT_MODEL} @ api.anthropic.com"
    return f"local: {_server.server_url()}"


# ── diagnostics ───────────────────────────────────────────────────────────────

_warned: set[str] = set()


def _warn_once(key: str, msg: str) -> None:
    if key not in _warned:
        _warned.add(key)
        print(msg, file=sys.stderr)


_counters = {"fallback_parses": 0}


def note_fallback_parse() -> None:
    """invoke.py calls this when a JSON envelope failed to parse (should be ~0
    once schema-constrained decoding is active — watch it in /health)."""
    _counters["fallback_parses"] += 1


def fallback_parses() -> int:
    return _counters["fallback_parses"]


# ── priority gate (local single-slot inference) ───────────────────────────────

# Lower number wins. PRI_REFINE (the slow loop, WS-R/R1) sits just below a live
# turn and above background work: non-droppable (it queues, never starved) but
# always yields a fresh turn ahead of it. PRI_PROACTIVE stays the droppable floor.
PRI_TURN, PRI_REFINE, PRI_COMPACT, PRI_PROACTIVE = 0, 1, 2, 3


class _PriorityGate:
    """Serialize local inference: lowest priority number wins; FIFO within a
    priority. Proactive callers use try_acquire() and skip instead of queueing."""

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._busy = False
        self._waiting: list[tuple[int, int]] = []
        self._seq = itertools.count()

    def acquire(self, priority: int) -> None:
        with self._cv:
            ticket = (priority, next(self._seq))
            heapq.heappush(self._waiting, ticket)
            while self._busy or self._waiting[0] != ticket:
                self._cv.wait()
            heapq.heappop(self._waiting)
            self._busy = True

    def try_acquire(self) -> bool:
        with self._cv:
            if self._busy or self._waiting:
                return False
            self._busy = True
            return True

    def release(self) -> None:
        with self._cv:
            self._busy = False
            self._cv.notify_all()


_gate = _PriorityGate()


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


# ── HTTP (local + OpenAI-compatible) ──────────────────────────────────────────

def _endpoint() -> str:
    b = _current_backend()
    if b.kind == "api" and b.base_url:
        return b.base_url.rstrip("/") + "/chat/completions"
    return f"{_server.server_url()}/v1/chat/completions"


def _headers() -> dict[str, str]:
    b = _current_backend()
    headers = {"Content-Type": "application/json"}
    if b.kind == "api" and b.api_key:
        headers["Authorization"] = f"Bearer {b.api_key}"
    return headers


def _post(payload: dict[str, Any], timeout: float | None) -> dict[str, Any]:
    req = urllib.request.Request(
        _endpoint(), data=json.dumps(payload).encode(), headers=_headers(), method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        raise RuntimeError(f"{_current_backend().kind} backend HTTP {e.code}: {body}") from None


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


def _post_stream(
    payload: dict[str, Any],
    req_timeout: float | None,
    wall_timeout: float | None,
    stream_fn: Callable[[str], None],
) -> str:
    """Streaming chat completion over SSE (`data:` lines). Returns the full
    accumulated text; stream_fn receives each delta. A wall-clock deadline
    bounds runaway generations even on the local backend (whose non-streaming
    calls deliberately have no read timeout)."""
    p = dict(payload)
    p["stream"] = True
    req = urllib.request.Request(
        _endpoint(), data=json.dumps(p).encode(), headers=_headers(), method="POST",
    )
    deadline = (time.monotonic() + wall_timeout) if wall_timeout else None
    sock_timeout = req_timeout if req_timeout is not None else wall_timeout
    parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=sock_timeout) as resp:
            for raw_line in resp:
                if deadline and time.monotonic() > deadline:
                    raise RuntimeError(
                        f"{_current_backend().kind} backend: generation exceeded {wall_timeout}s wall-clock timeout"
                    )
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or [{}]
                piece = (choices[0].get("delta") or {}).get("content") or ""
                if piece:
                    parts.append(piece)
                    try:
                        stream_fn(piece)
                    except Exception:
                        pass   # a broken UI consumer must not kill the turn
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        raise RuntimeError(f"{_current_backend().kind} backend HTTP {e.code}: {body}") from None
    except OSError as e:
        raise RuntimeError(f"{_current_backend().kind} backend stream error: {e}") from None
    return "".join(parts)


def health(timeout: float = 4.0) -> bool:
    """Backend-aware reachability check. Local → server /health. API/anthropic
    → GET the models endpoint (any non-5xx response, including 401, means the
    endpoint is reachable)."""
    if _backend.kind == "local":
        return _server.health_check(timeout=timeout)
    if _backend.kind == "anthropic":
        url = "https://api.anthropic.com/v1/models"
        headers = {"anthropic-version": "2023-06-01"}
        key = _backend.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            headers["x-api-key"] = key
    else:
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


# ── constrained decoding (local + OpenAI-compatible) ──────────────────────────

# Sampling knobs only llama-server understands — stripped before any remote
# OpenAI-compatible endpoint (OpenAI proper rejects unknown params with 400).
_LLAMA_ONLY_KEYS = (
    "min_p", "top_k", "typical_p", "tfs_z", "repeat_penalty", "repeat_last_n",
    "mirostat", "mirostat_tau", "mirostat_eta",
    "dry_multiplier", "dry_base", "dry_allowed_length",
)

_SCHEMA_MODES = ("json_schema", "json_object", "none")
_schema_mode: dict[str, str] = {}   # backend kind → first shape that worked


def _apply_schema(payload: dict[str, Any], schema: dict[str, Any], mode: str) -> dict[str, Any]:
    p = dict(payload)
    if mode == "json_schema":        # OpenAI-style; current llama-server + OpenRouter
        p["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "lk_envelope", "strict": True, "schema": schema},
        }
    elif mode == "json_object":      # older llama-server shape
        p["response_format"] = {"type": "json_object", "schema": schema}
    return p


def _generate(
    payload: dict[str, Any],
    schema: dict[str, Any] | None,
    stream_fn: Callable[[str], None] | None,
    req_timeout: float | None,
    wall_timeout: float | None,
) -> str:
    """One generation against local/api, attaching the schema in whichever
    response_format shape this backend accepts (probed once, then cached)."""
    kind = _backend.kind
    if schema is None:
        if stream_fn:
            return _post_stream(payload, req_timeout, wall_timeout, stream_fn)
        resp = _post_with_retry(payload, req_timeout)
        return resp["choices"][0]["message"]["content"] or ""

    start = _schema_mode.get(kind, "json_schema")
    last_err: Exception | None = None
    for mode in _SCHEMA_MODES[_SCHEMA_MODES.index(start):]:
        p = _apply_schema(payload, schema, mode)
        try:
            if stream_fn:
                text = _post_stream(p, req_timeout, wall_timeout, stream_fn)
            else:
                # Schema-shape probes use _post directly (no retry storm on a
                # rejected shape); the final plain mode gets normal retries.
                resp = _post(p, req_timeout) if mode != "none" else _post_with_retry(p, req_timeout)
                text = resp["choices"][0]["message"]["content"] or ""
            if _schema_mode.get(kind) != mode:
                _schema_mode[kind] = mode
                if mode == "none":
                    _warn_once(f"schema-none-{kind}",
                               f"[model] {kind} backend rejected response_format — "
                               "running without constrained decoding")
            return text
        except RuntimeError as exc:
            msg = str(exc)
            demotable = ("HTTP 400" in msg or "response_format" in msg
                         or "json_schema" in msg or "grammar" in msg)
            if mode != "none" and demotable:
                last_err = exc
                continue
            raise
    raise last_err  # type: ignore[misc]


# ── anthropic (native Claude Messages API) ────────────────────────────────────

_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.*)$", re.DOTALL)


def _anthropic_client(timeout: float | None):
    try:
        import anthropic  # type: ignore
    except ImportError:
        raise RuntimeError(
            "anthropic backend selected but the SDK is not installed — "
            "pip install -e '.[api]'  (or: pip install anthropic)"
        ) from None
    kwargs: dict[str, Any] = {"max_retries": 2}
    if timeout:
        kwargs["timeout"] = float(timeout)
    if _current_backend().api_key:
        kwargs["api_key"] = _current_backend().api_key   # else SDK reads ANTHROPIC_API_KEY
    return anthropic.Anthropic(**kwargs)


def _anthropic_convert(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    """Our OpenAI-shaped messages → (system, anthropic messages).
    image_url data-URLs become native base64 image blocks; audio is dropped
    (Claude has no audio input — transcription stays local)."""
    system: str | None = None
    out: list[dict[str, Any]] = []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if role == "system":
            system = content if isinstance(content, str) else None
            continue
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        blocks: list[dict[str, Any]] = []
        for b in content or []:
            t = b.get("type")
            if t == "text":
                blocks.append({"type": "text", "text": b.get("text", "")})
            elif t == "image_url":
                url = (b.get("image_url") or {}).get("url", "")
                dm = _DATA_URL_RE.match(url)
                if dm:
                    blocks.append({"type": "image", "source": {
                        "type": "base64", "media_type": dm.group(1), "data": dm.group(2)}})
                elif url:
                    blocks.append({"type": "image", "source": {"type": "url", "url": url}})
            elif t == "audio_url":
                _warn_once("anthropic-audio",
                           "[model] anthropic backend has no audio input — "
                           "audio attachment dropped (local whisper transcribes instead)")
        out.append({"role": role, "content": blocks})
    return system, out


def _call_anthropic(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
    temperature: float | None,
    timeout: float | None,
    schema: dict[str, Any] | None,
    stream_fn: Callable[[str], None] | None,
    stop: list[str] | None,
    top_p: float | None,
) -> dict[str, Any]:
    client = _anthropic_client(timeout)
    model = _current_backend().model or _ANTHROPIC_DEFAULT_MODEL
    system, msgs = _anthropic_convert(messages)

    params: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": msgs}
    if system:
        params["system"] = system
    if stop:
        params["stop_sequences"] = list(stop)
    if model.startswith(_ANTHROPIC_NO_SAMPLING_PREFIXES):
        _warn_once(f"anthropic-nosample-{model}",
                   f"[model] {model} accepts no sampling params — temperature/top_p ignored")
    elif temperature is not None:
        params["temperature"] = temperature      # at most ONE of temperature/top_p on Claude 4+
    elif top_p is not None:
        params["top_p"] = top_p
    if schema is not None:
        params["output_config"] = {"format": {"type": "json_schema", "schema": schema}}

    try:
        if stream_fn:
            with client.messages.stream(**params) as s:
                for piece in s.text_stream:
                    try:
                        stream_fn(piece)
                    except Exception:
                        pass
                final = s.get_final_message()
            text = "".join(b.text for b in final.content if getattr(b, "type", "") == "text")
        else:
            resp = client.messages.create(**params)
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    except RuntimeError:
        raise
    except Exception as exc:                      # typed SDK errors → uniform RuntimeError
        status = getattr(exc, "status_code", None)
        detail = getattr(exc, "message", None) or str(exc)
        if status is not None:
            raise RuntimeError(f"anthropic backend HTTP {status}: {detail}") from None
        raise RuntimeError(f"anthropic backend error: {detail}") from None
    # Thinking arrives as separate blocks on Claude — only text blocks joined,
    # so no regex stripping is needed here.
    return {"text": text.strip()}


# ── inference ─────────────────────────────────────────────────────────────────

def call_model(
    messages: list[dict[str, Any]],
    *,
    role:              str         = "query",
    max_tokens:        int         = 800,
    temperature:       float       = 0.2,
    timeout:           int         = 600,
    schema:            dict[str, Any] | None = None,
    stream_fn:         Callable[[str], None] | None = None,
    priority:          int         = PRI_TURN,
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
) -> dict[str, Any]:
    """Returns {"text": stripped_content}. JSON extraction is the caller's job
    (with schema= the text is guaranteed-valid JSON on supporting backends).

    role selects the backend via the routing table (background roles can run on
    a fast API while queries stay local). If a routed API backend fails and the
    local server is healthy, the call falls back to local (resilience).
    Proactive-priority local calls may return {"text": "", "skipped": True} when
    the inference slot is busy — callers treat empty text as a no-op.
    """
    def _attempt() -> dict[str, Any]:
        b = _current_backend()
        if b.kind == "anthropic":
            return _call_anthropic(
                messages, max_tokens=max_tokens, temperature=temperature,
                timeout=timeout, schema=schema, stream_fn=stream_fn,
                stop=stop, top_p=top_p,
            )

        payload: dict[str, Any] = {
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
            "stream":      False,
        }
        _opt: dict[str, Any] = {
            "top_p": top_p, "min_p": min_p, "top_k": top_k, "typical_p": typical_p,
            "tfs_z": tfs_z, "repeat_penalty": repeat_penalty, "repeat_last_n": repeat_last_n,
            "presence_penalty": presence_penalty, "frequency_penalty": frequency_penalty,
            "mirostat": mirostat, "mirostat_tau": mirostat_tau, "mirostat_eta": mirostat_eta,
            "dry_multiplier": dry_multiplier, "dry_base": dry_base,
            "dry_allowed_length": dry_allowed_length, "seed": seed, "stop": stop or None,
        }
        if b.kind == "api":
            for k in _LLAMA_ONLY_KEYS:
                if _opt.get(k) is not None:
                    _warn_once(f"api-drop-{k}",
                               f"[model] '{k}' is llama.cpp-only — dropped for the API backend")
                    _opt[k] = None
        payload.update({k: v for k, v in _opt.items() if v is not None})

        if b.kind == "api":
            if not b.model:
                raise RuntimeError("API backend selected but no model set (LK_API_MODEL / --api-model)")
            payload["model"] = b.model
            req_timeout: float | None = timeout          # APIs must not block forever
        else:
            payload["cache_prompt"] = True               # llama-server KV reuse
            if not _THINKING_ON:                          # huge CPU speedup (≈128s → ≈1s)
                payload["chat_template_kwargs"] = {"enable_thinking": False}
            if payload["max_tokens"] > _LOCAL_MAX_TOKENS:  # bound CPU runaways
                payload["max_tokens"] = _LOCAL_MAX_TOKENS
            req_timeout = None                           # local CPU gens can run long

        # Local inference is single-slot — serialize through the priority gate.
        gated = b.kind == "local"
        if gated:
            if priority >= PRI_PROACTIVE:
                if not _gate.try_acquire():
                    return {"text": "", "skipped": True}
            else:
                _gate.acquire(priority)
        try:
            raw = _generate(payload, schema, stream_fn, req_timeout,
                            wall_timeout=timeout if stream_fn else None)
        finally:
            if gated:
                _gate.release()
        return {"text": _strip_thinking(raw)}

    primary = _routing.get(role) or _backend
    try:
        _active.backend = primary
        return _attempt()
    except RuntimeError as exc:
        # Resilience: a routed API failed → fall back to local if the server is up.
        if primary.kind == "local" or not _server.health_check(timeout=1.5):
            raise
        _warn_once(f"route-fallback-{role}",
                   f"[model] role={role} {primary.kind} backend failed ({exc}); "
                   "falling back to local")
        _active.backend = Backend(kind="local")
        try:
            return _attempt()
        finally:
            _active.backend = None
    finally:
        _active.backend = None


def _strip_thinking(text: str) -> str:
    # Complete thought→answer block (normal Gemma 4 output)
    text = re.sub(r"<\|channel>thought.*?<\|channel>answer\s*", "", text, flags=re.DOTALL)
    # Unclosed thought block (thinking ran to end of output with no answer tag)
    text = re.sub(r"<\|channel>thought.*", "", text, flags=re.DOTALL)
    # Standard <think>…</think> (other model formats)
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    return text.strip()
