"""lk — the LAWRENCE front door. Fast, stdlib-only, works before anything heavy.

This is the control CLI (plan P2): the interface you use *before* the model or
UI loads. It never imports the kernel — it inspects state over HTTP and the
writer-lock file, and delegates real work to the existing entry points:

    lk                  open the launcher (interactive gateway menu)
    lk launcher         the launcher menu — set up / start / config / stop
    lk preset use NAME  apply a backend+routing preset (local/hybrid/gemini/claude)
    lk start            bridge + llama-server + popup  (the normal way to run)
    lk restart [--all]  stop then start  (--all also restarts llama-server)
    lk rebuild          recompile the desktop popup (Tauri) and relaunch it
    lk reset [--all]    force a clean slate from any wedged state (--all: + server)
    lk stop [--all]     stop popup+bridge  (--all also stops llama-server)
    lk memory [...]     inspect/back up/clear memory (stats|clear-cache|clear-all)
    lk processes        list launcher-managed LAWRENCE processes
    lk notes [...]      browse the zettelkasten (list | show <id> | search <q>)
    lk chats [...]      manage chats (list | show | export | new | switch | rename | delete)
    lk links [...]      cross-chat graph (show <chat> <seq> | add <c> <s> <c> <s>)
    lk status           who is running, who owns memory/, model health
    lk repl [flags...]  the terminal REPL (mutually exclusive with the UI kernel)
    lk ui               popup only (bridge must be running / will be started)
    lk doctor           dependency + pipeline diagnosis (audio, retrieval, UI)
    lk logs             tail bridge / popup / server logs
    lk config ...       get/set .runtime/lk.json (see lk config list)
    lk wizard [--yes]   first-run setup: detect everything, write lk.json
    lk ingest PATH|URL  add a document/page to the local knowledge base

Module-level imports must stay stdlib-and-light so `lk status` answers in
milliseconds with nothing running.
"""
from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOPCTL = REPO_ROOT / "apps" / "desktop" / "scripts" / "desktopctl.sh"
LOCK_PATH = REPO_ROOT / "memory" / ".writer.lock"
SERVER_LOG = REPO_ROOT / ".runtime" / "lk-server.log"
LAUNCHER_STATE = REPO_ROOT / ".runtime" / "launcher-actions.json"
LAUNCHER_LOCK = REPO_ROOT / ".runtime" / "launcher-actions.lock"

UI_PORT = int(os.environ.get("LK_UI_PORT", "8765"))
LLAMA_PORT = 8190


# ── tiny helpers ──────────────────────────────────────────────────────────────

def _get_json(url: str, timeout: float = 1.5) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _lock_owner() -> dict | None:
    """Who holds the memory/ writer lock right now (None if nobody)."""
    try:
        import fcntl
        f = open(LOCK_PATH, "a+", encoding="utf-8")
    except (OSError, ImportError):
        return None
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)        # free → nobody owns it
        return None
    except OSError:
        f.seek(0)
        try:
            return json.loads(f.read().strip() or "{}")
        except json.JSONDecodeError:
            return {"role": "unknown"}
    finally:
        f.close()


def _desktopctl(*args: str) -> int:
    if not DESKTOPCTL.exists():
        print(f"  missing: {DESKTOPCTL}", file=sys.stderr)
        return 1
    return subprocess.call(["bash", str(DESKTOPCTL), *args])


def _node_ready() -> bool:
    return (REPO_ROOT / "apps" / "desktop" / "node_modules").is_dir()


def _label_linux_process(cmd: str) -> str:
    root = str(REPO_ROOT)
    if "scripts/ui_bridge.py" in cmd:
        return "bridge"
    if "lawrence-desktop" in cmd and "target/release" in cmd:
        return "popup"
    if "llama-server" in cmd and "--port" in cmd and str(LLAMA_PORT) in cmd:
        return "model"
    if f"{root}/lk.py" in cmd:
        return "repl"
    if "services/lk/sensor.py" in cmd or "lk_sensor.py" in cmd:
        return "sensor"
    if f"{root}/lk launcher --gui" in cmd or " lk launcher --gui" in cmd:
        return "launcher"
    if any(name in cmd for name in ("dev-tauri.sh", "web-preview.sh", "stress-ui.sh")):
        return "desktop-dev"
    return ""


def _windows_hotkey_processes() -> list[dict]:
    if not shutil.which("powershell.exe"):
        return []
    query = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "$_.ProcessId -ne $PID -and ("
        "$_.CommandLine -match '(-File|/File)\\s+.*(GlobalHotkey|Register-Hotkey)\\.ps1' -or "
        "$_.Name -like 'lawrence-desktop*') "
        "} | ForEach-Object { \"$($_.ProcessId)`t$($_.Name)`t$($_.CommandLine)\" }"
    )
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", query],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return []
    rows: list[dict] = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        label = "popup" if "lawrence-desktop" in parts[1].lower() else "windows-hotkey"
        rows.append({"platform": "windows", "pid": int(parts[0]),
                     "label": label, "cmd": parts[2]})
    return rows


