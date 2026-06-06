"""llama-server lifecycle manager.

Starts llama-server once and keeps it alive for the session.
All turns use HTTP POST /v1/chat/completions — no model reloads.

start() takes a ModelProfile (see profile.py) that carries every model-dependent
flag, so swapping models needs no edits here. Fixed, model-independent flags:
  - defrag_thold: 0.1   (defragment KV cache across a long multi-turn session)
  - mlock      : on     (lock weights in RAM — no paging under memory pressure)
  - parallel   : 1      (single conversation slot)
  - n_gpu_layers: 0 by default (CPU), set via LLAMACPP_GPU_LAYERS env var
  - threads    : 9      (leaves headroom for system + editor during inference)

Profile-driven flags: --mmproj (only if present), --flash-attn, --cache-type-k/v,
--jinja, --ctx-size.

The server exposes OpenAI-compatible endpoints:
  POST /v1/chat/completions  (vision/audio via base64 image_url/audio_url blocks)
  GET  /health
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

from .profile import ModelProfile


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BIN    = REPO_ROOT / "third_party/llama.cpp/build/bin/llama-server"
DEFAULT_MODEL  = REPO_ROOT / "models/local/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf"
# The matching mmproj is auto-discovered next to the model — see profile._find_mmproj

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
    profile: ModelProfile,
    *,
    gpu_layers: int | None = None,
    threads: int | None = 9,       # leaves headroom for system + VSCode during inference
    wait_secs: int = 120,
) -> None:
    """Start llama-server in background from a ModelProfile. Blocks until healthy.

    All model-dependent flags (mmproj, flash-attn, KV type, jinja, ctx) come from
    the profile, so swapping models needs no edits here — see profile.py.
    """
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
        str(profile.bin),
        "--model", str(profile.model),
        "--host", HOST,
        "--port", str(PORT),
        "--ctx-size", str(profile.ctx_size),
        "--threads", str(threads),
        "--n-gpu-layers", str(gpu_layers),
        "--defrag-thold", "0.1",
        "--mlock",                    # lock weights in RAM — no paging under memory pressure
        "--no-webui",
        "--parallel", "1",            # single-slot: one conversation at a time
    ]
    # ── model-dependent flags (only when the model/build supports them) ──────────
    if profile.mmproj is not None:
        cmd += ["--mmproj", str(profile.mmproj)]   # multimodal projector
    if profile.flash_attn in ("on", "off", "auto"):
        cmd += ["--flash-attn", profile.flash_attn]
    if profile.kv_type:               # quantized KV cache (requires flash attn)
        cmd += ["--cache-type-k", profile.kv_type, "--cache-type-v", profile.kv_type]
    if profile.jinja:                 # embedded Jinja chat template
        cmd += ["--jinja"]

    print(f"  [server] {profile.summary()}")
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
