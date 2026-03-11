#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/n8n.pid"
PORT="${N8N_PORT:-5678}"

if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
  echo "n8n health: OK (http://127.0.0.1:${PORT})"
else
  echo "n8n health: DOWN (http://127.0.0.1:${PORT})"
fi

if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" >/dev/null 2>&1; then
    echo "n8n pid file: running (pid $pid)"
  else
    echo "n8n pid file: stale (pid $pid)"
  fi
else
  echo "n8n pid file: not present"
fi

running_pid="$(pgrep -f 'n8n start --host' | head -n1 || true)"
if [ -n "$running_pid" ]; then
  echo "n8n process scan: running (pid $running_pid)"
else
  echo "n8n process scan: no active n8n start process found"
fi
