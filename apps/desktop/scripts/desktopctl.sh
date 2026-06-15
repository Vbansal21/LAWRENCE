#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
RUNTIME="$REPO_ROOT/.runtime/desktop"
ENV_FILE="$RUNTIME/desktop.env"
APP_PID="$RUNTIME/app.pid"
BRIDGE_PID="$RUNTIME/bridge.pid"
APP_LOG="$RUNTIME/app.log"
BRIDGE_LOG="$RUNTIME/bridge.log"
HOST_UI_CONFIG="$RUNTIME/host-ui.json"
HOST_INSTALL_PLAN="$RUNTIME/host-install-plan.json"
APP_BIN="$ROOT/src-tauri/target/release/lawrence-desktop"

mkdir -p "$RUNTIME"
cd "$ROOT"

if [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
fi
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi

LK_UI_PORT="${LK_UI_PORT:-8765}"
LAWRENCE_HOTKEY="${LAWRENCE_HOTKEY:-Ctrl+Shift+L}"
LAWRENCE_HIDE_ON_BLUR="${LAWRENCE_HIDE_ON_BLUR:-0}"
LIFECYCLE_LOCK="$RUNTIME/desktopctl.lock"

# Serialize mutating lifecycle ops (start/stop/restart/build/reset/show/toggle) so
# concurrent or rapid-fire invocations can't race into duplicate or half-started
# processes. Reentrant across the process tree via an env guard, so `restart`
# (which re-invokes `$0 stop` / `$0 start`) does not deadlock on itself.
with_lifecycle_lock() {
  [[ "${LK_LIFECYCLE_LOCKED:-}" == "1" ]] && return 0
  if ! command -v flock >/dev/null 2>&1; then
    return 0   # flock absent (rare) → best-effort, no serialization
  fi
  exec 9>"$LIFECYCLE_LOCK"
  if ! flock -w 30 9; then
    echo "desktopctl: another lifecycle operation is in progress (waited 30s)" >&2
    exit 1
  fi
  export LK_LIFECYCLE_LOCKED=1
}

pid_alive() {
  local file="$1"
  [[ -f "$file" ]] && kill -0 "$(cat "$file")" 2>/dev/null
}

app_pids() {
  ps -eo pid=,args= 2>/dev/null \
    | awk '/[l]awrence-desktop/ && $0 !~ /cargo|rustc/ {print $1}'
}

bridge_pids() {
  ps -eo pid=,args= 2>/dev/null \
    | awk -v port="$LK_UI_PORT" '
        /[u]i_bridge\.py/ {
          if ($0 ~ "--port " port || (port == "8765" && $0 !~ /--port/)) print $1
        }'
}

all_bridge_pids() {
  ps -eo pid=,args= 2>/dev/null \
    | awk '/[u]i_bridge\.py/ {print $1}'
}

needs_build() {
  [[ ! -x "$APP_BIN" ]] && return 0
  find web src-tauri/src src-tauri/capabilities \
    src-tauri/tauri.conf.json src-tauri/Cargo.toml \
    -type f -newer "$APP_BIN" -print -quit 2>/dev/null | grep -q .
}

port_open() {
  python3 - "${1:-$LK_UI_PORT}" <<'PY'
import socket, sys
try:
    with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=0.2):
        pass
except OSError:
    raise SystemExit(1)
PY
}

# Reach the RUNNING popup over its loopback control socket (show|hide|toggle).
# Fails (exit 1) when the app isn't running — callers fall back to a start.
control_send() {
  python3 - "$1" <<'PY'
import os, socket, sys
port = int(os.environ.get("LAWRENCE_CONTROL_PORT", "8767"))
try:
    with socket.create_connection(("127.0.0.1", port), timeout=0.5) as s:
        s.sendall((sys.argv[1] + "\n").encode())
except OSError:
    raise SystemExit(1)
PY
}

bridge_health() {
  python3 - "$LK_UI_PORT" <<'PY'
import json, sys, urllib.request
try:
    raw = urllib.request.urlopen(f"http://127.0.0.1:{int(sys.argv[1])}/health", timeout=1.0).read()
    data = json.loads(raw)
except Exception:
    raise SystemExit(1)
if not data.get("ok"):
    raise SystemExit(1)
print(json.dumps(data))
PY
}

