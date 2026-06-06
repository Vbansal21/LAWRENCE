"""LAWRENCE v0.1 — terminal entry point.

Wires together:
  - llama-server lifecycle (server.py)
  - Vision + audio observers (obs/) → write to ContextStore, trigger proactive
  - Retrieval pipeline (retrieval/) → semantic DB + web
  - LLM kernel (kernel/invoke.py) — called on user queries + audio triggers + proactive events
  - UI connector stub (ui/) — no-op in CLI mode

Two output paths:
  1. Explicit query (you type something) → run_turn() → printed inline
  2. Audio-triggered query (--audio-query) → run_turn() in background thread
       → response pushed to response_q → printed between input prompts

The main loop is non-blocking (stdin read in a daemon thread) so background
responses surface immediately without waiting for the user to press Enter.

Commands:
  /screenshot [q]     capture screen now and attach to next turn
  /image PATH [q]     attach image file
  /audio PATH [q]     attach audio file (raw, passed to model as native audio)
  /record SECS [q]    record microphone for SECS seconds and attach
  /vision on|off      start/stop rolling vision observer
  /audio-on|off       start/stop rolling audio observer
  /context            print rolling context tail (what the model will see)
  /log                print last 30 lines of context.log
  /status             server + observer status
  /clear              clear rolling context buffer (context.log preserved)
  /skip-retrieval     toggle retrieval on/off for this session
  /help               this help
  /exit, /quit        quit (server stays alive unless --stop-server)
"""
from __future__ import annotations

import argparse
import queue
import signal
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from . import server as _server
from .ctx      import ContextStore
from .kernel   import run_turn, run_proactive, run_compaction, write_journal_entry, TurnConfig
from .obs      import VisionObserver, AudioObserver, capture_now, record_now
from .retrieval import SemanticDB, RetrievalPipeline
from .ui       import UIConnector


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
    p.add_argument("--mmproj",  default=str(_server.DEFAULT_MMPROJ))
    p.add_argument("--bin",     default=str(_server.DEFAULT_BIN))
    p.add_argument("--ctx-size",    type=int,   default=32_768)
    p.add_argument("--gpu-layers",  type=int,   default=None)
    p.add_argument("--threads",     type=int,   default=None)
    p.add_argument("--max-tokens",  type=int,   default=2048)
    p.add_argument("--temp",        type=float, default=0.2)
    p.add_argument("--timeout",     type=int,   default=300)
    return p.parse_args()


# ── command parsing ───────────────────────────────────────────────────────────

def _parse(
    line: str,
    tmp: Path,
    idx: int,
) -> tuple[str, list[Path], list[Path], str]:
    """Returns (user_text, images, audios, action). action='' means run a turn."""
    text = line.strip()
    if not text:
        return "", [], [], ""

    low = text.lower()
    if low in {"/exit", "/quit"}:   return "", [], [], "exit"
    if low == "/clear":              return "", [], [], "clear"
    if low == "/help":               return "", [], [], "help"
    if low == "/status":             return "", [], [], "status"
    if low == "/context":            return "", [], [], "context"
    if low == "/log":                return "", [], [], "log"
    if low == "/journal":            return "", [], [], "journal"
    if low == "/vision on":          return "", [], [], "vision_on"
    if low == "/vision off":         return "", [], [], "vision_off"
    if low == "/audio-on":           return "", [], [], "audio_on"
    if low == "/audio-off":          return "", [], [], "audio_off"
    if low == "/skip-retrieval":     return "", [], [], "toggle_retrieval"

    parts = text.split(maxsplit=2)
    cmd   = parts[0].lower()

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
    """Print the model's answer wrapped at width chars, with LAWRENCE> prefix."""
    import textwrap
    lines = answer.splitlines()
    out: list[str] = []
    for i, line in enumerate(lines):
        prefix = "LAWRENCE> " if i == 0 else "          "
        wrapped = textwrap.wrap(line, width=width - len(prefix)) or [""]
        out.append(prefix + wrapped[0])
        for cont in wrapped[1:]:
            out.append(" " * len(prefix) + cont)
    print("\n" + "\n".join(out))


# ── status / help ─────────────────────────────────────────────────────────────

