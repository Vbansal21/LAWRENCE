"""LAWRENCE v0.1 — terminal entry point.

Wires together:
  - llama-server lifecycle (server.py)
  - Vision + audio observers (obs/) → write to ContextStore, trigger proactive
  - Retrieval pipeline (retrieval/) → semantic DB + web
  - LLM kernel (kernel/invoke.py) — called on user queries + audio triggers + proactive events
  - UI connector stub (ui/) — no-op in CLI mode

The CLI is independent of the server: if the server fails to start, LAWRENCE
runs in degraded mode and you can configure + restart the server via /server.
All runtime parameters are live-configurable without restarting the CLI.

Commands:
  text               send a query to the model
  /screenshot [q]    capture screen now and attach to next turn
  /image PATH [q]    attach image file
  /audio PATH [q]    attach audio file
  /record SECS [q]   record microphone for SECS seconds and attach

  /vision on|off     start/stop rolling vision observer
  /audio-on|off      start/stop rolling audio observer
  /context           print rolling context (L1/L2/L3)
  /log               print last 30 lines of context event log
  /obs               show live state of vision/audio preprocessors

  /status            server + observer + memory state
  /config            show all live-configurable settings
  /set KEY VAL       change a setting (see /help set for all keys)
  /server CMD        server lifecycle: start|stop|restart|status

  /db CMD            semantic DB: info|clear
  /mem CMD           memory: info|clear|archive
  /journal           write + print a journal entry for this session
  /clear             clear rolling context (L1+L2+L3)
  /skip-retrieval    toggle web retrieval for this session

  /help              this help
  /help set          list all /set keys
  /exit, /quit       quit (writes journal automatically)
"""
from __future__ import annotations

import argparse
import os
import queue
import signal
import sys
import tempfile
import textwrap
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import server as _server
from . import admin  as _admin
from . import model  as _model
from .ctx        import ContextStore
from .ctx.gate   import gate_config
from .kernel     import run_turn, run_proactive, run_compaction, write_journal_entry, TurnConfig
from .obs        import VisionObserver, AudioObserver, capture_now, record_now, SpoolReader
<<<<<<< HEAD
=======
from .tasks      import TaskStore
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
from .obs.vision import POLL_INTERVAL, MIN_WRITE_SECS, REGION_EMA, REGION_CHANGE_MIN
from .profile    import ModelProfile
from .retrieval  import SemanticDB, RetrievalPipeline
from .ui         import UIConnector


# ── helpers ─────────────────────────────────────────────────────────────────

def _env_flag(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# ── args ──────────────────────────────────────────────────────────────────────

def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="LAWRENCE v0.1 local assistant")
    p.add_argument("--no-vision",      action="store_true")
    p.add_argument("--no-audio",       action="store_true")
    p.add_argument("--no-retrieval",   action="store_true")
    p.add_argument("--stop-server",    action="store_true", help="Stop llama-server on exit")
    p.add_argument("--skip-analysis",  action="store_true", help="Single-pass mode (no retrieval)")
    p.add_argument("--audio-query",    action="store_true",
                   help="Treat all significant audio as a query (full turn, response printed)")
    p.add_argument("--ingest-spool",   nargs="?", const="memory/spool", default=None,
                   help="Ingest events from an external sensor's spool dir (default: memory/spool). "
                        "Pair with `python3 lk_sensor.py` running on a host with screen/mic.")
    p.add_argument("--model",   default=str(_server.DEFAULT_MODEL))
    p.add_argument("--mmproj",  default=None,
                   help="multimodal projector GGUF (auto-detected next to --model if omitted)")
    p.add_argument("--bin",     default=str(_server.DEFAULT_BIN))
    # external API backend (OpenAI-compatible). If --api-base / $LK_API_BASE is set,
    # the local llama-server is not started; calls go to the remote endpoint instead.
    p.add_argument("--api-base",  default=None,
                   help="OpenAI-compatible base URL (e.g. https://api.openai.com/v1). "
                        "Enables the external API backend. Also $LK_API_BASE.")
    p.add_argument("--api-key",   default=None, help="bearer token for --api-base ($LK_API_KEY)")
    p.add_argument("--api-model", default=None, help="model name for --api-base ($LK_API_MODEL)")
    p.add_argument("--ctx-size",    type=int,   default=65_536)
    p.add_argument("--gpu-layers",  type=int,   default=None)
    p.add_argument("--threads",     type=int,   default=None)
    p.add_argument("--max-tokens",  type=int,   default=2048)
    p.add_argument("--temp",        type=float, default=0.2)
    p.add_argument("--timeout",     type=int,   default=300)
    return p.parse_args()


# ── live state (all runtime-configurable settings) ────────────────────────────

@dataclass
class _LiveState:
    """Single source of truth for all configurable parameters.

    Staged fields (marked [S]) require /server restart to take effect —
    they control how llama-server is launched.  All other fields apply
    immediately when changed with /set.
    """
    # ── [S] server / model ─────────────────────────────────────────────────
    model_path:   Path
    bin_path:     Path
    mmproj_path:  Path | None   # None = auto-detect from model dir
    ctx_size:     int
    gpu_layers:   int | None    # None → 0 (CPU)
    threads:      int | None    # None → 9 (default)
    kv_type:      str           # q4_0 | q8_0 | f16 | none
    flash_attn:   str           # on | off | auto
    jinja:        bool
    server_dirty: bool = False  # True → staged settings changed, restart needed
    # backend: "local" (llama-server) or "api" (external OpenAI-compatible)
    backend:      str = "local"
    api_base:     str = ""
    api_model:    str = ""

    # ── turn ──────────────────────────────────────────────────────────────
    max_tokens:        int         = 2048
    temperature:       float       = 0.2
    timeout:           int         = 300
    no_retrieval:      bool        = False
    skip_analysis:     bool        = False
    # Advanced sampling (None = backend default)
    top_p:             float | None = None
    min_p:             float | None = None
    top_k:             int   | None = None
    repeat_penalty:    float | None = None
    presence_penalty:  float | None = None
    frequency_penalty: float | None = None
    seed:              int   | None = None
    stop_sequences:    list[str] = field(default_factory=list)

    # ── observer tunables ─────────────────────────────────────────────────
    vision_interval:   float = POLL_INTERVAL
    vision_write_min:  int   = MIN_WRITE_SECS
    vision_high:       float = field(default_factory=lambda: gate_config.vision_high)
    vision_pixel_min:  float = field(default_factory=lambda: gate_config.vision_pixel_min)
    vision_novelty_min: float = field(default_factory=lambda: gate_config.vision_novelty_min)
    vision_regions:    bool  = True    # per-window OCR vs whole-screen
    region_ema:        float = REGION_EMA
    region_change_min: float = REGION_CHANGE_MIN
    audio_min_words:   int   = field(default_factory=lambda: gate_config.audio_min_words)
    audio_dedup_max:   float = field(default_factory=lambda: gate_config.audio_dedup_max)

    # ── proactive ─────────────────────────────────────────────────────────
    proactive_interval: float = 600.0   # 10-minute minimum between proactive calls
    proactive_present:  bool  = True    # surface findings unprompted (vs. warm cache silently)

    # ── memory ────────────────────────────────────────────────────────────
    compact_min: int = 300   # seconds minimum between compaction runs
    l2_budget:   int = 10_000
    l3_budget:   int = 4_000


def _build_profile(state: _LiveState) -> ModelProfile:
    """Construct a ModelProfile from the current live state, honoring env overrides."""
    env_set = {
        "LK_KV_TYPE":    state.kv_type,
        "LK_FLASH_ATTN": state.flash_attn,
        "LK_JINJA":      "1" if state.jinja else "0",
        "LK_CTX_SIZE":   str(state.ctx_size),
    }
    old = {k: os.environ.get(k) for k in env_set}
    os.environ.update(env_set)
    try:
        return ModelProfile.detect(
            model=state.model_path,
            bin_path=state.bin_path,
            mmproj=state.mmproj_path,
            ctx_size=state.ctx_size,
        )
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── /set handler ──────────────────────────────────────────────────────────────