start_bridge() {
  if bridge_health >/dev/null 2>&1; then
    echo "bridge http: already healthy on 127.0.0.1:$LK_UI_PORT"
    return
  fi
  if port_open "$LK_UI_PORT"; then
    local stale
    stale="$(bridge_pids | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
    if [[ -n "$stale" ]]; then
      echo "bridge: restarting unhealthy ui_bridge instance(s) $stale"
      stop_bridge_processes >/dev/null
    else
      echo "bridge: 127.0.0.1:$LK_UI_PORT is in use by a non-LAWRENCE process; not touching it"
      exit 1
    fi
  fi
  setsid python3 scripts/ui_bridge.py --port "$LK_UI_PORT" >"$BRIDGE_LOG" 2>&1 &
  echo "$!" > "$BRIDGE_PID"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if bridge_health >/dev/null 2>&1; then
      break
    fi
    if ! pid_alive "$BRIDGE_PID"; then
      echo "bridge: failed to start"
      tail -n 60 "$BRIDGE_LOG" 2>/dev/null || true
      exit 1
    fi
    sleep 0.5
  done
  echo "bridge http: started pid $(cat "$BRIDGE_PID") on 127.0.0.1:$LK_UI_PORT"
}

# Launch the Windows-side global hotkey listener so Ctrl+Shift+L works from
# anywhere (a WSLg-registered shortcut only fires while a WSLg window is
# focused). It connects to the control socket via forwarded localhost. The PS
# script self-guards with a named mutex, so repeated calls are harmless.
kill_windows_hotkey() {
  command -v powershell.exe >/dev/null 2>&1 || return 0
  # Codex: stop by script path or the title the helper sets, so cleanup still
  # works when PowerShell hides or rewrites one of those process surfaces.
  powershell.exe -NoProfile -Command "\$ids = @(); Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { \$_.ProcessId -ne \$PID -and \$_.CommandLine -match '(-File|/File)\s+.*(GlobalHotkey|Register-Hotkey)\.ps1' } | ForEach-Object { \$ids += [int]\$_.ProcessId }; Get-Process -Name powershell -ErrorAction SilentlyContinue | Where-Object { \$_.Id -ne \$PID -and \$_.MainWindowTitle -eq 'LAWRENCE-GlobalHotkey' } | ForEach-Object { \$ids += [int]\$_.Id }; \$ids | Sort-Object -Unique | ForEach-Object { Stop-Process -Id \$_ -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1 || true
}

ensure_windows_hotkey() {
  command -v powershell.exe >/dev/null 2>&1 || return 0
  local ps_unix="$ROOT/host/windows/GlobalHotkey.ps1" ps_win
  ps_win="$(wslpath -w "$ps_unix" 2>/dev/null)" || return 0
  local port="${LAWRENCE_CONTROL_PORT:-8767}"
  powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden \
    -Command "Start-Process -WindowStyle Hidden -FilePath powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File','$ps_win','-Port','$port'" \
    >/dev/null 2>&1 || true
  echo "hotkey: Windows-side listener armed (Ctrl+Shift+L → :$port)"
}

start_app() {
  if pid_alive "$APP_PID"; then
    echo "popup: already running pid $(cat "$APP_PID")"
    ensure_windows_hotkey
    return
  fi
  local stale
  stale="$(app_pids | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  if [[ -n "$stale" ]]; then
    echo "popup: stopping untracked instance(s) $stale"
    stop_app_processes >/dev/null
  fi
  if needs_build; then
    echo "popup: building native release"
    npm run build
  fi
  setsid env \
    LK_UI_PORT="$LK_UI_PORT" \
    LAWRENCE_BRIDGE_URL="${LAWRENCE_BRIDGE_URL:-http://127.0.0.1:$LK_UI_PORT}" \
    LAWRENCE_HOTKEY="$LAWRENCE_HOTKEY" \
    LAWRENCE_HIDE_ON_BLUR="$LAWRENCE_HIDE_ON_BLUR" \
    GTK_USE_PORTAL="${GTK_USE_PORTAL:-0}" \
    WEBKIT_DISABLE_DMABUF_RENDERER="${WEBKIT_DISABLE_DMABUF_RENDERER:-1}" \
    WEBKIT_DISABLE_COMPOSITING_MODE="${WEBKIT_DISABLE_COMPOSITING_MODE:-1}" \
    LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}" \
    "$APP_BIN" >"$APP_LOG" 2>&1 &
  echo "$!" > "$APP_PID"
  sleep 1
  if ! pid_alive "$APP_PID"; then
    echo "popup: failed to start"
    tail -n 80 "$APP_LOG" 2>/dev/null || true
    exit 1
  fi
  echo "popup: started pid $(cat "$APP_PID")"
  echo "hotkey: $LAWRENCE_HOTKEY"
  ensure_windows_hotkey
}

