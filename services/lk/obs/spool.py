"""Decoupled sensor I/O — lets capture+preprocess run as a separate process.

The observers (vision.py, audio.py) only call `ctx.append(ts, kind, compact,
detailed)` on their sink, so the sink is duck-typed. SpoolWriter is a sink that,
instead of writing to the rolling store, drops one JSON file per event into a
spool directory. An external sensor process (`python3 lk_sensor.py`) uses it so
screen/audio capture can run on the host while the kernel runs elsewhere — e.g.
in a headless Docker container — over a shared `memory/spool/` volume.

SpoolReader runs inside the kernel: it drains the spool directory, feeding each
event into the real ContextStore and firing the proactive trigger, so out-of-
process events are ingested exactly as if a local observer had produced them.

Writes are atomic (write `.tmp`, then rename) so the reader never sees a partial
file. The single-writer invariant on the rolling store is preserved: only the
kernel writes the store; the external sensor only writes the spool.
"""
from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path


class SpoolWriter:
    """ContextStore-compatible sink that publishes events as JSON spool files."""

    def __init__(self, spool_dir: Path) -> None:
        self._dir = Path(spool_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._n = 0

    def append(self, ts: str, kind: str, compact: str, detailed: str) -> None:
        self._n += 1
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        name  = f"{stamp}-{os.getpid()}-{self._n:06d}.json"
        payload = {"ts": ts, "kind": kind, "compact": compact, "detailed": detailed}
        tmp = self._dir / (name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.rename(self._dir / name)   # atomic publish — reader only sees *.json


class SpoolReader(threading.Thread):
    """Daemon thread: drains a spool dir into a ContextStore, firing on_event."""
    daemon = True

    def __init__(
        self,
        spool_dir: Path,
        ctx,                                   # ContextStore (duck-typed: .append)
        on_event: Callable[[str, str], None] | None = None,
        poll: float = 2.0,
    ) -> None:
        super().__init__(name="spool-reader")
        self._dir      = Path(spool_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ctx      = ctx
        self._on_event = on_event
        self._poll     = poll
        self._stop     = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._drain()
            except Exception:
                pass
            self._stop.wait(self._poll)

    def _drain(self) -> None:
        for p in sorted(self._dir.glob("*.json")):
            try:
                ev = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                p.unlink(missing_ok=True)      # drop a corrupt/partial file
                continue
            try:
                self._ctx.append(
                    ts=ev["ts"], kind=ev["kind"],
                    compact=ev["compact"], detailed=ev["detailed"],
                )
                if self._on_event:
                    self._on_event(ev["kind"], ev["compact"])
            finally:
                p.unlink(missing_ok=True)
