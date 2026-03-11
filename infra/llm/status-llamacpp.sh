#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/llama-server.pid"
PORT="${LLAMACPP_PORT:-8080}"

if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "llama-server health: OK (http://127.0.0.1:${PORT})"
else
  echo "llama-server health: DOWN (http://127.0.0.1:${PORT})"
fi

if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" >/dev/null 2>&1; then
    echo "llama-server pid file: running (pid $pid)"
  else
    echo "llama-server pid file: stale (pid $pid)"
  fi
else
  echo "llama-server pid file: not present"
fi

running_pid="$(pgrep -f 'llama-server --model' | head -n1 || true)"
if [ -n "$running_pid" ]; then
  echo "llama-server process scan: running (pid $running_pid)"
else
  echo "llama-server process scan: no active llama-server process found"
fi