def _print_help() -> None:
    print(
        "\nCommands:\n"
        "  text                  send a query\n"
        "  /screenshot [q]       attach screen capture\n"
        "  /image PATH [q]       attach image\n"
        "  /audio PATH [q]       attach audio file\n"
        "  /record SECS [q]      record mic\n"
        "  /vision on|off        rolling screen observer\n"
        "  /audio-on|off         rolling audio observer\n"
        "  /context              show memory context (L1/L2/L3, model input)\n"
        "  /log                  show today's event log tail\n"
        "  /journal              write + print a journal entry for this session\n"
        "  /status               server + observer + memory state\n"
        "  /clear                clear rolling context (L1+L2+L3)\n"
        "  /skip-retrieval       toggle web retrieval\n"
        "  /exit                 quit (writes journal automatically)\n"
    )


def _print_status(
    vision: VisionObserver | None,
    audio:  AudioObserver  | None,
    ctx:    ContextStore,
    audio_query: bool = False,
) -> None:
    print(f"  server : {'healthy' if _server.health_check() else 'DOWN'} @ {_server.server_url()}")
    print(
        f"  memory : L1={ctx._l1_size//1024}K  "
        f"L2={ctx._l2_size//1024}K  "
        f"L3={ctx._l3_size//1024}K  "
        f"| working budget {ctx.working_budget()//1024}K chars"
    )
    if vision:
        f = vision.latest
        print(f"  vision : ON | latest Δ={f.change_score:.2f}" if f else "  vision : ON | no frame yet")
    else:
        print("  vision : OFF")
    if audio:
        mic  = "" if audio.recording_ok else " (no mic)"
        mode = " [audio-query mode]" if audio_query else ""
        print(f"  audio  : {'ON' if audio.active else 'OFF'}{mic}{mode}")
    else:
        print("  audio  : OFF")


# ── desktop notification (best-effort) ───────────────────────────────────────

