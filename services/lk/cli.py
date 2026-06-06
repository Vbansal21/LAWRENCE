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
from .ctx        import ContextStore
from .ctx        import gate as _gate_mod
from .ctx.gate   import gate_config
from .kernel     import run_turn, run_proactive, run_compaction, write_journal_entry, TurnConfig
from .obs        import VisionObserver, AudioObserver, capture_now, record_now
from .obs.vision import POLL_INTERVAL, MIN_WRITE_SECS
from .profile    import ModelProfile
from .retrieval  import SemanticDB, RetrievalPipeline
from .ui         import UIConnector


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
    p.add_argument("--model",   default=str(_server.DEFAULT_MODEL))
    p.add_argument("--mmproj",  default=None,
                   help="multimodal projector GGUF (auto-detected next to --model if omitted)")
    p.add_argument("--bin",     default=str(_server.DEFAULT_BIN))
    p.add_argument("--ctx-size",    type=int,   default=32_768)
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

    # ── turn ──────────────────────────────────────────────────────────────
    max_tokens:   int   = 2048
    temperature:  float = 0.2
    timeout:      int   = 300
    no_retrieval: bool  = False
    skip_analysis: bool = False

    # ── observer tunables ─────────────────────────────────────────────────
    vision_interval:   float = POLL_INTERVAL
    vision_write_min:  int   = MIN_WRITE_SECS
    vision_high:       float = field(default_factory=lambda: gate_config.vision_high)
    vision_pixel_min:  float = field(default_factory=lambda: gate_config.vision_pixel_min)
    vision_novelty_min: float = field(default_factory=lambda: gate_config.vision_novelty_min)
    audio_min_words:   int   = field(default_factory=lambda: gate_config.audio_min_words)
    audio_dedup_max:   float = field(default_factory=lambda: gate_config.audio_dedup_max)

    # ── proactive ─────────────────────────────────────────────────────────
    proactive_interval: float = 600.0   # 10-minute minimum between proactive calls

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

    return f"[set] unknown key '{key}' — use /help set for all keys"


# ── /server handler ───────────────────────────────────────────────────────────

