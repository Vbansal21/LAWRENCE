"""LAWRENCE sensor agent — runs capture + preprocessing out-of-process.

Runs the vision/audio observers and writes gated, distilled events to a spool
directory instead of straight into the kernel's memory. A kernel running
elsewhere (e.g. headless in Docker) ingests them with `--ingest-spool`. This
keeps vision/audio support when the kernel itself has no screen or microphone:
run this agent on the host (or a host-privileged container), share the spool
directory as a volume, and the kernel consumes the events.

No model, no llama-server — this is pure preprocessing (capture → OCR/transcribe
→ significance gate → distill). The same heuristics and live-tunable thresholds
as the in-process observers apply (see obs/vision.py, obs/audio.py, ctx/gate.py).

Usage:
    python3 lk_sensor.py --spool memory/spool
    python3 lk_sensor.py --spool /shared/spool --no-audio --vision-interval 5

On the kernel side:
    python3 lk.py --no-vision --no-audio --ingest-spool memory/spool
"""
from __future__ import annotations

import argparse
import signal
import sys
import tempfile
import threading
from pathlib import Path

from .obs import VisionObserver, AudioObserver, SpoolWriter


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="LAWRENCE out-of-process sensor agent")
    p.add_argument("--spool", default="memory/spool",
                   help="spool directory to publish events into (default: memory/spool)")
    p.add_argument("--no-vision", action="store_true", help="disable the screen observer")
    p.add_argument("--no-audio",  action="store_true", help="disable the audio observer")
    p.add_argument("--vision-interval", type=float, default=None,
                   help="screen poll seconds (default: observer default)")
    p.add_argument("--vision-write-min", type=int, default=None,
                   help="min seconds between screen writes (default: observer default)")
    return p.parse_args()


def main() -> int:
    args = _args()
    spool = Path(args.spool).expanduser().resolve()
    sink  = SpoolWriter(spool)
    tmp   = Path(tempfile.mkdtemp(prefix="lk-sensor-"))

    print("\nLAWRENCE sensor agent")
    print(f"  spool : {spool}")

    observers: list[object] = []
    if not args.no_vision:
        kw = {}
        if args.vision_interval  is not None: kw["poll_interval"]  = args.vision_interval
        if args.vision_write_min is not None: kw["min_write_secs"] = args.vision_write_min
        v = VisionObserver(tmp, sink, **kw)   # sink is duck-typed as the store
        v.start()
        observers.append(v)
        print("  vision: ON")
    if not args.no_audio:
        a = AudioObserver(tmp, sink)
        a.start()
        observers.append(a)
        print("  audio : ON")

    if not observers:
        print("  nothing to run — both sensors disabled", file=sys.stderr)
        return 1

    print("  running — Ctrl-C to stop\n")
    stop = threading.Event()
    signal.signal(signal.SIGINT,  lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    while not stop.is_set():
        stop.wait(1.0)

    for o in observers:
        o.stop()  # type: ignore[attr-defined]
    print("\n  sensor stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
