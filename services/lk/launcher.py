"""lk launcher — the one screen you open first.

The launcher is the *gateway*: a tiny, instant, stdlib-only console menu to set
up, start, configure, inspect and stop LAWRENCE without remembering any command.
It is deliberately separate from the kernel, the llama-server, the chat REPL and
the desktop popup — it only *drives* them, by shelling out to the very same
`lk` front-door commands the CLI exposes. So everything the menu can do, you can
also type as `lk <command>`; there is no launcher-only behaviour.

Design goals: launches in milliseconds with nothing running, needs no build and
no extra dependency, works over SSH/WSL/any terminal, and always returns you to
the menu (every action runs as a subprocess). An inbuilt shell drops you to a
terminal in the repo and comes back.

Open it with a bare `./lk` (in a terminal) or `lk launcher`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
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
    return subprocess.call([sys.executable, str(FRONT), *args])


def _pause() -> None:
    try:
        input(_c("2", "\n  ↵ enter to return to the menu "))
    except (EOFError, KeyboardInterrupt):
        pass


# ── live status header ─────────────────────────────────────────────────────────

def _status_block() -> str:
    """A compact, honest snapshot — reuses ctl's lightweight probes (no kernel)."""
    from . import ctl
    from . import config as C

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


# ── menu actions ───────────────────────────────────────────────────────────────

def _act_presets() -> None:
    from . import config as C
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


# (key, label, callable). Callables either run a front-door command or a local action.
def _menu() -> list[tuple[str, str, object]]:
    return [
        ("1", "Start         — bridge + model + popup",      lambda: _run_front("start")),
        ("2", "Open popup    — show/focus the UI",           lambda: _run_front("ui")),
        ("3", "Stop          — leave the model warm",        lambda: _run_front("stop")),
        ("4", "Stop all      — also stop the model server",  lambda: _run_front("stop", "--all")),
        ("b", "Rebuild popup — recompile the Tauri binary",  lambda: _run_front("rebuild")),
        ("x", "Force reset   — clean slate from any wedged state", lambda: _run_front("reset", "--all")),
        ("r", "Chat (REPL)   — talk to it in this terminal", lambda: _run_front("repl")),
        ("w", "Setup wizard  — first-run detect & write config", lambda: _run_front("wizard")),
        ("p", "Presets       — backend / routing in one pick", _act_presets),
        ("k", "API keys      — store a provider key (0600)",  lambda: _run_front("secrets", "list")),
        ("c", "Config        — show/edit preferences",        lambda: _run_front("config", "list")),
        ("g", "Ingest        — add a doc/URL to the KB",      _act_ingest),
        ("n", "Notes         — browse the zettelkasten",      _act_notes),
        ("d", "Doctor        — diagnose deps & pipelines",    lambda: _run_front("doctor")),
        ("l", "Logs          — tail bridge/popup/server",     lambda: _run_front("logs")),
        ("t", "Terminal      — drop into a shell here",       _act_shell),
        (":", "Run lk …      — type any lk command",          _act_command),
    ]


def run() -> int:
    """The menu loop. Returns an exit code (0)."""
    if not _TTY:
        # Non-interactive (piped/cron): the launcher makes no sense — show status.
        return _run_front("status")

    menu = _menu()
    actions = {key: fn for key, _, fn in menu}
    while True:
        _clear()
        print(_c("1;36", "  L A W R E N C E") + _c("2", "   launcher · gateway"))
        print(_c("2", "  ─────────────────────────────────────────────"))
        print(_status_block())
        print(_c("2", "  ─────────────────────────────────────────────"))
        for key, label, _ in menu:
            print(f"   {_c('1;33', key)}  {label}")
        print(f"   {_c('1;33', 'q')}  Quit launcher (LAWRENCE keeps running)")
        try:
            choice = input(_c("1", "\n  > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice in ("q", "quit", "exit"):
            return 0
        fn = actions.get(choice)
        if fn is None:
            continue
        try:
            fn()
            # front-door commands already printed; give a beat unless they paused.
            if choice in {"1", "2", "3", "4", "b", "x", "w", "k", "c", "d", "l"}:
                _pause()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    raise SystemExit(run())