show_app() {
  start_bridge
  # Fast path: tell the running app to surface itself — no restart, instant.
  if control_send show 2>/dev/null; then
    echo "popup: shown (live control socket)"
    return
  fi
  if pid_alive "$APP_PID" || [[ -n "$(app_pids)" ]]; then
    echo "popup: restarting unresponsive instance"
    stop_app_processes >/dev/null
    rm -f "$APP_PID"
  fi
  start_app
}

toggle_app() {
  if control_send toggle 2>/dev/null; then
    echo "popup: toggled"
    return
  fi
  show_app
}

stop_app_processes() {
  local pid
  for pid in $(app_pids); do
    kill "$pid" 2>/dev/null || true
  done
  for _ in 1 2 3 4 5; do
    [[ -z "$(app_pids)" ]] && return
    sleep 0.2
  done
  for pid in $(app_pids); do
    kill -9 "$pid" 2>/dev/null || true
  done
}

stop_bridge_processes() {
  local pid
  for pid in $(bridge_pids); do
    kill "$pid" 2>/dev/null || true
  done
  for _ in 1 2 3 4 5; do
    [[ -z "$(bridge_pids)" ]] && return
    sleep 0.2
  done
  for pid in $(bridge_pids); do
    kill -9 "$pid" 2>/dev/null || true
  done
}

# Force a clean slate from ANY state: kill tracked + untracked popup and bridge
# instances (every ui_bridge.py, not just our port), stop the hotkey listener,
# and clear stale pidfiles. `--all`/`--server` also stops the warm llama-server.
# After this, a plain `start` always works. flock auto-releases on the dead PIDs,
# so the writer lock frees itself.
force_reset() {
  echo "reset: forcing a clean slate"
  stop_app_processes >/dev/null 2>&1 || true
  local pid
  for pid in $(all_bridge_pids); do kill "$pid" 2>/dev/null || true; done
  sleep 0.5
  for pid in $(all_bridge_pids); do kill -9 "$pid" 2>/dev/null || true; done
  kill_windows_hotkey
  rm -f "$APP_PID" "$BRIDGE_PID"
  if [[ "${1:-}" == "--all" || "${1:-}" == "--server" ]]; then
    pkill -9 -f "llama-server" 2>/dev/null || true
    echo "reset: llama-server stopped"
  fi
  echo "reset: cleared popup + bridge + hotkey + stale pidfiles"
}

services_start() {
  start_bridge
}

services_stop() {
  stop_pid "bridge" "$BRIDGE_PID"
}

services_restart() {
  services_stop
  services_start
}

stop_pid() {
  local label="$1"
  local file="$2"
  if [[ "$label" == "popup" ]]; then
    local pids
    pids="$(app_pids | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
    if pid_alive "$file" || [[ -n "$pids" ]]; then
      stop_app_processes
      rm -f "$file"
      echo "$label: stopped"
      return
    fi
    stop_app_processes
  fi
  if [[ "$label" == "bridge" ]]; then
    local pids
    pids="$(bridge_pids | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
    if pid_alive "$file" || [[ -n "$pids" ]]; then
      stop_bridge_processes
      rm -f "$file"
      echo "$label: stopped"
      return
    fi
  fi
  if ! pid_alive "$file"; then
    echo "$label: not running"
    rm -f "$file"
    return
  fi
  local pid
  pid="$(cat "$file")"
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$file"
      echo "$label: stopped"
      return
    fi
    sleep 0.2
  done
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$file"
  echo "$label: killed"
}

