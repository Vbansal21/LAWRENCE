#!/usr/bin/env python3
"""Prove llama.cpp slot state survives a managed server restart."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from lk import server  # noqa: E402
from lk.profile import ModelProfile  # noqa: E402


def complete(messages: list[dict[str, str]]) -> dict:
    body = json.dumps({
        "messages": messages,
        "max_tokens": 16,
        "temperature": 0,
        "cache_prompt": True,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(
        f"{server.server_url()}/v1/chat/completions", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read())


def main() -> int:
    profile = ModelProfile.detect(
        model=ROOT / "models/local/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf",
        bin_path=ROOT / "third_party/llama.cpp/build/bin/llama-server",
    )
    if server.health_check():
        raise RuntimeError("port 8190 is already in use; stop the unmanaged server first")

    server.start(profile, wait_secs=180)
    first_messages = [{"role": "user", "content": "Reply with exactly KV OK."}]
    first = complete(first_messages)
    first_answer = first["choices"][0]["message"]["content"]
    server.stop()
    checkpoint = server.SLOT_DIR / server._slot_filename(profile)
    if not checkpoint.exists() or checkpoint.stat().st_size == 0:
        raise RuntimeError("KV checkpoint was not written")

    server.start(profile, wait_secs=180)
    second = complete(first_messages + [
        {"role": "assistant", "content": first_answer},
        {"role": "user", "content": "Reply with exactly NEXT OK."},
    ])
    server.stop()

    first_n = int(first.get("timings", {}).get("prompt_n", 0))
    second_n = int(second.get("timings", {}).get("prompt_n", 0))
    second_total = int(second.get("usage", {}).get("prompt_tokens", 0))
    cached = second_total - second_n
    if cached <= 0:
        raise RuntimeError(f"restored prompt was not reused: total={second_total}, evaluated={second_n}")
    report = {
        "ok": True,
        "checkpoint": checkpoint.name,
        "bytes": checkpoint.stat().st_size,
        "promptTokens": {
            "coldEvaluated": first_n,
            "continuedTotal": second_total,
            "continuedEvaluated": second_n,
            "restored": cached,
        },
    }
    path = ROOT / ".runtime" / "kv-smoke-report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