def managed_processes(*, include_launcher: bool = False) -> list[dict]:
    """Processes the launcher is allowed to stop. Keep patterns project-scoped."""
    # Codex: keep one launcher-owned inventory so Stop all, Force reset, and the
    # Processes view agree on which LAWRENCE processes are safe to terminate.
    rows: list[dict] = []
    try:
        out = subprocess.run(["ps", "-eo", "pid=,args="],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        out = ""
    for line in out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid, cmd = int(parts[0]), parts[1]
        if pid == os.getpid():
            continue
        label = _label_linux_process(cmd)
        if not label or (label == "launcher" and not include_launcher):
            continue
        rows.append({"platform": "linux", "pid": pid, "label": label, "cmd": cmd})
    rows.extend(_windows_hotkey_processes())
    rows.sort(key=lambda row: (row["label"], row["platform"], row["pid"]))
    return rows


def format_processes(rows: list[dict]) -> str:
    if not rows:
        return "  no launcher-managed LAWRENCE processes found"
    return "\n".join(
        f"  {row['label']:<13} {row['platform']:<7} pid={row['pid']}  {row['cmd'][:140]}"
        for row in rows
    )


def active_jobs() -> tuple[int, list[dict]]:
    health = _get_json(f"http://127.0.0.1:{UI_PORT}/health", timeout=0.8) or {}
    counts = health.get("jobs") or {}
    active = int(counts.get("queued") or 0) + int(counts.get("running") or 0)
    if active <= 0:
        return 0, []
    jobs = _get_json(f"http://127.0.0.1:{UI_PORT}/jobs", timeout=0.8) or {}
    items = [j for j in jobs.get("items", []) if j.get("state") in ("queued", "running")]
    return active, items[:5]


def _confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        return input(prompt + " [y/N] ").strip().lower() == "y"
    except (EOFError, KeyboardInterrupt):
        return False


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        # Codex: zombies are already stopped; treating them as alive made Stop
        # all ask for needless force-kill confirmations that cannot reap them.
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(errors="ignore").split()
            return len(stat) < 3 or stat[2] != "Z"
        except OSError:
            return True
    except OSError:
        return False


def _stop_windows_pid(pid: int) -> None:
    if shutil.which("powershell.exe"):
        subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)


def terminate_processes(rows: list[dict], *, force: bool = False) -> None:
    for row in rows:
        if row["platform"] == "windows":
            _stop_windows_pid(row["pid"])
            continue
        try:
            os.kill(row["pid"], signal.SIGTERM)
        except OSError:
            pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not any(row["platform"] == "linux" and _alive(row["pid"]) for row in rows):
            return
        time.sleep(0.2)
    if not force:
        return
    for row in rows:
        if row["platform"] == "linux" and _alive(row["pid"]):
            try:
                os.kill(row["pid"], signal.SIGKILL)
            except OSError:
                pass


# ── launcher action gate ─────────────────────────────────────────────────────

def launcher_action_kind(args: list[str]) -> str:
    cmd = args[0] if args else ""
    if cmd in ("status", "processes", "ps", "logs", "doctor"):
        return "inspect"
    if cmd == "ui":
        return "open"
    if cmd == "stop":
        return "stop-all" if "--all" in args else "stop"
    if cmd in ("start", "restart", "rebuild", "reset", "wizard", "ingest"):
        return cmd
    if cmd in ("config", "secrets", "preset", "memory", "mem", "notes", "chats", "links"):
        return "tool"
    return "custom"


def launcher_action_is_inspect(kind: str) -> bool:
    return kind == "inspect"


def launcher_action_can_preempt(kind: str) -> bool:
    return kind in {"stop", "stop-all", "reset"}


def _launcher_state() -> dict:
    try:
        return json.loads(LAUNCHER_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"last": {}}