def _apply_set(
    key: str,
    val: str,
    state: _LiveState,
    cfg: TurnConfig,
    ctx: ContextStore,
    pipeline: RetrievalPipeline,
    vision_ref: "list[VisionObserver | None]",
) -> str:
    """Apply /set key val. Returns a status line for the terminal."""
    k = key.lower().strip()

    # ── staged: server / model ────────────────────────────────────────────
    if k == "model":
        p = Path(val).expanduser().resolve()
        if not p.exists():
            return f"[set] not found: {p}"
        state.model_path = p
        state.mmproj_path = None   # re-auto-detect from new dir
        state.server_dirty = True
        return f"[set] model → {p.name}  [restart server to apply]"

    if k == "bin":
        p = Path(val).expanduser().resolve()
        if not p.exists():
            return f"[set] not found: {p}"
        state.bin_path = p
        state.server_dirty = True
        return f"[set] bin → {p.name}  [restart server to apply]"

    if k == "mmproj":
        if val.lower() in ("auto", "none", ""):
            state.mmproj_path = None
        else:
            p = Path(val).expanduser().resolve()
            if not p.exists():
                return f"[set] not found: {p}"
            state.mmproj_path = p
        state.server_dirty = True
        label = "auto" if state.mmproj_path is None else state.mmproj_path.name
        return f"[set] mmproj → {label}  [restart server to apply]"

    if k == "ctx":
        try:
            n = int(val)
            if n < 2048:
                return "[set] ctx must be >= 2048"
        except ValueError:
            return "[set] ctx must be an integer"
        state.ctx_size = n
        state.server_dirty = True
        return f"[set] ctx → {n}  [restart server to apply]"

    if k == "threads":
        try:
            n = int(val)
            if n < 1:
                return "[set] threads must be >= 1"
        except ValueError:
            return "[set] threads must be an integer"
        state.threads = n
        state.server_dirty = True
        return f"[set] threads → {n}  [restart server to apply]"

    if k == "gpu-layers":
        try:
            n = int(val)
        except ValueError:
            return "[set] gpu-layers must be an integer"
        state.gpu_layers = n
        state.server_dirty = True
        return f"[set] gpu-layers → {n}  [restart server to apply]"

    if k == "kv-type":
        v = val.lower()
        if v not in ("q4_0", "q8_0", "f16", "none"):
            return "[set] kv-type must be q4_0 | q8_0 | f16 | none"
        state.kv_type = v
        state.server_dirty = True
        return f"[set] kv-type → {v}  [restart server to apply]"

    if k == "flash-attn":
        v = val.lower()
        if v not in ("on", "off", "auto"):
            return "[set] flash-attn must be on | off | auto"
        state.flash_attn = v
        state.server_dirty = True
        return f"[set] flash-attn → {v}  [restart server to apply]"

    if k == "jinja":
        v = val.lower() in ("on", "1", "true", "yes")
        state.jinja = v
        state.server_dirty = True
        return f"[set] jinja → {'on' if v else 'off'}  [restart server to apply]"

    # ── live: turn params ─────────────────────────────────────────────────
    if k == "max-tokens":
        try:
            n = int(val)
        except ValueError:
            return "[set] max-tokens must be an integer"
        state.max_tokens = cfg.max_tokens = n
        return f"[set] max-tokens → {n}"

    if k == "temp":
        try:
            f = float(val)
        except ValueError:
            return "[set] temp must be a float (e.g. 0.2)"
        state.temperature = cfg.temperature = f
        return f"[set] temperature → {f}"

    if k == "timeout":
        try:
            n = int(val)
        except ValueError:
            return "[set] timeout must be an integer (seconds)"
        state.timeout = cfg.timeout = n
        return f"[set] timeout → {n}s"

    if k == "retrieval":
        v = val.lower() not in ("off", "0", "false", "no")
        state.no_retrieval = cfg.no_retrieval = not v
        return f"[set] retrieval → {'on' if v else 'off'}"

    if k == "analysis":
        v = val.lower() not in ("off", "0", "false", "no")
        state.skip_analysis = cfg.skip_analysis = not v
        return f"[set] analysis → {'on' if v else 'off'}"

    # ── live: vision gate + observer ──────────────────────────────────────
    if k == "vision-high":
        try:
            f = float(val)
        except ValueError:
            return "[set] vision-high must be a float (0-1)"
        gate_config.vision_high = f
        state.vision_high = f
        return f"[set] vision-high → {f}"

    if k == "vision-pixel-min":
        try:
            f = float(val)
        except ValueError:
            return "[set] vision-pixel-min must be a float (0-1)"
        gate_config.vision_pixel_min = f
        state.vision_pixel_min = f
        return f"[set] vision-pixel-min → {f}"

    if k == "vision-novelty-min":
        try:
            f = float(val)
        except ValueError:
            return "[set] vision-novelty-min must be a float (0-1)"
        gate_config.vision_novelty_min = f
        state.vision_novelty_min = f
        return f"[set] vision-novelty-min → {f}"

    if k == "vision-interval":
        try:
            f = float(val)
            if f < 1:
                return "[set] vision-interval must be >= 1 second"
        except ValueError:
            return "[set] vision-interval must be a number (seconds)"
        state.vision_interval = f
        vi = vision_ref[0]
        if vi is not None:
            vi.poll_interval = f
        suffix = " (applied to running observer)" if vi else " (will apply on next start)"
        return f"[set] vision-interval → {f}s{suffix}"

    if k == "vision-write-min":
        try:
            n = int(val)
            if n < 0:
                return "[set] vision-write-min must be >= 0"
        except ValueError:
            return "[set] vision-write-min must be an integer (seconds)"
        state.vision_write_min = n
        vi = vision_ref[0]
        if vi is not None:
            vi.min_write_secs = n
        suffix = " (applied to running observer)" if vi else " (will apply on next start)"
        return f"[set] vision-write-min → {n}s{suffix}"

    if k == "vision-regions":
        v = val.lower() not in ("off", "0", "false", "no")
        state.vision_regions = v
        vi = vision_ref[0]
        if vi is not None:
            vi.regions = v
        return f"[set] vision-regions → {'on (per-window OCR)' if v else 'off (whole-screen)'}"

    if k == "region-ema":
        try:
            f = float(val)
            if not 0 < f <= 1:
                return "[set] region-ema must be in (0, 1]"
        except ValueError:
            return "[set] region-ema must be a float in (0, 1]"
        state.region_ema = f
        vi = vision_ref[0]
        if vi is not None:
            vi._tracker.ema = f
        return f"[set] region-ema → {f}"

    if k == "region-change-min":
        try:
            f = float(val)
        except ValueError:
            return "[set] region-change-min must be a float (0-1)"
        state.region_change_min = f
        vi = vision_ref[0]
        if vi is not None:
            vi.region_change_min = f
        return f"[set] region-change-min → {f}"

    # ── live: audio gate ──────────────────────────────────────────────────
    if k == "audio-min-words":
        try:
            n = int(val)
        except ValueError:
            return "[set] audio-min-words must be an integer"
        gate_config.audio_min_words = n
        state.audio_min_words = n
        return f"[set] audio-min-words → {n}"

    if k == "audio-dedup-max":
        try:
            f = float(val)
        except ValueError:
            return "[set] audio-dedup-max must be a float (0-1)"
        gate_config.audio_dedup_max = f
        state.audio_dedup_max = f
        return f"[set] audio-dedup-max → {f}"

    # ── live: proactive ───────────────────────────────────────────────────
    if k == "proactive-interval":
        try:
            f = float(val)
            if f < 60:
                return "[set] proactive-interval must be >= 60 seconds"
        except ValueError:
            return "[set] proactive-interval must be a number (seconds)"
        state.proactive_interval = f
        return f"[set] proactive-interval → {f}s"

    if k == "proactive-present":
        v = val.lower() not in ("off", "0", "false", "no")
        state.proactive_present = v
        return f"[set] proactive-present → {'on' if v else 'off'} (surface findings unprompted)"

    # ── live: memory compaction ───────────────────────────────────────────
    if k == "compact-min":
        try:
            n = int(val)
            if n < 0:
                return "[set] compact-min must be >= 0"
        except ValueError:
            return "[set] compact-min must be an integer (seconds)"
        state.compact_min = n
        ctx._min_compact_secs = n
        return f"[set] compact-min → {n}s"

    if k == "l2-budget":
        try:
            n = int(val)
        except ValueError:
            return "[set] l2-budget must be an integer (chars)"
        state.l2_budget = n
        ctx.l2_budget = n
        return f"[set] l2-budget → {n} chars"

    if k == "l3-budget":
        try:
            n = int(val)
        except ValueError:
            return "[set] l3-budget must be an integer (chars)"
        state.l3_budget = n
        ctx.l3_budget = n
        return f"[set] l3-budget → {n} chars"

    # ── live: retrieval ───────────────────────────────────────────────────
    if k == "retrieval-top-k":
        try:
            n = int(val)
        except ValueError:
            return "[set] retrieval-top-k must be an integer"
        pipeline.top_k = n
        return f"[set] retrieval-top-k → {n}"

    if k == "retrieval-fresh":
        try:
            n = int(val)
        except ValueError:
            return "[set] retrieval-fresh must be an integer"
        pipeline.fresh_per_q = n
        return f"[set] retrieval-fresh → {n}"

    if k == "retrieval-db-min":
        try:
            n = int(val)
        except ValueError:
            return "[set] retrieval-db-min must be an integer"
        pipeline.db_min_hits = n
        return f"[set] retrieval-db-min → {n}"

    if k == "api-model":
        if state.backend != "api":
            return "[set] api-model only applies to the API backend (start with --api-base)"
        _model.configure_backend(model=val)
        state.api_model = val
        return f"[set] api-model → {val}"

    # ── live: advanced sampling ───────────────────────────────────────────
    if k == "top-p":
        if val.lower() in ("off", "none", ""):
            state.top_p = cfg.top_p = None
            return "[set] top-p → off (backend default)"
        try:
            f = float(val)
        except ValueError:
            return "[set] top-p must be a float (0-1) or 'off'"
        state.top_p = cfg.top_p = f
        return f"[set] top-p → {f}"

    if k == "min-p":
        if val.lower() in ("off", "none", ""):
            state.min_p = cfg.min_p = None
            return "[set] min-p → off (backend default)"
        try:
            f = float(val)
        except ValueError:
            return "[set] min-p must be a float (0-1) or 'off'"
        state.min_p = cfg.min_p = f
        return f"[set] min-p → {f}"

    if k == "top-k":
        if val.lower() in ("off", "none", "0", ""):
            state.top_k = cfg.top_k = None
            return "[set] top-k → off (backend default)"
        try:
            n = int(val)
        except ValueError:
            return "[set] top-k must be an integer or 'off'"
        state.top_k = cfg.top_k = n
        return f"[set] top-k → {n}"

    if k == "repeat-penalty":
        if val.lower() in ("off", "none", ""):
            state.repeat_penalty = cfg.repeat_penalty = None
            return "[set] repeat-penalty → off (backend default)"
        try:
            f = float(val)
        except ValueError:
            return "[set] repeat-penalty must be a float (e.g. 1.1) or 'off'"
        state.repeat_penalty = cfg.repeat_penalty = f
        return f"[set] repeat-penalty → {f}"

    if k == "presence-penalty":
        if val.lower() in ("off", "none", ""):
            state.presence_penalty = cfg.presence_penalty = None
            return "[set] presence-penalty → off (backend default)"
        try:
            f = float(val)
        except ValueError:
            return "[set] presence-penalty must be a float (-2 to 2) or 'off'"
        state.presence_penalty = cfg.presence_penalty = f
        return f"[set] presence-penalty → {f}"

    if k == "frequency-penalty":
        if val.lower() in ("off", "none", ""):
            state.frequency_penalty = cfg.frequency_penalty = None
            return "[set] frequency-penalty → off (backend default)"
        try:
            f = float(val)
        except ValueError:
            return "[set] frequency-penalty must be a float (-2 to 2) or 'off'"
        state.frequency_penalty = cfg.frequency_penalty = f
        return f"[set] frequency-penalty → {f}"

    if k == "seed":
        if val.lower() in ("off", "none", "random", ""):
            state.seed = cfg.seed = None
            return "[set] seed → random (no fixed seed)"
        try:
            n = int(val)
        except ValueError:
            return "[set] seed must be an integer or 'off'"
        state.seed = cfg.seed = n
        return f"[set] seed → {n}"

    if k == "stop":
        if val.lower() in ("off", "none", "clear", ""):
            state.stop_sequences = cfg.stop_sequences = []
            return "[set] stop → cleared"
        seqs = [s.strip() for s in val.split(",") if s.strip()]
        state.stop_sequences = cfg.stop_sequences = seqs
        return f"[set] stop → {seqs}"

    return f"[set] unknown key '{key}' — use /help set for all keys"