write_hotkey() {
  local value="${1:-}"
  if [[ -z "$value" ]]; then
    echo "usage: npm run popup:hotkey -- Ctrl+Shift+L"
    exit 2
  fi
  cat > "$ENV_FILE" <<EOF
LK_UI_PORT=$LK_UI_PORT
LAWRENCE_HOTKEY=$value
LAWRENCE_HIDE_ON_BLUR=$LAWRENCE_HIDE_ON_BLUR
EOF
  echo "hotkey: $value"
  echo "restart required: npm run popup:restart"
}

status() {
  local pids
  pids="$(app_pids | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  if pid_alive "$APP_PID"; then
    echo "popup: running pid $(cat "$APP_PID")"
  elif [[ -n "$pids" ]]; then
    echo "popup: running untracked pid(s) $pids"
  else
    echo "popup: stopped"
  fi
  local health
  if health="$(bridge_health 2>/dev/null)"; then
    echo "bridge http: healthy on 127.0.0.1:$LK_UI_PORT"
    python3 - "$health" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
events = data.get("eventsUrl") or ""
if events:
    print(f"bridge events: {events}")
else:
    print("bridge events: disabled")
PY
  elif port_open "$LK_UI_PORT"; then
    echo "bridge http: port 127.0.0.1:$LK_UI_PORT is occupied but /health failed"
  else
    echo "bridge http: stopped"
  fi
  echo "hotkey: $LAWRENCE_HOTKEY"
  echo "hide-on-blur: $LAWRENCE_HIDE_ON_BLUR"
}

doctor() {
  echo "== LAWRENCE processes =="
  ps -eo pid,rss,etime,comm,args 2>/dev/null \
    | grep -E "llama-server|ui_bridge\.py|lawrence-desktop" | grep -v grep \
    || echo "  (none of llama-server / ui_bridge / lawrence-desktop are running)"
  echo
  echo "== expected ports =="
  for spec in "8190 llama.cpp model server" "$LK_UI_PORT desktop HTTP bridge" "${LK_UI_EVENTS_PORT:-8766} desktop SSE event stream"; do
    p="${spec%% *}"
    label="${spec#* }"
    if ss -tlnp 2>/dev/null | grep -q ":$p "; then
      echo "  $p  LISTEN  $label"
    else
      echo "  $p  -       $label"
    fi
  done
  echo
  echo "== model health (via bridge) =="
  curl -s --max-time 4 "http://127.0.0.1:$LK_UI_PORT/health" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('  backend:', d.get('backend')); print('  modelHealth:', d.get('modelHealth')); print('  eventsUrl:', d.get('eventsUrl'))" 2>/dev/null \
    || echo "  bridge not answering on 127.0.0.1:$LK_UI_PORT"
  echo
}

host_config() {
  local write=0
  if [[ "${1:-}" == "--write" ]]; then
    write=1
  fi
  local out
  out="$(python3 - "$REPO_ROOT" "$ROOT" "$LK_UI_PORT" "${LK_UI_EVENTS_PORT:-8766}" "$LAWRENCE_HOTKEY" "$LAWRENCE_HIDE_ON_BLUR" <<'PY'
import json, os, platform, socket, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

repo, desktop, bridge_port, events_port, hotkey, hide_on_blur = sys.argv[1:7]

def port_open(port: str) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.2):
            return True
    except OSError:
        return False

def health() -> dict:
    try:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{int(bridge_port)}/health", timeout=0.8).read()
        data = json.loads(raw)
        return data if data.get("ok") else {}
    except Exception:
        return {}

