"""llama-server HTTP client.

Sends chat completions to the resident llama-server (OpenAI-compatible API).
The server stays loaded — no per-turn model reload.

Multimodal content (images, audio) is passed as base64 content blocks:
  {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
  {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,..."}}

Gemma 4 native audio/vision work this way — no separate model needed.

call_model() always returns {"text": <content>}. JSON structure is enforced
via system prompt only (response_format modes produce empty output in this
llama.cpp build with Gemma 4). Callers do their own extraction.

Thinking blocks (<|channel>thought…, <think>…</think>) are stripped before
returning content.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from . import server as _server


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

def _post(payload: dict[str, Any]) -> dict[str, Any]:
    import http.client
    body = json.dumps(payload).encode()
    conn = http.client.HTTPConnection(_server.HOST, _server.PORT, timeout=None)
    try:
        conn.request("POST", "/v1/chat/completions", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = resp.read()
        if resp.status != 200:
            raise RuntimeError(
                f"llama-server HTTP {resp.status}: {data.decode(errors='replace')[:400]}"
            )
        return json.loads(data)
    finally:
        conn.close()


# ── inference ─────────────────────────────────────────────────────────────────

def call_model(
    messages: list[dict[str, Any]],
    *,
    max_tokens:  int   = 800,
    temperature: float = 0.2,
    timeout:     int   = 600,   # kept for API compat; timeout=None in _post
) -> dict[str, Any]:
    """Returns {"text": stripped_content}. JSON extraction is caller's job."""
    payload = {
        "messages":    messages,
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "stream":      False,
        "cache_prompt": True,   # reuse KV cache when prefix matches prior call
    }
    resp    = _post(payload)
    raw     = resp["choices"][0]["message"]["content"]
    return {"text": _strip_thinking(raw)}


def _strip_thinking(text: str) -> str:
    # Complete thought→answer block (normal Gemma 4 output)
    text = re.sub(r"<\|channel>thought.*?<\|channel>answer\s*", "", text, flags=re.DOTALL)
    # Unclosed thought block (thinking ran to end of output with no answer tag)
    text = re.sub(r"<\|channel>thought.*", "", text, flags=re.DOTALL)
    # Standard <think>…</think> (other model formats)
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    return text.strip()
