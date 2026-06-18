"""lk launcher — the stdlib console gateway (no-display / fallback surface).

A tiny, instant, stdlib-only menu to set up, start, configure, inspect and stop
LAWRENCE without remembering any command. It is deliberately separate from the
kernel, the llama-server, the chat REPL and the desktop popup — it only *drives*
them, by shelling out to the very same `lk` front-door commands the CLI exposes.
So everything the menu can do, you can also type as `lk <command>`; there is no
launcher-only behaviour.

The menu rows, their labels and their `lk` argv all come from the shared action
registry (`lk.launcher.actions`), so the Qt window and this console stay in sync.
Local interactive flows (presets, keys, ingest, memory, notes, an inbuilt shell,
free-form `lk`) are handled here.

Open it with a bare `./lk` (in a terminal) or `lk launcher --tui`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import actions

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONT = REPO_ROOT / "lk"          # the front-door script (this dispatches to ctl)

# ── small terminal helpers (no curses — bulletproof everywhere) ────────────────

_TTY = sys.stdin.isatty() and sys.stdout.isatty()
_COLOR = _TTY and os.environ.get("NO_COLOR") is None


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


def _clear() -> None:
    if _TTY:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def _run_front(*args: str) -> int:
    """Run a front-door command as a child so we always return to the menu."""
    ok, _kind, reason = actions.claim(list(args))
    if not ok:
        # Codex: TUI uses the same no-queue launcher gate as the GUI, so rapid
        # command entry gets a clear refusal instead of overlapping subprocesses.
        print(_c("33", f"  skipped: {reason}"))
        return 1
    return subprocess.call([sys.executable, str(FRONT), *args])


def _pause() -> None:
    try:
        input(_c("2", "\n  ↵ enter to return to the menu "))
    except (EOFError, KeyboardInterrupt):
        pass


# ── live status header ─────────────────────────────────────────────────────────

def _status_block() -> str:
    """A compact, honest snapshot — reuses ctl's lightweight probes (no kernel)."""
    from .. import ctl
    from .. import config as C

    lines: list[str] = []
    owner = ctl._lock_owner()
    if owner:
        lines.append(_c("32", f"  kernel   ● {owner.get('role','?')} (pid {owner.get('pid','?')})"))
    else:
        lines.append(_c("90", "  kernel   ○ stopped"))

    health = ctl._get_json(f"http://127.0.0.1:{ctl.UI_PORT}/health")
    if health:
        model = "ready" if health.get("modelHealth") else "NOT READY"
        lines.append(_c("32", f"  bridge   ● :{ctl.UI_PORT}  backend={health.get('backend','?')}  model={model}"))
        obs = health.get("observers", {})
        lines.append(f"  sensors    vision={'on' if obs.get('vision') else 'off'}"
                     f"  audio={'on' if obs.get('audio') else 'off'}")
    else:
        warm = ctl._http_ok(f"http://127.0.0.1:{ctl.LLAMA_PORT}/health")
        lines.append(_c("90", f"  bridge   ○ stopped" + ("   (model warm on :8190)" if warm else "")))

    cfg = C.configured_summary()
    routed = ",".join(sorted(set(cfg.get("routing", {}).values()))) or "—"
    keys = ", ".join(cfg.get("secrets", [])) or "none"
    lines.append(_c("36", f"  config     backend={cfg.get('backend','local')}  routes→{routed}  keys: {keys}"))
    return "\n".join(lines)


# ── local interactive handlers (no fixed argv) ─────────────────────────────────

def _act_presets() -> None:
    from .. import config as C
    _clear()
    print(_c("1", "  Presets — pick a backend/routing setup\n"))
    names = list(C.PRESETS)
    for i, name in enumerate(names, 1):
        p = C.PRESETS[name]
        print(f"   {i}. {_c('36', name):<24} {p['label']}")
    print("   0. back")
    choice = input("\n  preset> ").strip()
    if choice in ("0", "", "q"):
        return
    try:
        name = names[int(choice) - 1]
    except (ValueError, IndexError):
        name = choice if choice in C.PRESETS else None
    if not name:
        print(_c("31", "  unknown preset")); _pause(); return
    cfg, missing = C.apply_preset(name)
    print(_c("32", f"\n  applied preset '{name}' → {C.CONFIG_PATH}"))
    if missing:
        print(_c("33", f"  needs an API key for: {', '.join(missing)}"))
        if input("  add a key now? [y/N] ").strip().lower() == "y":
            _run_front("secrets", "set", missing[0])
    print(_c("2", "  takes effect on the next Start."))
    _pause()


