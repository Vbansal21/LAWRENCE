"""Structured ``[debug]`` logging for the long-running services (stdlib-only).

One mechanism for every service (bridge, kernel turn, proactive, observers,
notify, schedule). OFF by default; enabled with ``LK_DEBUG`` (``1``/``true``/a
level name). Each record is a single line:

    [debug] +<uptime>s <service>: <event> key=value key=value ...

so the launcher's read-only consoles and ``lk logs`` surface live internals
without a logging framework. Never raises — a debug call must never break the
service that emits it. Routes to stderr and, when ``LK_DEBUG_FILE`` is set, also
appends there (best-effort, single shared lock so lines never interleave).

Counters: ``bump(service, name)`` keeps cheap in-process tallies (e.g. how many
notifications were throttled) that ``snapshot()`` exposes to /metrics + tests —
these are collected even when text logging is OFF, so they are always truthful.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from collections import defaultdict

_LOCK = threading.Lock()
_START = time.monotonic()
_COUNTERS: dict[str, int] = defaultdict(int)


def _truthy(value: str) -> bool:
    return value.strip().lower() not in ("", "0", "false", "off", "no")


_ENABLED = _truthy(os.environ.get("LK_DEBUG", ""))
_FILE = os.environ.get("LK_DEBUG_FILE", "").strip() or None


def enabled() -> bool:
    """True when text debug logging is on (counters are always collected)."""
    return _ENABLED


def set_enabled(on: bool) -> None:
    """Toggle text logging at runtime (the bridge wires this to a control)."""
    global _ENABLED
    _ENABLED = bool(on)


def _fmt(value: object) -> str:
    s = str(value).replace("\n", "⏎").replace("\r", "")
    return s if len(s) <= 100 else s[:97] + "..."


def debug(service: str, event: str, **fields: object) -> None:
    """Emit one structured debug record. No-op (besides cost ~0) when disabled."""
    if not _ENABLED:
        return
    try:
        line = f"[debug] +{time.monotonic() - _START:8.3f}s {service}: {event}"
        if fields:
            line += " " + " ".join(f"{k}={_fmt(v)}" for k, v in fields.items())
        with _LOCK:
            sys.stderr.write(line + "\n")
            sys.stderr.flush()
            if _FILE:
                with open(_FILE, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
    except Exception:
        pass


def bump(service: str, name: str, n: int = 1) -> None:
    """Increment a truthful in-process counter (collected even when logging off)."""
    try:
        with _LOCK:
            _COUNTERS[f"{service}.{name}"] += n
    except Exception:
        pass


def snapshot() -> dict[str, int]:
    """A copy of the counters (for /metrics + tests)."""
    with _LOCK:
        return dict(_COUNTERS)


def reset() -> None:
    """Clear counters (tests)."""
    with _LOCK:
        _COUNTERS.clear()