# ── /server handler ───────────────────────────────────────────────────────────

def _do_server(
    verb: str,
    state: _LiveState,
    profile_ref: "list[ModelProfile]",
    cfg: TurnConfig,
) -> None:
    v = verb.strip().lower() if verb else "status"

    # External API backend: there is no local server to manage.
    if state.backend == "api":
        if v == "status":
            print(f"  backend: {'reachable' if _model.health() else 'UNREACHABLE'} "
                  f"({_model.describe_backend()})")
        else:
            print(f"  [server] external API backend — nothing to {v}. "
                  f"({_model.describe_backend()})")
        return

    if v == "status":
        ok = _server.health_check()
        print(f"  server: {'healthy' if ok else 'DOWN'} @ {_server.server_url()}")
        if state.server_dirty:
            print("  [!] staged settings changed — /server restart to apply")
        return

    if v in ("stop", "kill"):
        _server.stop()
        print("  [server] stopped — CLI continues (degraded: no LLM turns)")
        return

    if v in ("start", "restart"):
        if v == "restart":
            _server.stop()
        try:
            profile = _build_profile(state)
            _server.start(profile, gpu_layers=state.gpu_layers, threads=state.threads)
            profile_ref[0] = profile
            cfg.allow_images = profile.vision
            cfg.allow_audio  = profile.audio
            state.server_dirty = False
            print(f"  model: {profile.modalities}")
        except RuntimeError as e:
            print(f"  [server] failed: {e}")
        return

    print("  /server start|stop|restart|status")


# ── /config display ───────────────────────────────────────────────────────────

def _print_config(state: _LiveState, profile: ModelProfile, pipeline: RetrievalPipeline) -> None:
    dirty = "  [! staged settings changed — /server restart to apply]" if state.server_dirty else ""
    backend_line = (
        f"\n  ── backend ────────────────────────────────────────────────────────────"
        f"\n  backend     : {state.backend}"
        + (f"\n  api-base    : {state.api_base}\n  api-model   : {state.api_model or '(unset)'}"
           if state.backend == "api" else "")
    )
    print(
        f"\n[CONFIG]{dirty}"
        + backend_line +
        f"\n  ── server (staged: need /server restart; local backend only) ──────────"
        f"\n  model       : {state.model_path.name}"
        f"\n  mmproj      : {state.mmproj_path.name if state.mmproj_path else 'auto'}"
        f"\n  bin         : {state.bin_path.name}"
        f"\n  ctx-size    : {state.ctx_size}"
        f"\n  threads     : {state.threads or 9}"
        f"\n  gpu-layers  : {state.gpu_layers or 0}"
        f"\n  kv-type     : {state.kv_type}"
        f"\n  flash-attn  : {state.flash_attn}"
        f"\n  jinja       : {'on' if state.jinja else 'off'}"
        f"\n  ── active profile ─────────────────────────────────────────────────────"
        f"\n  {profile.summary()}"
        f"\n  ── turn (live) ────────────────────────────────────────────────────────"
        f"\n  max-tokens  : {state.max_tokens}"
        f"\n  temp        : {state.temperature}"
        f"\n  timeout     : {state.timeout}s"
        f"\n  retrieval   : {'off' if state.no_retrieval else 'on'}"
        f"\n  analysis    : {'off' if state.skip_analysis else 'on'}"
        f"\n  ── retrieval (live) ────────────────────────────────────────────────────"
        f"\n  top-k           : {pipeline.top_k}"
        f"\n  fresh-per-query : {pipeline.fresh_per_q}"
        f"\n  db-min-hits     : {pipeline.db_min_hits}"
        f"\n  ── vision gate (live) ─────────────────────────────────────────────────"
        f"\n  vision-high        : {state.vision_high}"
        f"\n  vision-pixel-min   : {state.vision_pixel_min}"
        f"\n  vision-novelty-min : {state.vision_novelty_min}"
        f"\n  vision-interval    : {state.vision_interval}s"
        f"\n  vision-write-min   : {state.vision_write_min}s"
        f"\n  vision-regions     : {'on (per-window OCR)' if state.vision_regions else 'off (whole-screen)'}"
        f"\n  region-ema         : {state.region_ema}"
        f"\n  region-change-min  : {state.region_change_min}"
        f"\n  ── audio gate (live) ──────────────────────────────────────────────────"
        f"\n  audio-min-words : {state.audio_min_words}"
        f"\n  audio-dedup-max : {state.audio_dedup_max}"
        f"\n  ── proactive (live) ───────────────────────────────────────────────────"
        f"\n  proactive-interval : {state.proactive_interval}s"
        f"\n  proactive-present  : {'on' if state.proactive_present else 'off'}"
        f"\n  ── memory compaction (live) ────────────────────────────────────────────"
        f"\n  compact-min : {state.compact_min}s"
        f"\n  l2-budget   : {state.l2_budget} chars"
        f"\n  l3-budget   : {state.l3_budget} chars"
    )