def _save_launcher_state(state: dict) -> None:
    LAUNCHER_STATE.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHER_STATE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _project_process_busy() -> str:
    """Return a coarse reason when a project build/lifecycle command is active."""
    try:
        out = subprocess.run(["ps", "-eo", "pid=,args="],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return ""
    for line in out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid, cmd = int(parts[0]), parts[1]
        if pid == os.getpid() or str(REPO_ROOT) not in cmd:
            continue
        if "desktopctl.sh" in cmd and any(a in cmd for a in (" build", " rebuild")):
            return "desktop build is already running"
        if any(token in cmd for token in ("npm run build", "tauri build", "cargo build")):
            return "desktop build is already running"
        if "desktopctl.sh" in cmd and any(a in cmd for a in (" start", " stop", " reset", " restart", " show")):
            return "desktop lifecycle command is already running"
    return ""


def _launcher_action_block(args: list[str], state: dict) -> str:
    kind = launcher_action_kind(args)
    busy = _project_process_busy()
    if busy and kind in {"start", "open", "restart", "rebuild", "wizard", "custom"}:
        return f"{busy}; skipped {kind}"

    health = _get_json(f"http://127.0.0.1:{UI_PORT}/health", timeout=0.8)
    model_loading = bool(health) and not bool(health.get("modelHealth"))
    if model_loading and kind in {"start", "restart", "rebuild"}:
        return "bridge/model is still loading; wait, Stop all, or Force reset"

    if kind in {"restart", "rebuild"}:
        active, _jobs = active_jobs()
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


def claim_launcher_action(args: list[str]) -> tuple[bool, str, str]:
    """Shared GUI/TUI admission check. It rejects, never queues, unsafe repeats."""
    kind = launcher_action_kind(args)
    if launcher_action_is_inspect(kind):
        return True, kind, ""
    try:
        import fcntl
        LAUNCHER_LOCK.parent.mkdir(parents=True, exist_ok=True)
        with open(LAUNCHER_LOCK, "a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = _launcher_state()
            reason = _launcher_action_block(args, state)
            if reason:
                return False, kind, reason
            state.setdefault("last", {})[kind] = time.time()
            _save_launcher_state(state)
            return True, kind, ""
    except Exception:
        state = _launcher_state()
        reason = _launcher_action_block(args, state)
        if reason:
            return False, kind, reason
        state.setdefault("last", {})[kind] = time.time()
        _save_launcher_state(state)
        return True, kind, ""


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_status(_args: list[str]) -> int:
    owner = _lock_owner()
    if owner:
        print(f"  kernel    : {owner.get('role', '?')} (pid {owner.get('pid', '?')}) owns memory/")
    else:
        print("  kernel    : stopped (memory/ unlocked)")

    health = _get_json(f"http://127.0.0.1:{UI_PORT}/health")
    if health:
        print(f"  bridge    : healthy on :{UI_PORT}  backend={health.get('backend', '?')}")
        print(f"  model     : {'ready' if health.get('modelHealth') else 'NOT READY'}"
              f"  modalities={health.get('modalities', '?')}")
        obs = health.get("observers", {})
        print(f"  observers : vision={'on' if obs.get('vision') else 'off'}"
              f" audio={'on' if obs.get('audio') else 'off'}")
        retr = health.get("retrieval", {})
        cooling = retr.get("cooling_down") or []
        if cooling:
            print(f"  retrieval : cooling down: {', '.join(cooling)}")
        if health.get("eventsUrl"):
            print(f"  events    : {health['eventsUrl']}")
    else:
        print(f"  bridge    : stopped (:{UI_PORT})")
        print(f"  model     : {'server warm on :' + str(LLAMA_PORT) if _http_ok(f'http://127.0.0.1:{LLAMA_PORT}/health') else 'stopped'}")
    # popup state via desktopctl (cheap ps scan)
    try:
        out = subprocess.run(["bash", str(DESKTOPCTL), "status"],
                             capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if line.startswith(("popup:", "hotkey:")):
                print(f"  {line}")
    except Exception:
        pass
    return 0


def cmd_start(args: list[str]) -> int:
    """Default launch: bridge (spawns llama-server) + popup. One command."""
    if "--repl" in args:
        return cmd_repl([a for a in args if a != "--repl"])
    owner = _lock_owner()
    if owner and owner.get("role") == "repl":
        print(f"  a REPL kernel (pid {owner.get('pid')}) owns memory/ — exit it first"
              " (UI and REPL are mutually exclusive). `lk attach` to reach it.")
        return 1
    if not _node_ready():
        print("  first run: installing desktop dependencies (npm install)…")
        rc = subprocess.call(["npm", "install", "--no-fund", "--no-audit"],
                             cwd=REPO_ROOT / "apps" / "desktop")
        if rc != 0:
            print("  npm install failed — run `lk doctor` for the dependency report")
            return rc
    print("  starting bridge (loads the model — first start can take a minute)…")
    rc = _desktopctl("start")
    if rc == 0:
        print("\n  LAWRENCE is up. Summon/dismiss the popup with the hotkey above.")
        print("  `lk status` for health, `lk logs` if anything misbehaves.")
    else:
        print("\n  start failed — `lk logs` shows why (model path? GTK deps? run `lk doctor`)")
    return rc


def cmd_stop(args: list[str]) -> int:
    all_ = "--all" in args
    force = "--force" in args
    allow_active = force or "--allow-active" in args
    if all_:
        # Codex: Stop all checks active bridge jobs first; force termination is
        # only used after explicit confirmation or a caller-provided --force.
        n_active, jobs = active_jobs()
        if n_active and not allow_active:
            print(f"  active work: {n_active} queued/running job(s)")
            for job in jobs:
                print(f"    {job.get('id', '?')}  {job.get('state', '?')}  {job.get('textPreview', '')}")
            if not _confirm("  stop anyway and interrupt active work?"):
                print("  stop cancelled")
                return 1

    _desktopctl("stop")
    labels = {"popup", "bridge", "windows-hotkey"}
    if all_:
        labels.update({"model", "repl", "sensor", "desktop-dev"})
        model_rows = [row for row in managed_processes() if row["label"] == "model"]
        if model_rows:
            # `--all` is an explicit "stop everything". The model is STATELESS
            # (memory lives in the bridge/store), so SIGTERM-then-SIGKILL is safe
            # and means the user never has to manually force-kill a warm/orphaned
            # llama-server. The bridge now reaps the server it started on its own
            # shutdown; this stays as the backstop for an externally-owned or
            # pre-existing orphaned server.
            print("  llama-server: stopping")
            terminate_processes(model_rows, force=True)
        else:
            print("  llama-server: was not running")
    else:
        if _http_ok(f"http://127.0.0.1:{LLAMA_PORT}/health"):
            print("  llama-server left warm on :8190 (use `lk stop --all` to stop it too)")

    leftovers = [row for row in managed_processes() if row["label"] in labels]
    if leftovers:
        print("  still running:")
        print(format_processes(leftovers))
        if force or _confirm("  force terminate remaining LAWRENCE processes?"):
            terminate_processes(leftovers, force=True)
            leftovers = [row for row in managed_processes() if row["label"] in labels]
    if leftovers:
        print("  stop incomplete:")
        print(format_processes(leftovers))
        return 1
    print("  all requested LAWRENCE processes stopped")
    return 0


def cmd_processes(args: list[str]) -> int:
    print(format_processes(managed_processes(include_launcher="--with-launcher" in args)))
    return 0


def cmd_repl(args: list[str]) -> int:
    os.chdir(REPO_ROOT)
    os.execv(sys.executable, [sys.executable, str(REPO_ROOT / "lk.py"), *args])


def cmd_ui(_args: list[str]) -> int:
    return _desktopctl("show")


def cmd_attach(_args: list[str]) -> int:
    return subprocess.call(["tmux", "-S", "/tmp/lk-tmux", "attach", "-t", "lawrence"])


def cmd_logs(args: list[str]) -> int:
    rc = _desktopctl("logs")
    print("== llama-server ==")
    try:
        print("\n".join(SERVER_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]))
    except OSError:
        print("(no server log)")
    return rc


def cmd_doctor(_args: list[str]) -> int:
    print("== toolchain ==")
    for tool, hint in (
        ("node", "UI build (apt: nodejs/npm or nvm)"),
        ("cargo", "Tauri build (rustup.rs)"),
        ("tesseract", "vision OCR (apt: tesseract-ocr)"),
        ("ffmpeg", "audio capture (conda/apt: ffmpeg)"),
        ("arecord", "audio capture alt (apt: alsa-utils)"),
        ("pactl", "PulseAudio check (apt: pulseaudio-utils)"),
    ):
        path = shutil.which(tool)
        print(f"  {tool:<10} {'OK ' + path if path else 'MISSING — ' + hint}")
    for mod, extra in (("faster_whisper", "audio"), ("trafilatura", "web"),
                       ("PIL", "vision"), ("anthropic", "api")):
        try:
            __import__(mod)
            print(f"  {mod:<14} OK (python)")
        except ImportError:
            print(f"  {mod:<14} MISSING — pip install -e '.[{extra}]'")
    try:
        __import__("tkinter")
        print(f"  {'tkinter':<14} OK (GUI launcher)")
    except ImportError:
        print(f"  {'tkinter':<14} MISSING — GUI launcher falls back to console menu"
              " (apt: python3-tk)")
    bin_ = REPO_ROOT / "third_party/llama.cpp/build/bin/llama-server"
    print(f"  llama-server {'OK ' + str(bin_) if bin_.exists() else 'MISSING — build third_party/llama.cpp'}")
    models = list((REPO_ROOT / "models").rglob("*.gguf"))
    print(f"  model gguf   {'OK ' + models[0].name if models else 'MISSING — put a GGUF under models/local/'}")
    print("\n== pipelines ==")
    for script in ("diag-audio.sh", "diag-retrieval.sh"):
        p = REPO_ROOT / "scripts" / script
        if p.exists():
            print(f"-- {script} --")
            subprocess.call(["bash", str(p)])
    print("\n== desktop ==")
    return _desktopctl("doctor")


def cmd_secrets(args: list[str]) -> int:
    """API keys, stored 0600 in ~/.lawrence/secrets.env (never in git).

    You name the PROVIDER and paste the key — nothing else:
        lk secrets set gemini        # then paste the key when prompted (hidden)
        lk secrets set openai
        lk secrets set anthropic
    """
    sys.path.insert(0, str(REPO_ROOT / "services"))
    from lk import config as C
    if not args or args[0] == "list":
        keys = C.secret_keys()
        print("keys stored:" if keys else "(no keys yet)")
        for k in keys:
            print(f"  {k}")
        print(f"\nfile: {C.SECRETS_PATH}")
        print(f"add one:  lk secrets set <{ '|'.join(C.secret_providers()) }>")
        print("          (you paste just the key; it's prompted hidden, off-screen)")
        return 0
    if args[0] == "set" and len(args) >= 2:
        provider = args[1]
        var = C.resolve_secret_name(provider)          # gemini → GEMINI_API_KEY
        value = args[2] if len(args) > 2 else ""
        if not value:
            import getpass
            label = provider if var != provider else var
            try:
                value = getpass.getpass(f"  paste your {label} API key (hidden): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  cancelled"); return 1
        if not value:
            print("  no key given"); return 1
        C.set_secret(var, value)
        print(f"  saved {var} (0600) — used automatically for '{provider}'")
        return 0
    print("usage: lk secrets [list | set <provider> [key]]")
    print(f"providers: {', '.join(C.secret_providers())}")
    return 2


def cmd_config(args: list[str]) -> int:
    sys.path.insert(0, str(REPO_ROOT / "services"))
    from lk import config as C
    if not args or args[0] == "list":
        cfg = C.load()
        print(json.dumps(cfg, indent=2) if cfg else "(empty — `lk wizard` or `lk config set KEY VALUE`)")
        print(f"\nfile: {C.CONFIG_PATH}\nkeys: {', '.join(C._ENV_MAP)}")
        return 0
    if args[0] == "get" and len(args) > 1:
        print(C.load().get(args[1], ""))
        return 0
    if args[0] == "set" and len(args) > 2:
        C.set_value(args[1], " ".join(args[2:]))
        print(f"  {args[1]} = {' '.join(args[2:])}  → {C.CONFIG_PATH}")
        return 0
    if args[0] == "unset" and len(args) > 1:
        C.set_value(args[1], "")
        print(f"  {args[1]} removed")
        return 0
    print("usage: lk config [list | get KEY | set KEY VALUE | unset KEY]")
    return 2


def cmd_wizard(args: list[str]) -> int:
    """First-run setup: detect what's present, choose a backend, write lk.json."""
    yes = "--yes" in args
    sys.path.insert(0, str(REPO_ROOT / "services"))
    from lk import config as C
    cfg = C.load()

    models = sorted((REPO_ROOT / "models").rglob("*.gguf"))
    weights = [m for m in models if "mmproj" not in m.name.lower()]
    bin_ = REPO_ROOT / "third_party/llama.cpp/build/bin/llama-server"
    has_local = bool(weights) and bin_.exists()
    has_claude_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

    print("LAWRENCE setup")
    print(f"  local model : {weights[0].name if weights else 'none found'}"
          f"{' + llama-server OK' if bin_.exists() else ' (llama-server NOT built)'}")
    print(f"  claude key  : {'ANTHROPIC_API_KEY set' if has_claude_key else 'not set'}")

    default = "local" if has_local else ("anthropic" if has_claude_key else "local")
    if yes:
        backend = default
    else:
        choice = input(f"  backend [local/anthropic/api] ({default}): ").strip().lower()
        backend = choice or default

    if backend == "local":
        if weights:
            cfg["model"] = str(weights[0])
        cfg.pop("backend", None)          # local is the built-in default
        cfg.pop("api_base", None)
    elif backend == "anthropic":
        cfg["backend"] = "anthropic"
        cfg["api_model"] = cfg.get("api_model") or (
            "claude-opus-4-8" if yes else
            (input("  model id (claude-opus-4-8): ").strip() or "claude-opus-4-8"))
        cfg["api_key_env"] = "ANTHROPIC_API_KEY"
        cfg.pop("api_base", None)
    elif backend == "api":
        cfg["api_base"] = cfg.get("api_base") or input("  OpenAI-compatible base URL: ").strip()
        cfg["api_model"] = cfg.get("api_model") or input("  model name: ").strip()
        key_env = input("  env var holding the API key (e.g. OPENAI_API_KEY): ").strip()
        if key_env:
            cfg["api_key_env"] = key_env
        cfg.pop("backend", None)
    path = C.save(cfg)
    print(f"  wrote {path}")
    print("  next: `lk start` (UI) or `lk repl` (terminal)")
    if not _node_ready():
        print("  note: first `lk start` will npm-install the desktop deps;"
              " if GTK/WebKit packages are missing run: cd apps/desktop && npm run deps:system")
    return 0


def cmd_ingest(args: list[str]) -> int:
    if not args:
        print("usage: lk ingest PATH|URL [more...]")
        return 2
    sys.path.insert(0, str(REPO_ROOT / "services"))
    from lk import config as C
    C.apply_to_env()
    from lk.retrieval.ingest import ingest
    rc = 0
    for target in args:
        try:
            n, title = ingest(target)
            print(f"  ingested {title!r}: {n} chunks → memory/retrieval.db")
        except Exception as exc:
            print(f"  FAILED {target}: {exc}", file=sys.stderr)
            rc = 1
    return rc


def cmd_launcher(args: list[str]) -> int:
    """The gateway. A separate GUI window when a display exists; a console menu
    otherwise. `lk launcher --tui` forces the console; `--gui` forces the window;
    `--here` runs the GUI in the foreground instead of detaching it."""
    sys.path.insert(0, str(REPO_ROOT / "services"))
    force_tui = "--tui" in args
    force_gui = "--gui" in args
    foreground = "--here" in args or "--foreground" in args
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    use_gui = force_gui or (not force_tui and has_display and _tk_available())
    if not use_gui:
        from lk.launcher import run
        return run()

    if foreground:
        from lk.launcher_gui import run as run_gui
        return run_gui()
    # Detach: a window you summon and walk away from — not tied to this terminal.
    # A second `lk launcher` raises the existing window instead of opening a new one.
    log = REPO_ROOT / ".runtime" / "launcher.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as fh:
        subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "lk"), "launcher", "--gui", "--here"],
            stdout=fh, stderr=fh, stdin=subprocess.DEVNULL,
            start_new_session=True, cwd=str(REPO_ROOT),
        )
    print("  launcher window opened (summon again with `lk` to raise it).")
    return 0