def _notify(title: str, body: str) -> None:
    """Fire a desktop notification. Silent on failure — never blocks the caller."""
    import shutil, subprocess
    body_s = body[:200].replace('"', "'").replace("\n", " ")
    try:
        if shutil.which("notify-send"):
            subprocess.Popen(
                ["notify-send", "--expire-time=8000", title, body_s],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        elif shutil.which("powershell.exe"):
            # WSL → Windows balloon notification via .NET Windows Forms
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


# ── proactive background trigger ──────────────────────────────────────────────

def _make_proactive_trigger(
    ctx: ContextStore,
    retrieval: RetrievalPipeline,
    cfg: TurnConfig,
    live_fn: "Callable[[str], None] | None" = None,
) -> Callable[[str, str], None]:
    """
    Returns an on_event callback passed to the sensor observers.
    Non-blocking lock: concurrent events are silently dropped.
    Only one proactive call runs at a time; it doesn't block the observer.
    Minimum 10-minute gap between calls — avoids constant model hammering.
    """
    _lock = threading.Lock()
    _last_run: list[float] = [0.0]
    _MIN_INTERVAL = 600.0   # 10 minutes between proactive analysis calls

    def _on_event(kind: str, compact: str) -> None:
        if cfg.no_retrieval or cfg.skip_analysis:
            return
        if time.monotonic() - _last_run[0] < _MIN_INTERVAL:
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


# ── audio query trigger ───────────────────────────────────────────────────────

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
    """
    Returns an on_query callback for AudioObserver (--audio-query mode).
    Each gated speech transcript becomes a full run_turn() call.
    Controls emitted by the model are pushed to control_q for the main loop.
    """
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
    """Reads stdin in a daemon thread; puts lines (or None on EOF) into input_q."""
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

    try:
        _server.start(
            model=Path(args.model), mmproj=Path(args.mmproj),
            bin_path=Path(args.bin), ctx_size=args.ctx_size,
            gpu_layers=args.gpu_layers, threads=args.threads,
        )
    except RuntimeError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

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

    # mutable reference so the audio-query handler always sees the current
    # vision observer (may be None if /vision off was called)
    vision_ref: list[VisionObserver | None] = [None]

    def _ctx_live(msg: str) -> None:
        # Only forward memory-layer status messages to the terminal.
        # Raw sensor compacts ([VISION …], [AUDIO …], [TURN …]) are logged
        # to context.log by the store itself — no need to spam the terminal.
        if msg.startswith("[memory]"):
            live_q.put(msg)

    ctx       = ContextStore(compact_fn=run_compaction, live_fn=_ctx_live)
    db        = SemanticDB()
    retrieval = RetrievalPipeline(db)
    ui        = UIConnector()

    cfg = TurnConfig(
        max_tokens    = args.max_tokens,
        temperature   = args.temp,
        timeout       = args.timeout,
        skip_analysis = args.skip_analysis,
        no_retrieval  = args.no_retrieval,
    )

    print(f"  event log    : {ctx._log}")
    print(f"  memory       : L1/L2/L3 in {ctx._mem_dir}")
    print(f"  retrieval DB : {db._con.execute('PRAGMA database_list').fetchone()[2]}")
    print(f"  mode         : {'single-pass' if args.skip_analysis else 'analysis → retrieval → respond'}")
    if args.audio_query:
        print("  audio-query  : ON — speech triggers full turns automatically")
    print("  Type /help for commands.\n")

    on_proactive = _make_proactive_trigger(ctx, retrieval, cfg, live_fn=live_q.put)

    _start_stdin_reader(input_q)

    with tempfile.TemporaryDirectory(prefix="lawrence-") as tmp_str:
        tmp = Path(tmp_str)

        vision: VisionObserver | None = None
        audio:  AudioObserver  | None = None
        _hi_idx = [0]

        def capture_fn() -> Path | None:
            """Capture a hi-res frame on model request via current vision observer."""
            vi = vision_ref[0]
            if vi is None:
                return None
            _hi_idx[0] += 1
            return vi.pull_hires(tmp / f"model-hi-{_hi_idx[0]}.png")

        # ── observer lifecycle (single source of truth for start/stop) ────────────
        def _start_vision() -> bool:
            """Start the vision observer. Returns False if already running."""
            nonlocal vision
            if vision is not None:
                return False
            vision = VisionObserver(tmp, ctx, on_event=on_proactive)
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
            """Start the audio observer. Returns False if already running."""
            nonlocal audio
            if audio is not None:
                return False
            on_query = (
                _make_audio_query_handler(
                    ctx, retrieval, cfg, ui, response_q, control_q,
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
            """Apply sensor control signals emitted by the model in its response JSON."""
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
                # ── rolling live events (sensor, proactive, memory) ───────────────────
                while not live_q.empty():
                    try:
                        msg = live_q.get_nowait()
                        sys.stdout.write(f"\r  ▸ {msg}\nyou> ")
                        sys.stdout.flush()
                    except queue.Empty:
                        break

                # ── model-emitted controls from background turns ──────────────────────
                while not control_q.empty():
                    try:
                        _apply_controls(control_q.get_nowait())
                    except queue.Empty:
                        break

                # ── background responses (audio-triggered turns) ──────────────────────
                while not response_q.empty():
                    try:
                        msg = response_q.get_nowait()
                        sys.stdout.write(f"\r{msg}\nyou> ")
                        sys.stdout.flush()
                    except queue.Empty:
                        break

                # ── poll for user input (non-blocking, 150ms timeout) ─────────────────
                try:
                    raw = input_q.get(timeout=0.15)
                except queue.Empty:
                    continue

                if raw is None:   # EOF
                    print()
                    break

                idx += 1
                user_text, images, audios, action = _parse(raw, tmp, idx)

                if action == "exit":
                    break
                if action == "clear":
                    ctx.clear_rolling()
                    print("[rolling context cleared — L1, L2, L3 wiped]")
                elif action == "help":
                    _print_help()
                elif action == "status":
                    _print_status(vision, audio, ctx, args.audio_query)
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
                    print("[vision on]" if _start_vision() else "[vision already on]")
                elif action == "vision_off":
                    print("[vision off]" if _stop_vision() else "[vision already off]")
                elif action == "audio_on":
                    print("[audio on]" if _start_audio() else "[audio already on]")
                elif action == "audio_off":
                    print("[audio off]" if _stop_audio() else "[audio already off]")
                elif action == "toggle_retrieval":
                    cfg.no_retrieval = not cfg.no_retrieval
                    print(f"[retrieval {'OFF' if cfg.no_retrieval else 'ON'}]")

                if not user_text:
                    sys.stdout.write("\nyou> ")
                    sys.stdout.flush()
                    continue

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
                        ctx=ctx, retrieval=retrieval,
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
            if vision: vision.stop()
            if audio:  audio.stop()
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