def _act_shell() -> None:
    _clear()
    print(_c("1", "  Inbuilt terminal") + _c("2", "  (repo: " + str(REPO_ROOT) + ")"))
    print(_c("2", "  `lk` is on this path. Type 'exit' to come back.\n"))
    env = dict(os.environ)
    env["PATH"] = f"{REPO_ROOT}{os.pathsep}{env.get('PATH','')}"
    shell = env.get("SHELL", "/bin/bash")
    subprocess.call([shell], cwd=str(REPO_ROOT), env=env)


def _act_command() -> None:
    cmd = input(_c("1", "  lk ") + "").strip()
    if not cmd:
        return
    _run_front(*cmd.split())
    _pause()


def _act_ingest() -> None:
    target = input("  path or URL to add to the knowledge base: ").strip()
    if target:
        _run_front("ingest", target)
    _pause()


def _act_notes() -> None:
    _clear()
    print(_c("1", "  Zettelkasten") + _c("2", "  list · show <id> · search <words>  (blank = list)"))
    q = input("\n  notes> ").strip()
    _run_front("notes", *(q.split() if q else ["list"]))
    _pause()


def _act_memory() -> None:
    _clear()
    print(_c("1", "  Memory") + _c("2", "  stats · backup · clear-cache · clear-rolling · clear-logs · clear-all"))
    q = input("\n  memory> ").strip()
    _run_front("memory", *(q.split() if q else ["stats"]))
    _pause()


def _act_key() -> None:
    provider = input("  provider (blank = list): ").strip()
    if provider:
        _run_front("secrets", "set", provider)
    else:
        _run_front("secrets", "list")
    _pause()


def _act_quit_all() -> None:
    """N-28 Quit-all from the console: terminate every LAWRENCE process, verify."""
    from .. import ctl
    try:
        if input("  terminate ALL LAWRENCE processes (full stop)? [y/N] ").strip().lower() != "y":
            print("  cancelled")
            return
    except (EOFError, KeyboardInterrupt):
        print("\n  cancelled")
        return
    print("  stopping every LAWRENCE process…")
    survivors = ctl.quit_all()
    if survivors:
        print(_c("33", "  could not stop:"))
        print(ctl.format_processes(survivors))
    else:
        print(_c("32", "  all LAWRENCE processes stopped"))


# Local interactive handlers, keyed by Action.handler.
_HANDLERS = {
    "presets": _act_presets,
    "key": _act_key,
    "ingest": _act_ingest,
    "memory": _act_memory,
    "notes": _act_notes,
    "shell": _act_shell,
    "command": _act_command,
    "quit_all": _act_quit_all,
}

# The console menu: (hotkey, action id), in display order. Labels and argv come
# from the shared registry so the GUI and console never drift.
_CONSOLE_KEYS: list[tuple[str, str]] = [
    ("1", "start"), ("2", "ui"), ("3", "stop"), ("4", "stop_all"),
    ("5", "processes"), ("6", "restart"), ("b", "rebuild"), ("x", "reset"),
    ("Q", "quit_all"),
    ("r", "repl"), ("w", "wizard"), ("p", "presets"), ("k", "keys"),
    ("c", "config"), ("g", "ingest"), ("m", "memory"), ("n", "notes"),
    ("d", "doctor"), ("l", "logs"), ("t", "shell"), (":", "command"),
]
# Keys whose action prints and returns immediately (front-door commands): pause
# so the output is readable. Interactive handlers pause themselves.
_PAUSE_KEYS = {"1", "2", "3", "4", "5", "6", "b", "x", "w", "c", "d", "l"}


def _dispatch(action) -> None:
    if action.handler:
        fn = _HANDLERS.get(action.handler)
        if fn:
            fn()
    elif action.argv:
        _run_front(*action.argv)


def run() -> int:
    """The menu loop. Returns an exit code (0)."""
    if not _TTY:
        # Non-interactive (piped/cron): the launcher makes no sense — show status.
        return _run_front("status")

    menu = [(key, actions.get(aid)) for key, aid in _CONSOLE_KEYS]
    menu = [(key, a) for key, a in menu if a is not None]
    dispatch_map = {key: a for key, a in menu}
    while True:
        _clear()
        print(_c("1;36", "  L A W R E N C E") + _c("2", "   launcher · gateway"))
        print(_c("2", "  ─────────────────────────────────────────────"))
        print(_status_block())
        print(_c("2", "  ─────────────────────────────────────────────"))
        for key, a in menu:
            print(f"   {_c('1;33', key)}  {a.label}")
        print(f"   {_c('1;33', 'q')}  Quit launcher (LAWRENCE keeps running)")
        try:
            choice = input(_c("1", "\n  > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice in ("q", "quit", "exit"):
            return 0
        action = dispatch_map.get(choice)
        if action is None:
            continue
        try:
            _dispatch(action)
            # front-door commands already printed; give a beat unless they paused.
            if choice in _PAUSE_KEYS:
                _pause()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    raise SystemExit(run())