def _tk_available() -> bool:
    try:
        import tkinter  # noqa: F401
        return True
    except Exception:
        return False


def cmd_reset(args: list[str]) -> int:
    """Force a clean slate from any state: kill every tracked/untracked popup +
    bridge, the hotkey listener, and stale pidfiles. `--all` also stops the warm
    llama-server. Use when something is wedged and a normal stop won't take."""
    rc = _desktopctl("reset", "--all") if "--all" in args else _desktopctl("reset")
    labels = {"popup", "bridge", "windows-hotkey"}
    if "--all" in args:
        labels.update({"model", "repl", "sensor", "desktop-dev"})
    leftovers = [row for row in managed_processes() if row["label"] in labels]
    if leftovers:
        terminate_processes(leftovers, force=True)
    leftovers = [row for row in managed_processes() if row["label"] in labels]
    if leftovers:
        print("  reset incomplete:")
        print(format_processes(leftovers))
        return 1
    return rc


def cmd_restart(args: list[str]) -> int:
    """Stop then start. `--force` hard-resets first (recovers a wedged state);
    `--all` also cycles the model server."""
    if "--force" in args:
        cmd_reset(["--all"] if "--all" in args else [])
    else:
        cmd_stop(["--all"] if "--all" in args else [])
    return cmd_start([a for a in args if a not in ("--all", "--force")])


