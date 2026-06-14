"""lk — the LAWRENCE front door. Fast, stdlib-only, works before anything heavy.

This is the control CLI (plan P2): the interface you use *before* the model or
UI loads. It never imports the kernel — it inspects state over HTTP and the
writer-lock file, and delegates real work to the existing entry points:

    lk start            bridge + llama-server + popup  (the normal way to run)
    lk stop [--all]     stop popup+bridge  (--all also stops llama-server)
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
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOPCTL = REPO_ROOT / "apps" / "desktop" / "scripts" / "desktopctl.sh"
LOCK_PATH = REPO_ROOT / "memory" / ".writer.lock"
SERVER_LOG = REPO_ROOT / ".runtime" / "lk-server.log"

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
    rc = _desktopctl("stop")
    if "--all" in args:
        n = subprocess.run(["pkill", "-f", "llama-server"], capture_output=True).returncode
        print(f"  llama-server: {'stopped' if n == 0 else 'was not running'}")
    else:
        if _http_ok(f"http://127.0.0.1:{LLAMA_PORT}/health"):
            print("  llama-server left warm on :8190 (use `lk stop --all` to stop it too)")
    return rc


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


_COMMANDS = {
    "status": cmd_status, "start": cmd_start, "stop": cmd_stop,
    "repl": cmd_repl, "ui": cmd_ui, "attach": cmd_attach,
    "logs": cmd_logs, "doctor": cmd_doctor, "config": cmd_config,
    "secrets": cmd_secrets, "wizard": cmd_wizard, "ingest": cmd_ingest,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args.pop(0) if args else "status"
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