# ── /obs display ──────────────────────────────────────────────────────────────

def _print_obs(vision: "VisionObserver | None", audio: "AudioObserver | None") -> None:
    print("\n[OBSERVER STATE]")
    if vision and vision.active:
        f = vision.latest
        if f:
            ocr_preview = f.ocr_text[:120].replace("\n", " ")
            diff_preview = f.heuristic_diff[:80]
            print(f"  vision : ON | score={f.change_score:.2f} | {f.ts[:19]}")
            if vision.regions:
                tr = vision._tracker.active()
                print(f"           regions: {len(tr)} tracked"
                      + (" — " + ", ".join(f'{r.title[:24]}' for r in tr[:4]) if tr else ""))
            else:
                print("           regions: off (whole-screen OCR)")
            print(f"           ocr: {ocr_preview}")
            if diff_preview:
                print(f"           diff: {diff_preview}")
            print(f"           hi-res pending: {'yes' if vision.pending_hi else 'no'}")
            print(f"           poll={vision.poll_interval}s  write-min={vision.min_write_secs}s")
        else:
            print("  vision : ON | no frame captured yet")
    else:
        print("  vision : OFF")

    if audio and audio.active:
        print("  audio  : ON")
    else:
        print("  audio  : OFF")


# ── /db and /mem handlers ─────────────────────────────────────────────────────

def _do_db(verb: str, db: SemanticDB) -> None:
    v = verb.strip().lower() if verb else "info"
    if v == "info":
        try:
            count = db._con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            raw   = db._con.execute(
                "SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()"
            ).fetchone()
            size_k = raw[0] // 1024 if raw else 0
            print(f"  semantic DB : {count} chunks | {size_k}K on disk")
        except Exception as e:
            print(f"  semantic DB : error — {e}")
    elif v == "clear":
        try:
            db._con.execute("DELETE FROM chunks")
            db._con.commit()
            print("  [db] semantic DB cleared (all cached retrieval results removed)")
        except Exception as e:
            print(f"  [db] clear failed — {e}")
    else:
        print("  /db info|clear")


def _do_mem(arg: str, ctx: ContextStore) -> None:
    """Rolling memory (L1/L2/L3): info | show | clear | archive | export."""
    parts = arg.split()
    v     = parts[0].lower() if parts else "info"
    rest  = parts[1:]

    if v == "info":
        cooldown = ctx._min_compact_secs - (time.monotonic() - ctx._last_compact)
        print(
            f"\n[MEMORY INFO]"
            f"\n  L1 : {ctx._l1_size // 1024}K chars (raw events, current session)"
            f"\n  L2 : {ctx._l2_size // 1024}K chars (session summaries)"
            f"\n  L3 : {ctx._l3_size // 1024}K chars (long-range summaries)"
            f"\n  working budget : {ctx.working_budget() // 1024}K chars (dynamic)"
            f"\n  compact-min    : {ctx._min_compact_secs}s"
            f"\n  compact cooldown : {'ready' if cooldown <= 0 else f'{int(cooldown)}s remaining'}"
            f"\n  l2-budget : {ctx.l2_budget} chars"
            f"\n  l3-budget : {ctx.l3_budget} chars"
        )
    elif v == "show":
        if not rest:
            print("\n[MEMORY — L1/L2/L3]\n" + ctx.tail_for_model())
        else:
            print(f"\n[{rest[0].upper()}]\n" + ctx.show_layer(rest[0]))
    elif v == "clear":
        if not rest or rest[0].lower() == "all":
            ctx.clear_rolling()
            print("[memory cleared — L1, L2, L3 wiped]")
        elif ctx.clear_layer(rest[0]):
            print(f"[memory] {rest[0].upper()} cleared")
        else:
            print("  /mem clear [l1|l2|l3|all]")
    elif v == "archive":
        ctx._archive_l1()
        print("[memory] L1 archived — new session started")
    elif v == "export":
        if not rest:
            print("  /mem export PATH")
        else:
            written = ctx.export(Path(rest[0]).expanduser().resolve())
            print(f"[memory] exported {len(written)} layer(s) → {rest[0]}"
                  if written else "[memory] nothing to export")
    else:
        print("  /mem info | show [l1|l2|l3] | clear [l1|l2|l3|all] | archive | export PATH")


def _do_journal(arg: str, ctx: ContextStore) -> None:
    """Daily MDX journals: (write) | list | show | export | edit | delete."""
    parts = arg.split()
    v     = parts[0].lower() if parts else ""
    rest  = parts[1:]

    if v == "":                                   # /journal → write a new entry now
        print("  [writing journal…]")
        entry = write_journal_entry(ctx)
        print(f"\n[JOURNAL]\n{entry}" if entry else "[journal] nothing to journal yet")
    elif v == "list":
        rows = _admin.list_journals()
        if not rows:
            print("[journal] none yet")
        else:
            print("\n[JOURNALS]")
            for date, size, entries in rows:
                print(f"  {date}.mdx   {size // 1024 or 1}K   {entries} entr{'y' if entries == 1 else 'ies'}")
    elif v == "show":
        print("\n" + _admin.show_journal(rest[0] if rest else None))
    elif v == "edit":
        print(_admin.edit_journal(rest[0] if rest else None))
    elif v == "export":
        if not rest:
            print("  /journal export PATH [DATE]")
        else:
            date    = rest[1] if len(rest) > 1 else None
            written = _admin.export_journal(rest[0], date)
            print(f"[journal] exported {len(written)} file(s) → {rest[0]}"
                  if written else "[journal] nothing matched")
    elif v == "delete":
        if not rest:
            print("  /journal delete DATE  (DATE = today|yesterday|YYYY-MM-DD)")
        else:
            print(f"[journal] deleted {rest[0]}" if _admin.delete_journal(rest[0])
                  else f"[journal] no journal for {rest[0]}")
    else:
        print("  /journal | list | show [DATE] | export PATH [DATE] | edit [DATE] | delete DATE")


def _do_log(arg: str, ctx: ContextStore) -> None:
    """Event + turn logs: (tail) | list | show | export | trim | delete."""
    parts = arg.split()
    v     = parts[0].lower() if parts else ""
    rest  = parts[1:]

    if v == "" or v.isdigit():                    # /log [N] → tail today's event log
        n = int(v) if v.isdigit() else 30
        print(f"\n[EVENT LOG — last {n}]\n" + ctx.tail_compact(n))
    elif v == "list":
        rows = _admin.list_logs()
        if not rows:
            print("[log] none yet")
        else:
            print("\n[LOGS]  date         event-log  turn-log")
            for date, ev, tn in rows:
                print(f"  {date}   {ev // 1024 or (1 if ev else 0)}K        {tn // 1024 or (1 if tn else 0)}K")
    elif v == "show":
        date = rest[0] if rest else None
        n    = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else None
        print("\n[EVENT LOG]\n" + _admin.show_log(date, n))
    elif v == "trim":
        if len(rest) < 2 or not rest[1].isdigit():
            print("  /log trim DATE N   (keep last N lines)")
        else:
            kept = _admin.trim_log(rest[0], int(rest[1]))
            print(f"[log] {rest[0]} trimmed to {kept} lines" if kept >= 0
                  else f"[log] no event log for {rest[0]}")
    elif v == "export":
        if not rest:
            print("  /log export PATH [DATE]")
        else:
            date    = rest[1] if len(rest) > 1 else None
            written = _admin.export_log(rest[0], date)
            print(f"[log] exported {len(written)} file(s) → {rest[0]}"
                  if written else "[log] nothing matched")
    elif v == "delete":
        if not rest:
            print("  /log delete DATE")
        else:
            removed = _admin.delete_log(rest[0])
            print(f"[log] deleted {', '.join(removed)}" if removed
                  else f"[log] no logs for {rest[0]}")
    else:
        print("  /log [N] | list | show [DATE [N]] | export PATH [DATE] | trim DATE N | delete DATE")