def cmd_rebuild(args: list[str]) -> int:
    """Recompile the desktop popup (Tauri release build) and relaunch it.

    The popup's frontend (web/) is embedded into the binary at build time, so a
    web/Rust edit only takes effect after a rebuild + relaunch. `--no-restart`
    builds without relaunching."""
    if not _node_ready():
        print("  installing desktop dependencies first (npm install)…")
        if subprocess.call(["npm", "install", "--no-fund", "--no-audit"],
                           cwd=REPO_ROOT / "apps" / "desktop") != 0:
            print("  npm install failed — see `lk doctor`")
            return 1
    print("  recompiling the popup (cargo release build — first build is slow)…")
    rc = _desktopctl("build")
    if rc != 0:
        print("  build failed — check cargo/node (`lk doctor`), then retry")
        return rc
    if "--no-restart" in args:
        print("  built. `lk start` (or Restart) to run the new binary.")
        return 0
    print("  built — relaunching so the new binary takes effect…")
    return _desktopctl("restart")


def cmd_memory(args: list[str]) -> int:
    """Inspect / back up / clear LAWRENCE memory (see memops.py)."""
    sys.path.insert(0, str(REPO_ROOT / "services"))
    from lk import memops as M
    sub = args[0] if args else "stats"
    if sub in ("stats", "status", "ls"):
        s = M.stats()
        owner = s["locked_by"]
        print(f"  memory: {M.human(s['total_bytes'])} total"
              + (f"   (LOCKED by {owner.get('role','?')} pid {owner.get('pid','?')})" if owner else "   (unlocked)"))
        for cat, v in s["categories"].items():
            print(f"    {cat:<8} {v['files']:>4} files  {M.human(v['bytes'])}")
        print("\n  clear:  lk memory clear-cache | clear-rolling | clear-logs | clear-all")
        return 0
    if sub == "backup":
        print(f"  backed up → {M.backup()}")
        return 0
    mapping = {
        "clear-cache":   ["cache"],   "clear-rolling": ["rolling"],
        "clear-logs":    ["log"],     "clear-journal": ["journal"],
        "clear-notes":   ["notes"],   "clear-chats":   ["chats"],
        "clear-all":     ["all"],
    }
    if sub in mapping:
        force = "--force" in args
        res = M.clear(mapping[sub], force=force)
        if res.get("skipped"):
            print(f"  skipped: {res['skipped']}")
            print(f"  (re-run with --force to override, e.g. `lk memory {sub} --force`)")
            return 1
        print(f"  cleared {res['cleared']}: removed {res['removed']} item(s)")
        if res.get("backup"):
            print(f"  backup: {res['backup']}")
        return 0
    print("usage: lk memory [stats | backup | clear-cache | clear-rolling | clear-logs | clear-journal | clear-notes | clear-all] [--force]")
    return 2


