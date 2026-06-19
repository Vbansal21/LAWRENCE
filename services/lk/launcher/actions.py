"""The launcher action registry — the single source both surfaces render from.

Every launcher action (the Qt GUI and the stdlib console) is one `Action` record
here: its label, the `lk` front-door argv (or a local interactive handler key),
the IA tier it belongs to, and its group. The admission gate — which actions may
run when, plus the double-click / cooldown protection — lives here too, so both
surfaces share one policy instead of duplicating it.

Imports stay stdlib-cheap: the live probes (`/health`, job counts, lock paths)
are pulled from `lk.ctl` *lazily* inside the gate functions, so importing this
module never triggers a circular import and never drags Qt or HTTP onto the
fast control path. `lk.ctl` re-exports `launcher_action_kind`,
`launcher_action_is_inspect`, `launcher_action_can_preempt` and
`claim_launcher_action` from here for back-compat.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass


# ── action records ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Action:
    """One launcher action, rendered by both the Qt GUI and the console.

    `argv` runs the matching `lk` front-door command through the gate; an empty
    `argv` with a `handler` key is a local interactive flow (prompts, an editor,
    a sub-shell) owned by each surface. `tier` is the IA placement (1 front view,
    2 dropdown child of a front control, 3 advanced tab, 4 terminal-only).
    """
    id: str
    label: str
    short: str = ""
    argv: tuple[str, ...] = ()
    handler: str = ""        # local interactive handler key, when there is no argv
    tier: int = 3            # 1 front · 2 dropdown child · 3 advanced tab · 4 terminal
    group: str = "tools"     # lifecycle · config · knowledge · diag · shell
    parent: str = ""         # id of the tier-1 control this drops down from (tier 2)
    needs_input: bool = False
    confirm: bool = False
    hint: str = ""


REGISTRY: tuple[Action, ...] = (
    # ── lifecycle (front view + dropdowns) ──────────────────────────────────
    Action("start", "Start         — bridge + model + popup", "Start",
           argv=("start",), tier=1, group="lifecycle",
           hint="bring up bridge, model server and popup"),
    Action("ui", "Open popup    — show/focus the UI", "Open",
           argv=("ui",), tier=1, group="lifecycle",
           hint="show or raise the desktop popup"),
    Action("stop", "Stop          — leave the model warm", "Stop",
           argv=("stop",), tier=1, group="lifecycle",
           hint="stop popup+bridge, keep the model warm"),
    Action("restart", "Restart       — stop then start", "Restart",
           argv=("restart",), tier=1, group="lifecycle",
           hint="stop then start"),
    Action("stop_all", "Stop all      — also stop the model server", "Stop all",
           argv=("stop", "--all"), tier=2, group="lifecycle", parent="stop",
           hint="stop popup+bridge and the llama-server"),
    Action("reset", "Force reset   — clean slate from any wedged state", "Force reset",
           argv=("reset", "--all"), tier=2, group="lifecycle", parent="stop",
           confirm=True, hint="kill everything and clear wedged locks"),
    Action("rebuild", "Rebuild popup — recompile the Tauri binary", "Rebuild",
           argv=("rebuild",), tier=2, group="lifecycle", parent="ui",
           confirm=True, hint="compile only; start or restart nothing"),
    Action("processes", "Processes     — list launcher-managed PIDs", "Processes",
           argv=("processes",), tier=2, group="lifecycle", parent="restart",
           hint="list managed PIDs"),
    Action("quit", "Quit          — close this launcher (services keep running)", "Quit",
           handler="quit", tier=1, group="lifecycle",
           hint="close the launcher window; bridge/model/popup keep running"),
    Action("quit_all", "Quit all      — full stop: every LAWRENCE process", "Quit all",
           handler="quit_all", tier=2, group="lifecycle", parent="quit", confirm=True,
           hint="terminate every LAWRENCE process incl. this launcher, then verify"),

    # ── config (advanced tab) ───────────────────────────────────────────────
    Action("wizard", "Setup wizard  — first-run detect & write config", "Wizard",
           argv=("wizard",), tier=3, group="config",
           hint="detect everything and write lk.json"),
    Action("presets", "Presets       — backend / routing in one pick", "Presets",
           handler="presets", tier=3, group="config", needs_input=True,
           hint="apply a backend+routing preset"),
    Action("keys", "API keys      — list or store provider keys", "API keys",
           handler="key", tier=3, group="config", needs_input=True,
           hint="store a provider key (hidden), or list names"),
    Action("config", "Config        — show/edit preferences", "Config",
           argv=("config", "list"), tier=3, group="config",
           hint="show lk.json preferences"),

    # ── knowledge (advanced tab) ────────────────────────────────────────────
    Action("ingest", "Ingest        — add a doc/URL to the KB", "Ingest",
           handler="ingest", tier=3, group="knowledge", needs_input=True,
           hint="add a document or URL to the knowledge base"),
    Action("memory", "Memory        — stats/backup/clear", "Memory",
           handler="memory", tier=3, group="knowledge", needs_input=True,
           hint="inspect / back up / clear memory"),
    Action("notes", "Notes         — browse the zettelkasten", "Notes",
           handler="notes", tier=3, group="knowledge", needs_input=True,
           hint="browse the zettelkasten"),
    Action("chats", "Chats         — list/show/export transcripts", "Chats",
           handler="chats", tier=3, group="knowledge", needs_input=True,
           hint="manage chat transcripts"),
    Action("links", "Links         — cross-chat reference graph", "Links",
           handler="links", tier=3, group="knowledge", needs_input=True,
           hint="cross-chat reference graph"),
    Action("remind", "Reminders     — durable, fire-once", "Reminders",
           handler="remind", tier=3, group="knowledge", needs_input=True,
           hint="durable reminders (list / add / done / rm)"),

    # ── diagnostics (advanced tab) ──────────────────────────────────────────
    Action("doctor", "Doctor        — diagnose deps & pipelines", "Doctor",
           argv=("doctor",), tier=3, group="diag",
           hint="dependency + pipeline diagnosis"),
    Action("logs", "Logs          — tail bridge/popup/server", "Logs",
           argv=("logs",), tier=3, group="diag",
           hint="tail bridge / popup / server logs"),

    # ── shell / terminal (tier 4) ───────────────────────────────────────────
    Action("repl", "Chat (REPL)   — talk to it in this terminal", "Chat",
           argv=("repl",), tier=4, group="shell",
           hint="terminal chat REPL"),
    Action("shell", "Terminal      — drop into a shell here", "Terminal",
           handler="shell", tier=4, group="shell",
           hint="a shell in the repo with lk on PATH"),
    Action("command", "Run lk …      — type any lk command", "Run lk…",
           handler="command", tier=4, group="shell", needs_input=True,
           hint="run an arbitrary lk command"),
)

_BY_ID = {a.id: a for a in REGISTRY}


def get(action_id: str) -> Action | None:
    return _BY_ID.get(action_id)


def all_actions() -> tuple[Action, ...]:
    return REGISTRY


def by_tier(tier: int) -> list[Action]:
    return [a for a in REGISTRY if a.tier == tier]


def by_group(group: str) -> list[Action]:
    return [a for a in REGISTRY if a.group == group]


def dropdown_children(parent_id: str) -> list[Action]:
    return [a for a in REGISTRY if a.parent == parent_id]


# ── classification (pure) ─────────────────────────────────────────────────────

def action_kind(args: list[str] | tuple[str, ...]) -> str:
    cmd = args[0] if args else ""
    if cmd in ("status", "processes", "ps", "logs", "doctor"):
        return "inspect"
    if cmd == "ui":
        return "open"
    if cmd == "stop":
        return "stop-all" if "--all" in args else "stop"
    if cmd in ("start", "restart", "rebuild", "reset", "wizard", "ingest"):
        return cmd
    if cmd in ("config", "secrets", "preset", "memory", "mem", "notes", "chats", "links", "remind"):
        return "tool"
    return "custom"


def is_inspect(kind: str) -> bool:
    return kind == "inspect"


def can_preempt(kind: str) -> bool:
    return kind in {"stop", "stop-all", "reset"}


# ── admission gate (lazy ctl probes) ──────────────────────────────────────────

def _state_read() -> dict:
    from .. import ctl
    try:
        return json.loads(ctl.LAUNCHER_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"last": {}}


def _state_write(state: dict) -> None:
    from .. import ctl
    ctl.LAUNCHER_STATE.parent.mkdir(parents=True, exist_ok=True)
    ctl.LAUNCHER_STATE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _project_process_busy() -> str:
    """Coarse reason when a project build/lifecycle command is already active."""
    from .. import ctl
    try:
        out = subprocess.run(["ps", "-eo", "pid=,args="],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return ""
    root = str(ctl.REPO_ROOT)
    for line in out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid, cmd = int(parts[0]), parts[1]
        if pid == os.getpid() or root not in cmd:
            continue
        if "desktopctl.sh" in cmd and any(a in cmd for a in (" build", " rebuild")):
            return "desktop build is already running"
        if any(token in cmd for token in ("npm run build", "tauri build", "cargo build")):
            return "desktop build is already running"
        if "desktopctl.sh" in cmd and any(a in cmd for a in (" start", " stop", " reset", " restart", " show")):
            return "desktop lifecycle command is already running"
    return ""


def block(args: list[str], state: dict) -> str:
    """Return a refusal reason if this action must not run right now, else ''."""
    from .. import ctl
    kind = action_kind(args)
    busy = _project_process_busy()
    if busy and kind in {"start", "open", "restart", "rebuild", "wizard", "custom"}:
        return f"{busy}; skipped {kind}"

    health = ctl._get_json(f"http://127.0.0.1:{ctl.UI_PORT}/health", timeout=0.8)
    model_loading = bool(health) and not bool(health.get("modelHealth"))
    if model_loading and kind in {"start", "restart", "rebuild"}:
        return "bridge/model is still loading; wait, Stop all, or Force reset"

    if kind in {"restart", "rebuild"}:
        active, _jobs = ctl.active_jobs()
        if active:
            return f"active work is running ({active} queued/running job(s)); stop/reset first"

    cooldowns = {
        # Codex: launcher buttons are not queued. These per-action cooldowns
        # absorb double-clicks while live state checks handle long build/load work.
        "open": 0.8,
        "start": 2.0,
        "restart": 3.0,
        "rebuild": 8.0,
        "wizard": 2.0,
        "ingest": 1.0,
        "tool": 0.5,
        "custom": 1.5,
    }
    wait = cooldowns.get(kind, 0.0)
    last = float((state.get("last") or {}).get(kind) or 0)
    remaining = wait - (time.time() - last)
    if remaining > 0:
        return f"{kind} was just requested; try again in {remaining:.1f}s"
    return ""


def claim(args: list[str]) -> tuple[bool, str, str]:
    """Shared GUI/console admission check. It rejects, never queues, unsafe repeats."""
    args = list(args)
    kind = action_kind(args)
    if is_inspect(kind):
        return True, kind, ""
    from .. import ctl
    try:
        import fcntl
        ctl.LAUNCHER_LOCK.parent.mkdir(parents=True, exist_ok=True)
        with open(ctl.LAUNCHER_LOCK, "a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = _state_read()
            reason = block(args, state)
            if reason:
                return False, kind, reason
            state.setdefault("last", {})[kind] = time.time()
            _state_write(state)
            return True, kind, ""
    except Exception:
        state = _state_read()
        reason = block(args, state)
        if reason:
            return False, kind, reason
        state.setdefault("last", {})[kind] = time.time()
        _state_write(state)
        return True, kind, ""