# ── command parsing ───────────────────────────────────────────────────────────

def _parse(
    line: str,
    tmp: Path,
    idx: int,
) -> tuple[str, list[Path], list[Path], str]:
    """Parse a line of input. Returns (user_text, images, audios, action).

    action=''     → run a model turn with user_text
    action='exit' → quit
    Other action strings are handled in the main loop.
    For commands that carry an argument, the argument is in user_text.
    """
    text = line.strip()
    if not text:
        return "", [], [], ""

    low = text.lower()

    # ── simple commands ──────────────────────────────────────────────────
    if low in {"/exit", "/quit"}:    return "", [], [], "exit"
    if low == "/clear":              return "", [], [], "clear"
    if low == "/help":               return "", [], [], "help"
    if low == "/help set":           return "", [], [], "help_set"
    if low == "/status":             return "", [], [], "status"
    if low == "/context":            return "", [], [], "context"
    if low == "/vision on":          return "", [], [], "vision_on"
    if low == "/vision off":         return "", [], [], "vision_off"
    if low == "/audio-on":           return "", [], [], "audio_on"
    if low == "/audio-off":          return "", [], [], "audio_off"
    if low == "/skip-retrieval":     return "", [], [], "toggle_retrieval"
    if low == "/config":             return "", [], [], "config"
    if low == "/obs":                return "", [], [], "obs"

    # ── commands with arguments ──────────────────────────────────────────
    parts = text.split(maxsplit=2)
    cmd   = parts[0].lower()

    # /set KEY VAL
    if cmd == "/set":
        if len(parts) < 3:
            return "", [], [], "set_usage"
        arg = parts[1] + " " + parts[2]   # "KEY VAL" in user_text
        return arg, [], [], "set"

    # /server VERB
    if cmd == "/server":
        return parts[1] if len(parts) > 1 else "", [], [], "server"

    # /db [VERB]
    if cmd == "/db":
        return parts[1] if len(parts) > 1 else "", [], [], "db"

    # /mem [VERB [ARGS]]   — full remainder carried in user_text
    if cmd == "/mem":
        return text.removeprefix(parts[0]).strip(), [], [], "mem"

    # /journal [SUBCMD [ARGS]]
    if cmd == "/journal":
        return text.removeprefix(parts[0]).strip(), [], [], "journal"

    # /log [SUBCMD [ARGS] | N]
    if cmd == "/log":
        return text.removeprefix(parts[0]).strip(), [], [], "log"

    # /tasks [add TEXT | done TEXT | remember TEXT | clear [scope]]
    if cmd == "/tasks":
        return text.removeprefix(parts[0]).strip(), [], [], "tasks"

    # /screenshot [q]
    if cmd == "/screenshot":
        q   = text.removeprefix(parts[0]).strip() or "What do you see on my screen?"
        out = tmp / f"ss-{idx}.png"
        try:
            capture_now(out)
        except RuntimeError as e:
            print(f"[screenshot] {e}")
            return "", [], [], ""
        return q, [out], [], ""

    if cmd == "/image" and len(parts) >= 2:
        img = Path(parts[1]).expanduser().resolve()
        q   = parts[2] if len(parts) > 2 else "Describe this image."
        return q, [img], [], ""

    if cmd == "/audio" and len(parts) >= 2:
        aud = Path(parts[1]).expanduser().resolve()
        q   = parts[2] if len(parts) > 2 else "What do you hear?"
        return q, [], [aud], ""

    if cmd == "/record" and len(parts) >= 2:
        try:
            secs = float(parts[1])
        except ValueError:
            print("[record] usage: /record SECONDS [question]")
            return "", [], [], ""
        q   = parts[2] if len(parts) > 2 else "What did I say?"
        out = tmp / f"rec-{idx}.wav"
        try:
            record_now(out, secs)
        except RuntimeError as e:
            print(f"[record] {e}")
            return "", [], [], ""
        return q, [], [out], ""

    if cmd.startswith("/"):
        print(f"Unknown command '{cmd}'. Type /help.")
        return "", [], [], ""

    return text, [], [], ""


# ── answer display ────────────────────────────────────────────────────────────

def _print_answer(answer: str, width: int = 100) -> None:
    lines = answer.splitlines()
    out: list[str] = []
    for i, line in enumerate(lines):
        prefix = "LAWRENCE> " if i == 0 else "          "
        wrapped = textwrap.wrap(line, width=width - len(prefix)) or [""]
        out.append(prefix + wrapped[0])
        for cont in wrapped[1:]:
            out.append(" " * len(prefix) + cont)
    print("\n" + "\n".join(out))


def _print_briefing(finding: dict, width: int = 100) -> None:
    """Render an unprompted proactive finding as a boxed card."""
    inner = width - 2
    head  = finding.get("headline", "").strip()
    body  = finding.get("insight", "").strip()
    cites = finding.get("citations", [])

    out = ["\n╭─ ⚡ LAWRENCE noticed " + "─" * (inner - 20)]
    for w in textwrap.wrap(head, inner - 2) or [""]:
        out.append(f"│ {w}")
    out.append("│")
    for line in body.splitlines() or [""]:
        for w in textwrap.wrap(line, inner - 2) or [""]:
            out.append(f"│ {w}")
    if cites:
        out.append("│")
        for c in cites[:4]:
            ref = f"[{c['num']}] {c.get('title') or c.get('url','')}"
            out.append(f"│ {ref[:inner - 2]}")
    out.append("╰" + "─" * (inner + 1))
    print("\n".join(out))


# ── help ──────────────────────────────────────────────────────────────────────

def _print_help() -> None:
    print(
        "\nCommands  (see docs/CLI.md for the full reference)\n"
        "\n  ── ask / attach ──────────────────────────────────────────────────────\n"
        "  text                    send a query\n"
        "  /screenshot [q]         attach a screen capture\n"
        "  /image PATH [q]         attach an image file\n"
        "  /audio PATH [q]         attach an audio file\n"
        "  /record SECS [q]        record mic for SECS seconds\n"
        "\n  ── sensors ───────────────────────────────────────────────────────────\n"
        "  /vision on|off          rolling screen observer\n"
        "  /audio-on|off           rolling audio observer\n"
        "  /obs                    live preprocessor state (frame Δ, OCR, audio)\n"
        "\n  ── rolling memory (L1/L2/L3) ──────────────────────────────────────────\n"
        "  /context                what the model reads (L3→L2→L1)\n"
        "  /mem info                       sizes, budget, compaction state\n"
        "  /mem show [l1|l2|l3]            print a layer (default: all)\n"
        "  /mem clear [l1|l2|l3|all]       wipe a layer (or everything)\n"
        "  /mem archive                    snapshot + truncate L1 (new session)\n"
        "  /mem export PATH                dump layers to a folder\n"
        "  /clear                          shortcut for /mem clear all\n"
        "\n  ── event + turn logs ──────────────────────────────────────────────────\n"
        "  /log [N]                        tail today's event log (default 30)\n"
        "  /log list                       all log dates + sizes\n"
        "  /log show [DATE [N]]            view a day's event log\n"
        "  /log export PATH [DATE]         copy logs out\n"
        "  /log trim DATE N                keep only the last N lines\n"
        "  /log delete DATE                remove a day's event + turn logs\n"
        "\n  ── journal (daily MDX) ────────────────────────────────────────────────\n"
        "  /journal                        write + show an entry now\n"
        "  /journal list                   all journal dates\n"
        "  /journal show [DATE]            view a journal\n"
        "  /journal edit [DATE]            open in $EDITOR\n"
        "  /journal export PATH [DATE]     copy journal(s) out\n"
        "  /journal delete DATE            remove a journal\n"
        "\n  ── config / server / retrieval ───────────────────────────────────────\n"
        "  /status                 server + observer + memory state\n"
        "  /config                 every configurable setting\n"
        "  /set KEY VAL            change a setting live (see /help set)\n"
        "  /server start|stop|restart|status\n"
        "  /db info|clear          semantic retrieval cache\n"
        "  /skip-retrieval         toggle web retrieval\n"
        "\n  ── session ────────────────────────────────────────────────────────────\n"
        "  /help   /help set       this list / all /set keys\n"
        "  /exit, /quit            quit (writes journal automatically)\n"
        "  DATE = today | yesterday | YYYY-MM-DD\n"
    )