data = health()
payload = {
    "schemaVersion": 1,
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "roles": {
        "serviceManager": "wsl",
        "uiRuntime": "host-native"
    },
    "manager": {
        "platform": platform.platform(),
        "repoRoot": str(Path(repo)),
        "desktopRoot": str(Path(desktop)),
        "controller": "apps/desktop/scripts/desktopctl.sh",
        "commands": {
            "status": "npm run popup:status",
            "doctor": "npm run popup:doctor",
            "startServices": "npm run services:start",
            "stopServices": "npm run services:stop",
            "restartServices": "npm run services:restart",
            "writeHostConfig": "npm run host:config:write"
        }
    },
    "bridge": {
        "httpUrl": f"http://127.0.0.1:{int(bridge_port)}",
        "eventsUrl": data.get("eventsUrl") or f"http://127.0.0.1:{int(events_port)}/events",
        "healthPath": "/health",
        "jobsPath": "/jobs",
        "turnPath": "/turn/async",
        "httpHealthy": bool(data),
        "eventStreamAdvertised": bool(data.get("eventsUrl")) if data else port_open(events_port)
    },
    "model": {
        "serverUrl": "http://127.0.0.1:8190",
        "healthy": bool(data.get("modelHealth")) if data else port_open("8190"),
        "backend": data.get("backend", "")
    },
    "ui": {
        "hotkey": hotkey,
        "hideOnBlur": hide_on_blur not in ("0", "false", "False", "no", "off"),
        "expectedRuntime": "native-host",
        "fallbackRuntime": "wslg-tauri",
        "nativeTarget": "windows-arm64-tauri",
        "windowsBuildScript": "apps/desktop/host/windows/Build-HostUi.ps1",
        "windowsStartScript": "apps/desktop/host/windows/Start-HostUi.ps1",
        "windowsHotkeyHelper": "apps/desktop/host/windows/Register-Hotkey.ps1"
    },
    "security": {
        "dataPlane": "loopback-http-sse",
        "controlPlane": "windows-host-helper-or-named-pipe",
        "auth": "local-token-planned",
        "note": "Use loopback HTTP/SSE for high-volume UI data; use a Windows host helper or named pipe for privileged lifecycle/control operations."
    },
    "removedServices": {
        "ollama": "not used by LAWRENCE; disable/remove the host ollama.service if present"
    }
}
print(json.dumps(payload, indent=2))
PY
)"
  if (( write )); then
    printf "%s\n" "$out" > "$HOST_UI_CONFIG"
    echo "host ui config: $HOST_UI_CONFIG"
  else
    printf "%s\n" "$out"
  fi
}

host_install_plan() {
  local write=0
  if [[ "${1:-}" == "--write" ]]; then
    write=1
  fi
  local out
  out="$(python3 - "$REPO_ROOT" "$ROOT" "$HOST_UI_CONFIG" "$LAWRENCE_HOTKEY" <<'PY'
import json, os, platform, sys
from datetime import datetime, timezone
from pathlib import Path

repo, desktop, host_config, hotkey = sys.argv[1:5]
proc_version = ""
try:
    proc_version = Path("/proc/version").read_text(errors="ignore").lower()
except OSError:
    pass
is_wsl = "microsoft" in proc_version or "wsl" in proc_version
system_profiles = {"all users", "default", "default user", "public", "desktop.ini"}
windows_users = sorted(str(p) for p in Path("/mnt/c/Users").glob("*") if p.is_dir()) if Path("/mnt/c/Users").exists() else []
real_windows_users = [p for p in windows_users if Path(p).name.lower() not in system_profiles]
default_windows_dir = ""
if real_windows_users:
    default_windows_dir = str(Path(real_windows_users[0]) / "AppData/Local/LAWRENCE")

payload = {
    "schemaVersion": 1,
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "intent": "install-or-update-host-native-ui-from-wsl-manager",
    "target": {
        "host": "windows",
        "arch": "arm64",
        "ui": "tauri",
        "rustTarget": "aarch64-pc-windows-msvc",
        "buildLocation": "windows-native",
        "cacheRoot": "%LOCALAPPDATA%\\LAWRENCE\\cache"
    },
    "detected": {
        "platform": platform.platform(),
        "isWsl": is_wsl,
        "windowsUserDirs": windows_users[:8],
        "candidateWindowsUserDirs": real_windows_users[:8],
        "defaultWindowsInstallDir": os.environ.get("LAWRENCE_HOST_UI_DIR", default_windows_dir)
    },
    "inputs": {
        "repoRoot": str(Path(repo)),
        "desktopRoot": str(Path(desktop)),
        "hostConfigPath": str(Path(host_config)),
        "hotkey": hotkey
    },
    "phases": [
        {
            "id": "wsl-services",
            "owner": "wsl-manager",
            "status": "implemented",
            "commands": ["npm run services:start", "npm run services:stop", "npm run services:restart", "npm run popup:doctor"]
        },
        {
            "id": "handoff-config",
            "owner": "wsl-manager",
            "status": "implemented",
            "commands": ["npm run host:config", "npm run host:config:write"],
            "artifact": str(Path(host_config))
        },
        {
            "id": "host-native-build",
            "owner": "windows-host-toolchain",
            "status": "scripted-pending-host-run",
            "script": "apps/desktop/host/windows/Build-HostUi.ps1",
            "hotkeyHelper": "apps/desktop/host/windows/Register-Hotkey.ps1",
            "target": "aarch64-pc-windows-msvc",
            "cacheRoot": "%LOCALAPPDATA%\\LAWRENCE\\cache",
            "needs": ["Windows ARM64 Node/npm", "Rust MSVC toolchain", "Visual Studio Build Tools", "WebView2 Runtime"]
        },
        {
            "id": "host-native-install",
            "owner": "windows-host-script",
            "status": "scripted-pending-host-run",
            "script": "apps/desktop/host/windows/Build-HostUi.ps1",
            "targetDir": os.environ.get("LAWRENCE_HOST_UI_DIR", default_windows_dir),
            "creates": ["lawrence-desktop.exe", "config/host-ui.json", "host-ui-install.json", "scripts/Start-HostUi.ps1", "scripts/Register-Hotkey.ps1"],
            "optional": ["Start Menu shortcut with -CreateShortcut"]
        },
        {
            "id": "host-native-run",
            "owner": "windows-host-script",
            "status": "scripted-pending-host-run",
            "script": "apps/desktop/host/windows/Start-HostUi.ps1",
            "starts": ["npm run services:start inside WSL", "lawrence-desktop.exe on Windows"]
        },
        {
            "id": "host-to-wsl-ipc",
            "owner": "host-ui+manager",
            "status": "planned",
            "dataPlane": "loopback-http-sse-with-local-token",
            "controlPlane": "windows-host-helper-or-named-pipe",
            "reason": "HTTP/SSE fits streaming UI data; a Windows helper/named pipe is better for privileged lifecycle and richer future control."
        }
    ],
    "nonGoalsForThisPlan": [
        "Do not stop Ollama automatically.",
        "Do not expose manager commands beyond loopback without auth.",
        "Do not make WSLg the final UI runtime."
    ]
}
print(json.dumps(payload, indent=2))
PY
)"
  if (( write )); then
    printf "%s\n" "$out" > "$HOST_INSTALL_PLAN"
    echo "host install plan: $HOST_INSTALL_PLAN"
  else
    printf "%s\n" "$out"
  fi
}