def cmd_notes(args: list[str]) -> int:
    """Browse the zettelkasten — atomic, addressable notes (see ctx/notes.py).

    lk notes [list [N] | show <id> | search <query…>]
    Read-only and model-free: works against the same memory/ from any process,
    whether or not the kernel is running (the GUI/REPL share the identical store).
    """
    sys.path.insert(0, str(REPO_ROOT / "services"))
    from lk.ctx.notes import NoteStore
    ns = NoteStore()
    sub = args[0] if args else "list"

    if sub in ("list", "ls"):
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 20
        recs = ns.list_notes(n)
        if not recs:
            print("  (no notes yet — they accrue from significant observations)")
            return 0
        print(f"  {len(recs)} note(s), most recent first:")
        for r in recs:
            tags = (" #" + " #".join(r.get("tags", []))) if r.get("tags") else ""
            print(f"    {r['id']}  [{r.get('kind','?')}]{tags}")
        print("\n  show one:  lk notes show <id>")
        return 0

    if sub == "show":
        if len(args) < 2:
            print("usage: lk notes show <id>")
            return 2
        note = ns.read_note(args[1])
        if not note:
            print(f"  no note with id {args[1]}")
            return 1
        print(f"  id      {note['id']}")
        print(f"  ts      {note.get('ts','')}")
        print(f"  kind    {note.get('kind','')}")
        if note.get("tags"):    print(f"  tags    {', '.join(note['tags'])}")
        if note.get("links"):   print(f"  links   {', '.join(note['links'])}")
        if note.get("backlinks"): print(f"  ↩ from  {', '.join(note['backlinks'])}")
        if note.get("source"):  print(f"  source  {note['source']}")
        print(f"\n{note.get('body','')}\n")
        return 0

    if sub == "search":
        q = " ".join(args[1:]).strip()
        if not q:
            print("usage: lk notes search <query…>")
            return 2
        hits = ns.search(q, limit=15)
        if not hits:
            print(f"  no notes match {q!r}")
            return 0
        print(f"  {len(hits)} match(es) for {q!r}:")
        for r in hits:
            tags = (" #" + " #".join(r.get("tags", []))) if r.get("tags") else ""
            print(f"    {r['id']}  [{r.get('kind','?')}]{tags}")
        return 0

    print("usage: lk notes [list [N] | show <id> | search <query…>]")
    return 2