def _print_help_set() -> None:
    print(
        "\n/set KEY VAL — all configurable keys:\n"
        "\n  ── server (staged: need /server restart) ──────────────────────────────\n"
        "  model PATH          path to GGUF model file\n"
        "  bin PATH            path to llama-server binary\n"
        "  mmproj PATH|auto    multimodal projector (auto = detect next to model)\n"
        "  ctx N               context window tokens (default 65536)\n"
        "  threads N           inference threads (default 9)\n"
        "  gpu-layers N        GPU offload layers (0 = CPU only)\n"
        "  kv-type q4_0|q8_0|f16|none\n"
        "  flash-attn on|off|auto\n"
        "  jinja on|off\n"
        "\n  ── turn (live) ────────────────────────────────────────────────────────\n"
        "  max-tokens N        max response tokens (default 2048)\n"
        "  temp F              temperature 0.0-1.0 (default 0.2)\n"
        "  timeout N           per-turn timeout seconds (default 300)\n"
        "  retrieval on|off    web/DB retrieval (default on)\n"
        "  analysis on|off     analysis pre-pass (default on)\n"
        "\n  ── retrieval (live) ────────────────────────────────────────────────────\n"
        "  retrieval-top-k N   final results returned to model (default 6)\n"
        "  retrieval-fresh N   web results per query (default 3)\n"
        "  retrieval-db-min N  min DB hits before hitting web (default 3)\n"
        "\n  ── vision gate + observer (live) ──────────────────────────────────────\n"
        "  vision-high F         score >= this → always write (default 0.50)\n"
        "  vision-pixel-min F    score below this → skip (default 0.10)\n"
        "  vision-novelty-min F  text Jaccard distance required (default 0.30)\n"
        "  vision-interval N     poll every N seconds (default 10)\n"
        "  vision-write-min N    min gap between context writes (default 60s)\n"
        "  vision-regions on|off per-window OCR vs whole-screen (default on)\n"
        "  region-ema F          box smoothing 0-1, higher=snappier (default 0.4)\n"
        "  region-change-min F   per-region pixel change to re-OCR (default 0.06)\n"
        "\n  ── audio gate (live) ──────────────────────────────────────────────────\n"
        "  audio-min-words N   minimum words to pass gate (default 3)\n"
        "  audio-dedup-max F   Jaccard sim ceiling before dedup-skip (default 0.60)\n"
        "\n  ── proactive (live) ───────────────────────────────────────────────────\n"
        "  proactive-interval N  min seconds between proactive calls (default 600)\n"
        "  proactive-present on|off  surface findings unprompted vs. warm cache (default on)\n"
        "\n  ── memory compaction (live) ────────────────────────────────────────────\n"
        "  compact-min N   min seconds between compaction runs (default 300)\n"
        "  l2-budget N     L2 summary budget chars before L2→L3 (default 10000)\n"
        "  l3-budget N     L3 long-range budget chars (default 4000)\n"
        "\n  ── backend (api only; select at launch with --api-base) ────────────────\n"
        "  api-model NAME  model name sent to the external API endpoint\n"
    )


# ── status ────────────────────────────────────────────────────────────────────

def _print_status(
    vision: "VisionObserver | None",
    audio:  "AudioObserver  | None",
    ctx:    ContextStore,
    state:  _LiveState,
) -> None:
    ok = _model.health()
    if state.backend == "api":
        print(f"  backend: {'reachable' if ok else 'UNREACHABLE'} ({_model.describe_backend()})")
    else:
        print(f"  server : {'healthy' if ok else 'DOWN'} @ {_server.server_url()}")
        if state.server_dirty:
            print("  [!] staged settings changed — /server restart to apply")
    print(
        f"  memory : L1={ctx._l1_size // 1024}K  "
        f"L2={ctx._l2_size // 1024}K  "
        f"L3={ctx._l3_size // 1024}K  "
        f"| budget {ctx.working_budget() // 1024}K chars"
    )
    if vision:
        f = vision.latest
        print(f"  vision : ON | Δ={f.change_score:.2f}" if f else "  vision : ON | no frame yet")
    else:
        print("  vision : OFF")
    if audio:
        mic  = "" if audio.recording_ok else " (no mic)"
        print(f"  audio  : {'ON' if audio.active else 'OFF'}{mic}")
    else:
        print("  audio  : OFF")
    print(f"  proactive-interval : {state.proactive_interval}s")


# ── desktop notification (best-effort) ────────────────────────────────────────

def _notify(title: str, body: str) -> None:
    import shutil, subprocess
    body_s = body[:200].replace('"', "'").replace("\n", " ")
    try:
        if shutil.which("notify-send"):
            subprocess.Popen(
                ["notify-send", "--expire-time=8000", title, body_s],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        elif shutil.which("powershell.exe"):
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n=New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon=[System.Drawing.SystemIcons]::Information;"
                "$n.Visible=$true;"
                f'$n.ShowBalloonTip(8000,"{title}","{body_s}",0);'
                "Start-Sleep -Milliseconds 600;$n.Dispose();"
            )
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


# ── proactive trigger ────────────────────────────────────────────────────────

def _make_proactive_trigger(
    ctx: ContextStore,
    retrieval: RetrievalPipeline,
    cfg: TurnConfig,
    state: _LiveState,
    live_fn:    "Callable[[str], None] | None"  = None,
    present_fn: "Callable[[dict], None] | None" = None,
) -> Callable[[str, str], None]:
    """
    Returns an on_event callback for sensor observers — the autonomous trigger.
    Reads state live so /set proactive-interval and /set proactive-present take
    effect without a CLI restart. present_fn is passed to run_proactive only when
    surfacing is enabled, so disabling it also skips the extra briefing model call.
    """
    _lock = threading.Lock()
    _last_run: list[float] = [0.0]

    def _on_event(kind: str, compact: str) -> None:
        if cfg.no_retrieval or cfg.skip_analysis:
            return
        if time.monotonic() - _last_run[0] < state.proactive_interval:
            return
        if not _lock.acquire(blocking=False):
            return
        _last_run[0] = time.monotonic()
        pf = present_fn if state.proactive_present else None

        def _run() -> None:
            try:
                run_proactive(ctx, retrieval, live_fn=live_fn, present_fn=pf)
            finally:
                _lock.release()
        threading.Thread(target=_run, daemon=True, name="proactive").start()

    return _on_event


# ── audio query handler ───────────────────────────────────────────────────────

def _make_audio_query_handler(
    ctx: ContextStore,
    retrieval: RetrievalPipeline,
    cfg: TurnConfig,
    ui: UIConnector,
    response_q: "queue.Queue[str]",
    control_q:  "queue.Queue[dict]",
    vision_ref: "list[VisionObserver | None]",
    capture_fn: "Callable[[], Path | None] | None" = None,
    live_fn:    "Callable[[str], None] | None"     = None,
    tasks_fn:   "Callable[[dict], None] | None"    = None,
) -> Callable[[str], None]:
    _lock = threading.Lock()

    def _on_query(transcript: str) -> None:
        if not _lock.acquire(blocking=False):
            return

        images: list[Path] = []
        vi = vision_ref[0]
        if vi is not None and vi.pending_hi:
            hi = vi.consume_pending_hi()
            if hi is not None and hi.exists():
                images = [hi]

        def _run() -> None:
            try:
                answer, controls = run_turn(
                    transcript,
                    ctx=ctx, retrieval=retrieval,
                    cfg=cfg, images=images, audios=[], ui=ui,
                    capture_fn=capture_fn, live_fn=live_fn,
                    tasks_fn=tasks_fn,
                )
                msg = f"\n[heard] {transcript}\nLAWRENCE> {answer}"
                response_q.put(msg)
                if controls:
                    control_q.put(controls)
                _notify("LAWRENCE", answer)
            except Exception as e:
                response_q.put(f"\n[audio-turn error] {e}")
            finally:
                _lock.release()

        threading.Thread(target=_run, daemon=True, name="audio-turn").start()

    return _on_query


# ── non-blocking stdin reader ─────────────────────────────────────────────────

