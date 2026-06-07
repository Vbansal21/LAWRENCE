#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-1423}"
BRIDGE_PORT="${LK_UI_PORT:-8765}"
BRIDGE_PID=""

if [[ "${LK_UI_BRIDGE:-1}" != "0" ]]; then
  if ! python3 - "$BRIDGE_PORT" <<'PY'
import socket, sys
try:
    with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=0.2):
        pass
except OSError:
    raise SystemExit(1)
PY
  then
    python3 scripts/ui_bridge.py --port "$BRIDGE_PORT" &
    BRIDGE_PID="$!"
    trap '[[ -n "$BRIDGE_PID" ]] && kill "$BRIDGE_PID" 2>/dev/null || true' EXIT
  fi
fi

echo "[web] http://127.0.0.1:${PORT}"
python3 -m http.server "$PORT" --directory web