def _do_server(
    verb: str,
    state: _LiveState,
    profile_ref: "list[ModelProfile]",
    cfg: TurnConfig,
) -> None:
    v = verb.strip().lower() if verb else "status"

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
    print(
        f"\n[CONFIG]{dirty}"
        f"\n  ── server (staged: need /server restart) ──────────────────────────────"
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
        f"\n  ── audio gate (live) ──────────────────────────────────────────────────"
        f"\n  audio-min-words : {state.audio_min_words}"
        f"\n  audio-dedup-max : {state.audio_dedup_max}"
        f"\n  ── proactive (live) ───────────────────────────────────────────────────"
        f"\n  proactive-interval : {state.proactive_interval}s"
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


def _do_mem(verb: str, ctx: ContextStore) -> None:
    v = verb.strip().lower() if verb else "info"
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
    elif v == "clear":
        ctx.clear_rolling()
        print("[memory cleared — L1, L2, L3 wiped]")
    elif v == "archive":
        ctx._archive_l1()
        print("[memory] L1 archived — new session started")
    else:
        print("  /mem info|clear|archive")


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
    if low == "/log":                return "", [], [], "log"
    if low == "/journal":            return "", [], [], "journal"
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

    # /mem [VERB]
    if cmd == "/mem":
        return parts[1] if len(parts) > 1 else "", [], [], "mem"

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


# ── help ──────────────────────────────────────────────────────────────────────

def _print_help() -> None:
    print(
        "\nCommands:\n"
        "  text                    send a query\n"
        "  /screenshot [q]         attach screen capture\n"
        "  /image PATH [q]         attach image file\n"
        "  /audio PATH [q]         attach audio file\n"
        "  /record SECS [q]        record mic\n"
        "\n"
        "  /vision on|off          rolling screen observer\n"
        "  /audio-on|off           rolling audio observer\n"
        "  /obs                    show live preprocessor state (frame, audio)\n"
        "\n"
        "  /context                show memory context (L1/L2/L3, model input)\n"
        "  /log                    show today's event log tail\n"
        "  /journal                write + print session journal entry\n"
        "  /status                 server + observer + memory state\n"
        "  /clear                  clear rolling context (L1+L2+L3)\n"
        "\n"
        "  /config                 show all configurable settings\n"
        "  /set KEY VAL            change a setting live (see /help set)\n"
        "  /server start|stop|restart|status\n"
        "\n"
        "  /db info|clear          semantic retrieval DB\n"
        "  /mem info|clear|archive memory layers\n"
        "  /skip-retrieval         toggle web retrieval\n"
        "  /exit                   quit (writes journal)\n"
    )


def _print_help_set() -> None:
    print(
        "\n/set KEY VAL — all configurable keys:\n"
        "\n  ── server (staged: need /server restart) ──────────────────────────────\n"
        "  model PATH          path to GGUF model file\n"
        "  bin PATH            path to llama-server binary\n"
        "  mmproj PATH|auto    multimodal projector (auto = detect next to model)\n"
        "  ctx N               context window tokens (default 32768)\n"
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
        "\n  ── audio gate (live) ──────────────────────────────────────────────────\n"
        "  audio-min-words N   minimum words to pass gate (default 3)\n"
        "  audio-dedup-max F   Jaccard sim ceiling before dedup-skip (default 0.60)\n"
        "\n  ── proactive (live) ───────────────────────────────────────────────────\n"
        "  proactive-interval N  min seconds between proactive calls (default 600)\n"
        "\n  ── memory compaction (live) ────────────────────────────────────────────\n"
        "  compact-min N   min seconds between compaction runs (default 300)\n"
        "  l2-budget N     L2 summary budget chars before L2→L3 (default 10000)\n"
        "  l3-budget N     L3 long-range budget chars (default 4000)\n"
    )


# ── status ────────────────────────────────────────────────────────────────────

def _print_status(
    vision: "VisionObserver | None",
    audio:  "AudioObserver  | None",
    ctx:    ContextStore,
    state:  _LiveState,
) -> None:
    ok = _server.health_check()
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
    live_fn: "Callable[[str], None] | None" = None,
) -> Callable[[str, str], None]:
    """
    Returns an on_event callback for sensor observers.
    Reads state.proactive_interval live so /set proactive-interval takes effect
    without a CLI restart.
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

        def _run() -> None:
            try:
                run_proactive(ctx, retrieval, live_fn=live_fn)
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

    # Build initial model profile from args + environment
    profile = ModelProfile.detect(
        model=args.model, bin_path=args.bin,
        mmproj=args.mmproj, ctx_size=args.ctx_size,
    )

    # profile_ref lets server-restart update the profile without restarting CLI
    profile_ref: list[ModelProfile] = [profile]

    # Attempt to start the server — failure enters degraded mode (no LLM turns)
    try:
        _server.start(profile, gpu_layers=args.gpu_layers, threads=args.threads)
    except RuntimeError as e:
        print(f"  [server] failed to start: {e}", file=sys.stderr)
        print(f"  [server] running in degraded mode — use /server start to retry")

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

    # mutable reference: audio-query handler and control handler always get latest observer
    vision_ref: list[VisionObserver | None] = [None]

    def _ctx_live(msg: str) -> None:
        if msg.startswith("[memory]"):
            live_q.put(msg)

    ctx       = ContextStore(compact_fn=run_compaction, live_fn=_ctx_live)
    db        = SemanticDB()
    pipeline  = RetrievalPipeline(db)
    ui        = UIConnector()

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

    on_proactive = _make_proactive_trigger(ctx, pipeline, cfg, state, live_fn=live_q.put)

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
                    print("\n[EVENT LOG — last 30]\n" + ctx.tail_compact(30))

                elif action == "journal":
                    print("  [writing journal…]")
                    entry = write_journal_entry(ctx)
                    if entry:
                        print(f"\n[JOURNAL]\n{entry}")
                    else:
                        print("[journal] nothing to journal yet")

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

                # ── server health gate ────────────────────────────────────────────
                if not _server.health_check():
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
