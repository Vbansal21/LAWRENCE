"""lk launcher — one action registry, two surfaces.

The launcher is the gateway you open first. Everything it can do is also a plain
`lk <command>`; the launcher only *drives* the kernel, model server, REPL and
desktop popup, it never owns them. Two surfaces render the SAME action registry
(`lk.launcher.actions`):

  • a native Qt window (PySide6 + pyte) when a display is present, and
  • a stdlib console menu fallback over SSH / WSL / any terminal.

Imports here stay lazy so `lk status` (the fast control path in `lk.ctl`) never
pulls in Qt. `run()` is the console gateway; the Qt window is dispatched
separately by `lk.ctl.cmd_launcher`.
"""
from __future__ import annotations


def run(argv: list[str] | None = None) -> int:
    """Open the stdlib console gateway (the no-display / fallback surface)."""
    from .console import run as _run
    return _run()
