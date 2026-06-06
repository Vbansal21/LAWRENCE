"""llama-server lifecycle manager.

Starts llama-server once and keeps it alive for the session.
All turns use HTTP POST /v1/chat/completions — no model reloads.

Configuration:
  - ctx_size   : 32768  (32K KV-cache ceiling; the kernel's working context
                         flexes dynamically below this — see ctx/store.py)
  - flash_attn : on     (required for long contexts at reasonable memory)
  - cache_type_k/v: q4_0 (KV quantization — reduces VRAM/RAM for long contexts)
  - defrag_thold: 0.1   (defragment KV cache across a long multi-turn session)
  - mlock      : on     (lock weights in RAM — no paging under memory pressure)
  - mmproj     : loaded so native image/audio tokens work
  - n_gpu_layers: 0 by default (CPU), set via LLAMACPP_GPU_LAYERS env var
  - threads    : 9      (leaves headroom for system + editor during inference)

The server exposes OpenAI-compatible endpoints:
  POST /v1/chat/completions  (with vision via base64 image_url content blocks)
  GET  /health

Gemma 4 native audio: the llama-server build must include mtmd support.
Audio files are passed as base64-encoded content in the chat message,
using the same multimodal content block format as images.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BIN    = REPO_ROOT / "third_party/llama.cpp/build/bin/llama-server"
DEFAULT_MODEL  = REPO_ROOT / "models/local/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf"
DEFAULT_MMPROJ = REPO_ROOT / "models/local/gemma-4-E4B-it-GGUF/mmproj-gemma-4-E4B-it-BF16.gguf"

HOST = "127.0.0.1"
PORT = 8190          # avoid clash with existing llama-server on 8080

_proc: subprocess.Popen[bytes] | None = None


def server_url() -> str:
    return f"http://{HOST}:{PORT}"


def health_check(timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(f"{server_url()}/health")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def start(
    *,
    model: Path = DEFAULT_MODEL,
    mmproj: Path = DEFAULT_MMPROJ,
    bin_path: Path = DEFAULT_BIN,
    ctx_size: int = 32_768,        # KV-cache ceiling; working context flexes below this
    gpu_layers: int | None = None,
    threads: int | None = 9,       # leaves headroom for system + VSCode during inference
    wait_secs: int = 120,
) -> None:
    """Start llama-server in background. Blocks until /health responds."""
    global _proc

    if health_check():
        print(f"  [server] already running at {server_url()}")
        return

    if gpu_layers is None:
        gpu_layers = int(os.environ.get("LLAMACPP_GPU_LAYERS", "0"))
    if threads is None:           # caller passed None explicitly → use our default
        threads = 9

    log_path = REPO_ROOT / ".runtime" / "lk-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(bin_path),
        "--model", str(model),
        "--mmproj", str(mmproj),
        "--host", HOST,
        "--port", str(PORT),
        "--ctx-size", str(ctx_size),
        "--threads", str(threads),
        "--n-gpu-layers", str(gpu_layers),
        "--flash-attn", "on",
        "--cache-type-k", "q4_0",
        "--cache-type-v", "q4_0",
        "--defrag-thold", "0.1",
        "--mlock",                    # lock weights in RAM — prevent OS paging under memory pressure
        "--no-webui",
        "--jinja",                    # enable Jinja chat template (Gemma 4 needs it)
        "--parallel", "1",            # single-slot: one conversation at a time
    ]

    log_file = open(log_path, "wb")
    _proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    print(f"  [server] starting (pid {_proc.pid}) — model loading, please wait…")
    deadline = time.monotonic() + wait_secs
    while time.monotonic() < deadline:
        if _proc.poll() is not None:
            log_file.close()
            print(f"  [server] process exited early — check {log_path}", file=sys.stderr)
            raise RuntimeError("llama-server exited during startup")
        if health_check(timeout=3.0):
            print(f"  [server] ready at {server_url()}")
            return
        time.sleep(2)

    log_file.close()
    stop()
    raise RuntimeError(f"llama-server did not become healthy within {wait_secs}s — check {log_path}")


def stop() -> None:
    global _proc
    if _proc is None:
        return
    if _proc.poll() is None:
        try:
            os.killpg(_proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            _proc.terminate()
        try:
            _proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(_proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                _proc.kill()
            _proc.wait(timeout=5)
    _proc = None
    print("  [server] stopped")


def ensure_running(**kwargs: object) -> None:
    """Start the server if not already healthy."""
    if not health_check():
        start(**kwargs)  # type: ignore[arg-type]
