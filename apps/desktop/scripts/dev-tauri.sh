#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo is missing. Run: npm run bootstrap"
  exit 1
fi

if ! command -v pkg-config >/dev/null 2>&1; then
  echo "pkg-config is missing. Run: npm run deps:system"
  exit 1
fi

BRIDGE_PORT="${LK_UI_PORT:-8765}"
BRIDGE_PID=""
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

npm run dev:raw