def _start_stdin_reader(input_q: "queue.Queue[str | None]") -> None:
    def _read() -> None:
        while True:
            try:
                line = sys.stdin.readline()
            except (OSError, EOFError):
                input_q.put(None)
                return
            input_q.put(None if not line else line.rstrip("\n"))
            if not line:
                return
    threading.Thread(target=_read, daemon=True, name="stdin").start()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = _args()
    print("\nLAWRENCE v0.1")

    # ── backend selection ───────────────────────────────────────────────────
    # External API backend if --api-base / $LK_API_BASE is set; else local server.
    api_base = args.api_base or os.environ.get("LK_API_BASE")
    use_api  = bool(api_base)

    if use_api:
        _model.configure_backend(
            kind="api",
            base_url=api_base,
            api_key=args.api_key or os.environ.get("LK_API_KEY"),
            model=args.api_model or os.environ.get("LK_API_MODEL"),
        )
        # No local model files → modalities come from env (default text-only).
        vis = _env_flag("LK_VISION", False)
        aud = _env_flag("LK_AUDIO", False)
        profile = ModelProfile(
            model=Path(_model.backend().model or "api-model"), bin=Path("(api)"),
            mmproj=None, vision=vis, audio=aud, ctx_size=args.ctx_size,
            flash_attn="off", kv_type=None, jinja=False,
        )
        print(f"  backend      : {_model.describe_backend()}")
        if not _model.backend().model:
            print("  [api] no model set — use --api-model or $LK_API_MODEL", file=sys.stderr)
    else:
        profile = ModelProfile.detect(
            model=args.model, bin_path=args.bin,
            mmproj=args.mmproj, ctx_size=args.ctx_size,
        )

    # profile_ref lets server-restart update the profile without restarting CLI
    profile_ref: list[ModelProfile] = [profile]

    # Local backend: start the server (failure → degraded). API backend: probe reachability.
    if use_api:
        print(f"  backend      : {'reachable' if _model.health() else 'UNREACHABLE'} ({_model.describe_backend()})")
    else:
        try:
            _server.start(profile, gpu_layers=args.gpu_layers, threads=args.threads)
        except RuntimeError as e:
            print(f"  [server] failed to start: {e}", file=sys.stderr)
            print("  [server] running in degraded mode — use /server start to retry")

    def _on_signal(sig: int, _f: object) -> None:
        if args.stop_server:
            _server.stop()
        sys.exit(128 + sig)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGHUP,  _on_signal)

    # queues for threaded I/O
    input_q:    queue.Queue[str | None] = queue.Queue()
    response_q: queue.Queue[str]        = queue.Queue()
    control_q:  queue.Queue[dict]       = queue.Queue()
    live_q:     queue.Queue[str]        = queue.Queue()
    brief_q:    queue.Queue[dict]       = queue.Queue()   # proactive findings to surface

    # mutable reference: audio-query handler and control handler always get latest observer
    vision_ref: list[VisionObserver | None] = [None]

    def _ctx_live(msg: str) -> None:
        if msg.startswith("[memory]"):
            live_q.put(msg)

    ctx       = ContextStore(compact_fn=run_compaction, live_fn=_ctx_live)
    db        = SemanticDB()
    pipeline  = RetrievalPipeline(db)
    ui        = UIConnector()
    tasks     = TaskStore()   # self-curated TODO + remember (shared with desktop UI)

    def _tasks_fn(proposals: dict) -> None:
        summary = tasks.apply_model(proposals)
        bits = []
        if summary.get("added"):      bits.append(f"+{len(summary['added'])} task")
        if summary.get("done"):       bits.append(f"✓{len(summary['done'])} done")
        if summary.get("remembered"): bits.append(f"★{len(summary['remembered'])} noted")
        if bits:
            live_q.put("[tasks] " + " ".join(bits))

    cfg = TurnConfig(
        max_tokens    = args.max_tokens,
        temperature   = args.temp,
        timeout       = args.timeout,
        skip_analysis = args.skip_analysis,
        no_retrieval  = args.no_retrieval,
        allow_images  = profile.vision,
        allow_audio   = profile.audio,
    )

    # Live state — single source of truth for all configurable parameters
    state = _LiveState(
        model_path   = Path(args.model).expanduser().resolve(),
        bin_path     = Path(args.bin).expanduser().resolve(),
        mmproj_path  = Path(args.mmproj).expanduser().resolve() if args.mmproj else None,
        ctx_size     = args.ctx_size,
        gpu_layers   = args.gpu_layers,
        threads      = args.threads,
        kv_type      = profile.kv_type or "f16",
        flash_attn   = profile.flash_attn,
        jinja        = profile.jinja,
        max_tokens   = args.max_tokens,
        temperature  = args.temp,
        timeout      = args.timeout,
        no_retrieval = args.no_retrieval,
        skip_analysis = args.skip_analysis,
        compact_min  = ctx._min_compact_secs,
        l2_budget    = ctx.l2_budget,
        l3_budget    = ctx.l3_budget,
        backend      = "api" if use_api else "local",
        api_base     = api_base or "",
        api_model    = (_model.backend().model or "") if use_api else "",
    )

    print(f"  model        : {profile.modalities}")
    print(f"  event log    : {ctx._log}")
    print(f"  memory       : L1/L2/L3 in {ctx._mem_dir}")
    print(f"  retrieval DB : {db._con.execute('PRAGMA database_list').fetchone()[2]}")
    print(f"  mode         : {'single-pass' if args.skip_analysis else 'analysis → retrieval → respond'}")
    if args.audio_query and not profile.audio:
        print("  audio-query  : requested but model has no audio input — disabled")
    elif args.audio_query:
        print("  audio-query  : ON — speech triggers full turns automatically")
    print("  Type /help for commands.\n")

    def _present_finding(finding: dict) -> None:
        brief_q.put(finding)
        _notify("LAWRENCE noticed", finding.get("headline", ""))

    on_proactive = _make_proactive_trigger(
        ctx, pipeline, cfg, state, live_fn=live_q.put, present_fn=_present_finding,
    )

    # Ingest events captured by an out-of-process sensor (lk.sensor) — keeps
    # vision/audio working when this kernel is headless (e.g. in a container).
    spool_reader: SpoolReader | None = None
    if args.ingest_spool:
        spool_dir = Path(args.ingest_spool).expanduser().resolve()
        spool_reader = SpoolReader(spool_dir, ctx, on_event=on_proactive)
        spool_reader.start()
        print(f"  ingest spool : {spool_dir}")

    _start_stdin_reader(input_q)

    with tempfile.TemporaryDirectory(prefix="lawrence-") as tmp_str:
        tmp = Path(tmp_str)

        vision: VisionObserver | None = None
        audio:  AudioObserver  | None = None
        _hi_idx = [0]

        def capture_fn() -> Path | None:
            vi = vision_ref[0]
            if vi is None:
                return None
            _hi_idx[0] += 1
            return vi.pull_hires(tmp / f"model-hi-{_hi_idx[0]}.png")

        # ── observer lifecycle ──────────────────────────────────────────────────
        def _start_vision() -> bool:
            nonlocal vision
            if not profile_ref[0].vision or vision is not None:
                return False
            vision = VisionObserver(
                tmp, ctx, on_event=on_proactive,
                poll_interval=state.vision_interval,
                min_write_secs=state.vision_write_min,
            )
            vision.regions          = state.vision_regions
            vision.region_change_min = state.region_change_min
            vision._tracker.ema      = state.region_ema
            vision_ref[0] = vision
            vision.start()
            return True

        def _stop_vision() -> bool:
            nonlocal vision
            if vision is None:
                return False
            vision.stop()
            vision = vision_ref[0] = None
            return True

        def _start_audio() -> bool:
            nonlocal audio
            if not profile_ref[0].audio or audio is not None:
                return False
            on_query = (
                _make_audio_query_handler(
                    ctx, pipeline, cfg, ui, response_q, control_q,
                    vision_ref, capture_fn=capture_fn, live_fn=live_q.put,
                    tasks_fn=_tasks_fn,
                ) if args.audio_query else None
            )
            audio = AudioObserver(
                tmp, ctx,
                on_event=on_proactive if not args.audio_query else None,
                on_query=on_query,
            )
            audio.start()
            return True

        def _stop_audio() -> bool:
            nonlocal audio
            if audio is None:
                return False
            audio.stop()
            audio = None
            return True

        def _apply_controls(ctrl: dict) -> None:
            v, a = ctrl.get("vision", ""), ctrl.get("audio", "")
            if v == "hi":
                live_q.put("[vision] model requested hi-res — captured" if capture_fn()
                           else "[vision] hi-res requested but observer is off")
            elif v == "on" and _start_vision():
                live_q.put("[vision] observer started by model")
            elif v == "off" and _stop_vision():
                live_q.put("[vision] observer stopped by model")
            if a == "on" and _start_audio():
                live_q.put("[audio] observer started by model")
            elif a == "off" and _stop_audio():
                live_q.put("[audio] observer stopped by model")

        if not args.no_vision and _start_vision():
            print("  Vision observer started.")
        if not args.no_audio and _start_audio():
            print("  Audio observer started.")

        idx = 0
        sys.stdout.write("\nyou> ")
        sys.stdout.flush()

        try:
            while True:
                # ── rolling live events ───────────────────────────────────────────
                while not live_q.empty():
                    try:
                        msg = live_q.get_nowait()
                        sys.stdout.write(f"\r  ▸ {msg}\nyou> ")
                        sys.stdout.flush()
                    except queue.Empty:
                        break

                # ── model-emitted controls ────────────────────────────────────────
                while not control_q.empty():
                    try:
                        _apply_controls(control_q.get_nowait())
                    except queue.Empty:
                        break

                # ── background responses (audio-triggered turns) ──────────────────
                while not response_q.empty():
                    try:
                        msg = response_q.get_nowait()
                        sys.stdout.write(f"\r{msg}\nyou> ")
                        sys.stdout.flush()
                    except queue.Empty:
                        break

                # ── proactive findings surfaced unprompted ────────────────────────
                while not brief_q.empty():
                    try:
                        sys.stdout.write("\r")
                        _print_briefing(brief_q.get_nowait())
                        sys.stdout.write("\nyou> ")
                        sys.stdout.flush()
                    except queue.Empty:
                        break

                # ── poll for user input (non-blocking, 150ms timeout) ─────────────
                try:
                    raw = input_q.get(timeout=0.15)
                except queue.Empty:
                    continue

                if raw is None:   # EOF
                    print()
                    break

                idx += 1
                user_text, images, audios, action = _parse(raw, tmp, idx)

                # ── command dispatch ──────────────────────────────────────────────
                if action == "exit":
                    break

                elif action == "clear":
                    ctx.clear_rolling()
                    print("[rolling context cleared — L1, L2, L3 wiped]")

                elif action == "help":
                    _print_help()

                elif action == "help_set":
                    _print_help_set()

                elif action == "status":
                    _print_status(vision, audio, ctx, state)

                elif action == "config":
                    _print_config(state, profile_ref[0], pipeline)

                elif action == "obs":
                    _print_obs(vision, audio)

                elif action == "context":
                    print("\n[MEMORY CONTEXT — L1/L2/L3 — model input]\n" + ctx.tail_for_model())

                elif action == "log":
                    _do_log(user_text, ctx)

                elif action == "journal":
                    _do_journal(user_text, ctx)

                elif action == "tasks":
                    sub  = user_text.split(maxsplit=1)
                    verb = sub[0].lower() if sub else ""
                    rest = sub[1] if len(sub) > 1 else ""
                    if verb == "add" and rest:
                        tasks.add_task(rest, source="user")
                        print(f"[tasks] added: {rest}")
                    elif verb in ("done", "complete") and rest:
                        t = tasks.complete_task(text=rest, source="user")
                        print(f"[tasks] done: {t['text']}" if t else "[tasks] no match")
                    elif verb == "remember" and rest:
                        tasks.add_remember(rest, source="user")
                        print(f"[remember] {rest}")
                    elif verb == "clear":
                        tasks.clear(rest or "all")
                        print(f"[tasks] cleared {rest or 'all'}")
                    else:
                        snap = tasks.snapshot()
                        c = snap["counts"]
                        print(f"\n[TASKS — {c['open']} open / {c['done']} done]")
                        for t in snap["tasks"]:
                            mark = "x" if t["status"] == "done" else " "
                            tag  = " (auto)" if t.get("source") == "model" else ""
                            print(f"  [{mark}] {t['text']}{tag}")
                        if snap["remember"]:
                            print(f"\n[REMEMBER — {len(snap['remember'])}]")
                            for r in snap["remember"]:
                                tag = " (auto)" if r.get("source") == "model" else ""
                                print(f"  • {r['text']}{tag}")

                elif action == "vision_on":
                    if not profile_ref[0].vision:
                        print("[vision] model has no vision input — unavailable")
                    else:
                        print("[vision on]" if _start_vision() else "[vision already on]")

                elif action == "vision_off":
                    print("[vision off]" if _stop_vision() else "[vision already off]")

                elif action == "audio_on":
                    if not profile_ref[0].audio:
                        print("[audio] model has no audio input — unavailable")
                    else:
                        print("[audio on]" if _start_audio() else "[audio already on]")

                elif action == "audio_off":
                    print("[audio off]" if _stop_audio() else "[audio already off]")

                elif action == "toggle_retrieval":
                    cfg.no_retrieval = state.no_retrieval = not cfg.no_retrieval
                    print(f"[retrieval {'OFF' if cfg.no_retrieval else 'ON'}]")

                elif action == "set":
                    # user_text = "KEY VAL"
                    parts = user_text.split(maxsplit=1)
                    if len(parts) < 2:
                        print("[set] usage: /set KEY VAL — see /help set for keys")
                    else:
                        msg = _apply_set(parts[0], parts[1], state, cfg, ctx, pipeline, vision_ref)
                        print(msg)

                elif action == "set_usage":
                    print("[set] usage: /set KEY VAL — see /help set for keys")

                elif action == "server":
                    _do_server(user_text, state, profile_ref, cfg)

                elif action == "db":
                    _do_db(user_text, db)

                elif action == "mem":
                    _do_mem(user_text, ctx)

                if not user_text or action:
                    sys.stdout.write("\nyou> ")
                    sys.stdout.flush()
                    continue

                # ── backend health gate ───────────────────────────────────────────
                if not _model.health():
                    if state.backend == "api":
                        print(f"[API backend unreachable — {_model.describe_backend()}]")
                    else:
                        print("[server is DOWN — use /server start or /server restart]")
                    sys.stdout.write("\nyou> ")
                    sys.stdout.flush()
                    continue

                # drop manually-attached media the model can't consume
                if images and not profile_ref[0].vision:
                    print("[note] model has no vision input — ignoring attached image(s)")
                    images = []
                if audios and not profile_ref[0].audio:
                    print("[note] model has no audio input — ignoring attached audio")
                    audios = []

                # claim pending high-res screenshot from vision observer
                if vision and vision.pending_hi:
                    hi = vision.consume_pending_hi()
                    if hi and hi not in images:
                        images = [hi] + images

                bad = [p for p in images + audios if not p.exists()]
                if bad:
                    for p in bad:
                        print(f"[error] not found: {p}")
                    sys.stdout.write("\nyou> ")
                    sys.stdout.flush()
                    continue

                try:
                    t0 = time.monotonic()
                    sys.stdout.write("  [thinking…]")
                    sys.stdout.flush()
                    answer, controls = run_turn(
                        user_text,
                        ctx=ctx, retrieval=pipeline,
                        cfg=cfg, images=images, audios=audios, ui=ui,
                        capture_fn=capture_fn, live_fn=live_q.put,
                        tasks_fn=_tasks_fn,
                    )
                    elapsed = int((time.monotonic() - t0) * 1000)
                    sys.stdout.write(f"\r  done ({elapsed}ms)      \n")
                    if controls:
                        _apply_controls(controls)
                except KeyboardInterrupt:
                    print("\n[interrupted]")
                    sys.stdout.write("\nyou> ")
                    sys.stdout.flush()
                    continue
                except Exception as e:
                    print(f"\n[error] {e}")
                    sys.stdout.write("\nyou> ")
                    sys.stdout.flush()
                    continue

                _print_answer(answer)
                sys.stdout.write("\nyou> ")
                sys.stdout.flush()

        finally:
            if vision:
                vision.stop()
            if audio:
                audio.stop()
            if spool_reader:
                spool_reader.stop()
            print("  [writing session journal…]")
            entry = write_journal_entry(ctx)
            if entry:
                print(f"  [journal] {entry[:120]}{'…' if len(entry) > 120 else ''}")
            db.close()
            if args.stop_server:
                _server.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