def cmd_chats(args: list[str]) -> int:
    """Browse + manage the chat workspace (WS-U Track 1) — switchable conversations.

    lk chats [list | show <id> | export <id> | new [title…] | switch <id>
              | rename <id> <title…> | delete <id> [--hard]]
    Works against the same memory/chats/ store the desktop UI uses. Management
    ops are file-level — prefer running them while the kernel is stopped.
    """
    sys.path.insert(0, str(REPO_ROOT / "services"))
    from lk.ctx.chats import ChatStore
    cs = ChatStore()
    sub = args[0] if args else "list"

    if sub in ("list", "ls"):
        active = cs.active_chat()
        rows = cs.list_chats()
        if not rows:
            print("  (no chats yet — created from the desktop UI or `lk chats new`)")
            return 0
        print(f"  {len(rows)} chat(s), most recent first (* = active):")
        for r in rows:
            mark = "*" if r["id"] == active else " "
            print(f"   {mark} {r['id']}  {r.get('title') or '(untitled)'}  · {r.get('messages', 0)} msg")
        print("\n  show one:  lk chats show <id>")
        return 0

    if sub == "show":
        if len(args) < 2:
            print("usage: lk chats show <id>"); return 2
        chat = cs.get_chat(args[1])
        if not chat:
            print(f"  no chat with id {args[1]}"); return 1
        print(f"  id     {chat['id']}")
        print(f"  title  {chat.get('title') or '(untitled)'}")
        print(f"  msgs   {chat.get('messages', 0)}\n")
        for m in chat.get("messages_list", []):
            who = "you" if m.get("role") == "user" else "lk "
            print(f"    [{m.get('seq')}] {who}  {str(m.get('text', ''))[:100]}")
        return 0

    if sub == "export":
        if len(args) < 2:
            print("usage: lk chats export <id>"); return 2
        mdx = cs.export_chat(args[1])
        if not mdx:
            print(f"  no chat with id {args[1]}"); return 1
        print(mdx)
        return 0

    if sub == "new":
        meta = cs.create_chat(" ".join(args[1:]))
        cs.set_active(meta["id"])
        print(f"  created {meta['id']}  {meta.get('title') or '(untitled)'}  (now active)")
        return 0

    if sub == "switch":
        if len(args) < 2:
            print("usage: lk chats switch <id>"); return 2
        if not cs.set_active(args[1]):
            print(f"  no chat with id {args[1]}"); return 1
        print(f"  active chat → {args[1]}  (a running kernel applies this on next start)")
        return 0

    if sub == "rename":
        if len(args) < 3:
            print("usage: lk chats rename <id> <title…>"); return 2
        if not cs.rename_chat(args[1], " ".join(args[2:])):
            print(f"  no chat with id {args[1]}"); return 1
        print(f"  renamed {args[1]}")
        return 0

    if sub in ("delete", "rm"):
        if len(args) < 2:
            print("usage: lk chats delete <id> [--hard]"); return 2
        hard = "--hard" in args
        if not cs.delete_chat(args[1], hard=hard):
            print(f"  no chat with id {args[1]}"); return 1
        print(f"  {'deleted' if hard else 'archived'} {args[1]}")
        return 0

    print("usage: lk chats [list | show <id> | export <id> | new [title…] | "
          "switch <id> | rename <id> <title…> | delete <id> [--hard]]")
    return 2


