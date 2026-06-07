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
  if [[ ! -x "$APP_BIN" ]]; then
    npm run build
  fi
  setsid env \
    LK_UI_PORT="$LK_UI_PORT" \
    LAWRENCE_HOTKEY="$LAWRENCE_HOTKEY" \
    LAWRENCE_HIDE_ON_BLUR="$LAWRENCE_HIDE_ON_BLUR" \
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

stop_pid() {
  local label="$1"
  local file="$2"
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
  if pid_alive "$APP_PID"; then
    echo "popup: running pid $(cat "$APP_PID")"
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
  status)
    status
    ;;
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
    echo "usage: $0 start|stop|restart|status|logs|build|hotkey VALUE|config"
    exit 2
    ;;
esac
