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

restart() stops the running instance (if any) and starts a new one — lets the CLI
swap models or change server flags without restarting the whole process.

The server exposes OpenAI-compatible endpoints:
  POST /v1/chat/completions  (vision/audio via base64 image_url/audio_url blocks)
  GET  /health
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import urllib.request
import urllib.error

from .profile import ModelProfile


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BIN    = REPO_ROOT / "third_party/llama.cpp/build/bin/llama-server"
DEFAULT_MODEL  = REPO_ROOT / "models/local/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf"
# The matching mmproj is auto-discovered next to the model — see profile._find_mmproj

# Local-first embeddings: a *dedicated* embedding GGUF dropped here is auto-found
# and served by a second llama-server (llama.cpp requires --embeddings to run on
# its own server, separate from the chat model). See ensure_embeddings().
DEFAULT_EMBED_DIR = REPO_ROOT / "models" / "local" / "embed"

HOST = "127.0.0.1"
PORT = 8190          # avoid clash with existing llama-server on 8080
EMB_PORT = 8191      # dedicated local embedding server (chat stays on PORT)

_proc: subprocess.Popen[bytes] | None = None
_current_profile: ModelProfile | None = None   # profile the running server was started with

_emb_proc: subprocess.Popen[bytes] | None = None
_emb_lock = threading.Lock()                   # serialise lazy start of the embed server


def server_url() -> str:
    return f"http://{HOST}:{PORT}"


def health_check(timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(f"{server_url()}/health")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def current_profile() -> ModelProfile | None:
    """Return the profile the currently running server was started with, or None."""
    return _current_profile


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
    global _proc, _current_profile

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
            _current_profile = profile
            print(f"  [server] ready at {server_url()}")
            return
        time.sleep(2)

    log_file.close()
    stop()
    raise RuntimeError(f"llama-server did not become healthy within {wait_secs}s — check {log_path}")


def restart(
    profile: ModelProfile,
    *,
    gpu_layers: int | None = None,
    threads: int | None = 9,
    wait_secs: int = 120,
) -> None:
    """Stop the running server (if any) then start with the new profile.

    Lets the CLI swap models or change flags without restarting the whole process.
    Raises RuntimeError if the new server fails to start.
    """
    stop()
    start(profile, gpu_layers=gpu_layers, threads=threads, wait_secs=wait_secs)


# ── local embedding server (local-first vector arm) ────────────────────────────

def embed_server_url() -> str:
    return f"http://{HOST}:{EMB_PORT}"


def embeddings_health(timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(f"{embed_server_url()}/health")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _discover_embed_model() -> Path | None:
    """The local embedding GGUF to serve: ``LK_EMBED_MODEL_PATH`` if set, else the
    first non-mmproj ``*.gguf`` under models/local/embed/. None ⇒ none installed."""
    explicit = os.environ.get("LK_EMBED_MODEL_PATH", "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.exists() else None
    try:
        for g in sorted(DEFAULT_EMBED_DIR.glob("*.gguf")):
            if "mmproj" not in g.name.lower():
                return g
    except OSError:
        pass
    return None


def ensure_embeddings(*, wait_secs: int = 120) -> str | None:
    """Return the local embedding server URL, starting it on first use.

    Local-first: serves a dedicated embedding GGUF (see _discover_embed_model) on
    its own port so chat inference is untouched. Returns None when no local
    embedding model is installed — the caller then degrades (or, in a testing
    config, an API route handles embeddings instead). Thread-safe + idempotent."""
    if embeddings_health():
        return embed_server_url()
    with _emb_lock:
        if embeddings_health():
            return embed_server_url()
        model = _discover_embed_model()
        if model is None:
            return None
        _start_embeddings(model, wait_secs=wait_secs)
        return embed_server_url() if embeddings_health() else None


def _start_embeddings(model: Path, *, wait_secs: int = 120) -> None:
    global _emb_proc
    gpu_layers = int(os.environ.get("LLAMACPP_GPU_LAYERS", "0"))
    threads    = int(os.environ.get("LK_EMBED_THREADS", "4"))   # small model; leave cores for chat
    bin_path   = Path(os.environ.get("LK_LLAMA_BIN", str(DEFAULT_BIN)))
    log_path   = REPO_ROOT / ".runtime" / "lk-embed-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(bin_path),
        "--model", str(model),
        "--host", HOST,
        "--port", str(EMB_PORT),
        "--embeddings",               # dedicated embedding server (llama.cpp requirement)
        "--threads", str(threads),
        "--n-gpu-layers", str(gpu_layers),
        "--mlock",
        "--no-webui",
        "--parallel", "1",
    ]
    pooling = os.environ.get("LK_EMBED_POOLING", "").strip().lower()
    if pooling in ("none", "mean", "cls", "last", "rank"):
        cmd += ["--pooling", pooling]     # else use the model's default pooling
    ctx = os.environ.get("LK_EMBED_CTX", "").strip()
    if ctx:
        cmd += ["--ctx-size", ctx]

    print(f"  [embed-server] starting {model.name} on :{EMB_PORT}")
    log_file = open(log_path, "wb")
    _emb_proc = subprocess.Popen(
        cmd, stdout=log_file, stderr=log_file, stdin=subprocess.DEVNULL, start_new_session=True,
    )
    deadline = time.monotonic() + wait_secs
    while time.monotonic() < deadline:
        if _emb_proc.poll() is not None:
            log_file.close()
            raise RuntimeError(f"embed-server exited during startup — check {log_path}")
        if embeddings_health(timeout=3.0):
            print(f"  [embed-server] ready at {embed_server_url()}")
            return
        time.sleep(1.5)
    log_file.close()
    stop_embeddings()
    raise RuntimeError(f"embed-server did not become healthy within {wait_secs}s — check {log_path}")


def stop_embeddings() -> None:
    global _emb_proc
    if _emb_proc is None:
        return
    if _emb_proc.poll() is None:
        try:
            os.killpg(_emb_proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            _emb_proc.terminate()
        try:
            _emb_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(_emb_proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                _emb_proc.kill()
            _emb_proc.wait(timeout=5)
    _emb_proc = None
    print("  [embed-server] stopped")


def stop() -> None:
    global _proc, _current_profile
    stop_embeddings()      # reap the embedding server alongside the chat server
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
    _current_profile = None
    print("  [server] stopped")
