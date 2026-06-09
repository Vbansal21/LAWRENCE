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

pid_alive() {
  local file="$1"
  [[ -f "$file" ]] && kill -0 "$(cat "$file")" 2>/dev/null
}

<<<<<<< HEAD
=======
app_pids() {
  ps -eo pid=,args= 2>/dev/null \
    | awk '/[l]awrence-desktop/ && $0 !~ /cargo|rustc/ {print $1}'
}

bridge_pids() {
  ps -eo pid=,args= 2>/dev/null \
    | awk '/[u]i_bridge\.py/ {print $1}'
}

needs_build() {
  [[ ! -x "$APP_BIN" ]] && return 0
  find web src-tauri/src src-tauri/capabilities \
    src-tauri/tauri.conf.json src-tauri/Cargo.toml \
    -type f -newer "$APP_BIN" -print -quit 2>/dev/null | grep -q .
}

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
port_open() {
  python3 - "$LK_UI_PORT" <<'PY'
import socket, sys
try:
    with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=0.2):
        pass
except OSError:
    raise SystemExit(1)
PY
}

start_bridge() {
  if port_open; then
    echo "bridge: already listening on 127.0.0.1:$LK_UI_PORT"
    return
  fi
  setsid python3 scripts/ui_bridge.py --port "$LK_UI_PORT" >"$BRIDGE_LOG" 2>&1 &
  echo "$!" > "$BRIDGE_PID"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if port_open; then
      break
    fi
    if ! pid_alive "$BRIDGE_PID"; then
      echo "bridge: failed to start"
      tail -n 60 "$BRIDGE_LOG" 2>/dev/null || true
      exit 1
    fi
    sleep 0.5
  done
  echo "bridge: started pid $(cat "$BRIDGE_PID")"
}

start_app() {
  if pid_alive "$APP_PID"; then
    echo "popup: already running pid $(cat "$APP_PID")"
    return
  fi
<<<<<<< HEAD
  if [[ ! -x "$APP_BIN" ]]; then
=======
  local stale
  stale="$(app_pids | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  if [[ -n "$stale" ]]; then
    echo "popup: stopping untracked instance(s) $stale"
    stop_app_processes >/dev/null
  fi
  if needs_build; then
    echo "popup: building native release"
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
    npm run build
  fi
  setsid env \
    LK_UI_PORT="$LK_UI_PORT" \
<<<<<<< HEAD
    LAWRENCE_HOTKEY="$LAWRENCE_HOTKEY" \
    LAWRENCE_HIDE_ON_BLUR="$LAWRENCE_HIDE_ON_BLUR" \
=======
    LAWRENCE_BRIDGE_URL="${LAWRENCE_BRIDGE_URL:-http://127.0.0.1:$LK_UI_PORT}" \
    LAWRENCE_HOTKEY="$LAWRENCE_HOTKEY" \
    LAWRENCE_HIDE_ON_BLUR="$LAWRENCE_HIDE_ON_BLUR" \
    GTK_USE_PORTAL="${GTK_USE_PORTAL:-0}" \
    WEBKIT_DISABLE_DMABUF_RENDERER="${WEBKIT_DISABLE_DMABUF_RENDERER:-1}" \
    WEBKIT_DISABLE_COMPOSITING_MODE="${WEBKIT_DISABLE_COMPOSITING_MODE:-1}" \
    LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}" \
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
}

<<<<<<< HEAD
stop_pid() {
  local label="$1"
  local file="$2"
=======
show_app() {
  start_bridge
  if pid_alive "$APP_PID" || [[ -n "$(app_pids)" ]]; then
    echo "popup: restarting visible instance"
    stop_app_processes >/dev/null
    rm -f "$APP_PID"
  fi
  start_app
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
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
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
<<<<<<< HEAD
  if pid_alive "$APP_PID"; then
    echo "popup: running pid $(cat "$APP_PID")"
=======
  local pids
  pids="$(app_pids | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  if pid_alive "$APP_PID"; then
    echo "popup: running pid $(cat "$APP_PID")"
  elif [[ -n "$pids" ]]; then
    echo "popup: running untracked pid(s) $pids"
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  else
    echo "popup: stopped"
  fi
  if port_open; then
    echo "bridge: listening on 127.0.0.1:$LK_UI_PORT"
  else
    echo "bridge: stopped"
  fi
  echo "hotkey: $LAWRENCE_HOTKEY"
  echo "hide-on-blur: $LAWRENCE_HIDE_ON_BLUR"
}

<<<<<<< HEAD
=======
doctor() {
  echo "== LAWRENCE processes =="
  ps -eo pid,rss,etime,comm,args 2>/dev/null \
    | grep -E "llama-server|ui_bridge\.py|lawrence-desktop" | grep -v grep \
    || echo "  (none of llama-server / ui_bridge / lawrence-desktop are running)"
  echo
  echo "== expected ports =="
  for p in 8190 "$LK_UI_PORT" 8766; do
    if ss -tlnp 2>/dev/null | grep -q ":$p "; then
      echo "  $p  LISTEN"
    else
      echo "  $p  -"
    fi
  done
  echo
  echo "== model health (via bridge) =="
  curl -s --max-time 4 "http://127.0.0.1:$LK_UI_PORT/health" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('  backend:', d.get('backend')); print('  modelHealth:', d.get('modelHealth')); print('  eventsUrl:', d.get('eventsUrl'))" 2>/dev/null \
    || echo "  bridge not answering on 127.0.0.1:$LK_UI_PORT"
  echo
  if pgrep -x ollama >/dev/null 2>&1; then
    echo "note: 'ollama serve' is running but LAWRENCE does not use it (it talks to"
    echo "      llama-server on :8190). Stop it with 'pkill ollama' to free RAM if unused."
  fi
}

>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
case "${1:-status}" in
  start)
    start_bridge
    start_app
    ;;
  stop|kill)
    stop_pid "popup" "$APP_PID"
    stop_pid "bridge" "$BRIDGE_PID"
    ;;
  restart)
    "$0" stop
    "$0" start
    ;;
<<<<<<< HEAD
  status)
    status
    ;;
=======
  show|open)
    show_app
    ;;
  status)
    status
    ;;
  doctor)
    doctor
    ;;
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
  logs)
    echo "== bridge =="
    tail -n 80 "$BRIDGE_LOG" 2>/dev/null || true
    echo "== popup =="
    tail -n 80 "$APP_LOG" 2>/dev/null || true
    ;;
  build)
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
<<<<<<< HEAD
    echo "usage: $0 start|stop|restart|status|logs|build|hotkey VALUE|config"
=======
    echo "usage: $0 start|show|stop|restart|status|doctor|logs|build|hotkey VALUE|config"
>>>>>>> e4fb94d (UI Working on WSL. Audio from kernal Broken.)
    exit 2
    ;;
esac