case "${1:-status}" in
  start)
    with_lifecycle_lock
    start_bridge
    start_app
    ;;
  stop|kill)
    with_lifecycle_lock
    stop_pid "popup" "$APP_PID"
    stop_pid "bridge" "$BRIDGE_PID"
    kill_windows_hotkey
    echo "hotkey: Windows listener stopped"
    ;;
  reset|force-reset)
    with_lifecycle_lock
    force_reset "${2:-}"
    ;;
  services-start)
    with_lifecycle_lock
    services_start
    ;;
  services-stop)
    with_lifecycle_lock
    services_stop
    ;;
  services-restart)
    with_lifecycle_lock
    services_stop
    services_start
    ;;
  restart)
    with_lifecycle_lock
    stop_pid "popup" "$APP_PID"
    stop_pid "bridge" "$BRIDGE_PID"
    kill_windows_hotkey
    start_bridge
    start_app
    ;;
  show|open)
    with_lifecycle_lock
    show_app
    ;;
  toggle)
    with_lifecycle_lock
    toggle_app
    ;;
  status)
    status
    ;;
  doctor)
    doctor
    ;;
  host-config)
    host_config "${2:-}"
    ;;
  host-install-plan)
    host_install_plan "${2:-}"
    ;;
  logs)
    echo "== bridge =="
    tail -n 80 "$BRIDGE_LOG" 2>/dev/null || true
    echo "== popup =="
    tail -n 80 "$APP_LOG" 2>/dev/null || true
    ;;
  build)
    with_lifecycle_lock
    npm run build
    ;;
  hotkey)
    write_hotkey "${2:-}"
    ;;
  config)
    echo "config: $ENV_FILE"
    [[ -f "$ENV_FILE" ]] && cat "$ENV_FILE" || status
    ;;
  *)
    echo "usage: $0 start|show|stop|restart|reset [--all]|services-start|services-stop|services-restart|status|doctor|host-config [--write]|host-install-plan [--write]|logs|build|hotkey VALUE|config"
    exit 2
    ;;
esac