def cmd_links(args: list[str]) -> int:
    """Browse + create cross-chat graph links (WS-U Track 2) — the zettelkasten
    extended so chat messages are first-class, linkable nodes.

    lk links show <chatId> <seq>                      a message's neighborhood
    lk links add  <srcChat> <srcSeq> <dstChat> <dstSeq> [kind]
    """
    sys.path.insert(0, str(REPO_ROOT / "services"))
    from lk.ctx import NoteStore
    ns = NoteStore()
    sub = args[0] if args else ""

    if sub == "show" and len(args) >= 3:
        node = f"{args[1]}:{args[2]}"
        nb = ns.neighborhood(node)
        print(f"  node    {node}")
        print(f"  → out   {', '.join(nb['out']) or '—'}")
        print(f"  ← in    {', '.join(nb['in']) or '—'}")
        return 0

    if sub == "add" and len(args) >= 5:
        src, dst = f"{args[1]}:{args[2]}", f"{args[3]}:{args[4]}"
        kind = args[5] if len(args) > 5 else "link"
        created = ns.add_edge(src, dst, kind=kind)
        print(f"  {'linked' if created else 'already linked'} {src} ↔ {dst}")
        return 0

    print("usage: lk links [show <chatId> <seq> | add <srcChat> <srcSeq> <dstChat> <dstSeq> [kind]]")
    return 2


def cmd_preset(args: list[str]) -> int:
    """Apply a one-pick backend + per-role routing setup."""
    sys.path.insert(0, str(REPO_ROOT / "services"))
    from lk import config as C
    if not args or args[0] in ("list", "ls"):
        print("presets (lk preset use <name>):")
        for name, p in C.PRESETS.items():
            print(f"  {name:<8} {p['label']}")
        cur = C.load()
        print(f"\ncurrent: backend={cur.get('backend','local')} routing={cur.get('routing',{}) or '—'}")
        return 0
    if args[0] in ("use", "set") and len(args) >= 2:
        try:
            _cfg, missing = C.apply_preset(args[1])
        except KeyError:
            print(f"  unknown preset: {args[1]} (try: {', '.join(C.PRESETS)})")
            return 2
        print(f"  applied '{args[1]}' → {C.CONFIG_PATH}")
        if missing:
            print(f"  needs a key for: {', '.join(missing)}  →  lk secrets set {missing[0]}")
        print("  takes effect on the next `lk start`.")
        return 0
    print("usage: lk preset [list | use <name>]")
    print(f"names: {', '.join(C.PRESETS)}")
    return 2


_COMMANDS = {
    "status": cmd_status, "start": cmd_start, "stop": cmd_stop,
    "processes": cmd_processes, "ps": cmd_processes,
    "repl": cmd_repl, "ui": cmd_ui, "attach": cmd_attach,
    "logs": cmd_logs, "doctor": cmd_doctor, "config": cmd_config,
    "secrets": cmd_secrets, "wizard": cmd_wizard, "ingest": cmd_ingest,
    "launcher": cmd_launcher, "menu": cmd_launcher, "preset": cmd_preset,
    "restart": cmd_restart, "rebuild": cmd_rebuild, "reset": cmd_reset,
    "memory": cmd_memory, "mem": cmd_memory, "notes": cmd_notes,
    "chats": cmd_chats, "links": cmd_links,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # Bare `lk` in a terminal opens the launcher gateway; piped/non-TTY → status.
    if not args:
        return cmd_launcher([]) if sys.stdin.isatty() and sys.stdout.isatty() else cmd_status([])
    cmd = args.pop(0)
    if cmd in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    fn = _COMMANDS.get(cmd)
    if fn is None:
        print(f"unknown command: {cmd}\n")
        print(__doc__.strip())
        return 2
    return fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
