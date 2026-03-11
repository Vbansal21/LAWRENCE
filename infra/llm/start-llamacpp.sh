#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
PID_FILE="$RUNTIME_DIR/llama-server.pid"
LOG_FILE="$RUNTIME_DIR/llama-server.log"

BIN_PATH="${LLAMACPP_BIN:-$ROOT_DIR/third_party/llama.cpp/build/bin/llama-server}"
MODEL_PATH="${LLAMACPP_MODEL:-$ROOT_DIR/models/Qwen3.5-4B-Q4_0.gguf}"
HOST="${LLAMACPP_HOST:-0.0.0.0}"
PORT="${LLAMACPP_PORT:-8080}"
CTX_SIZE="${LLAMACPP_CTX_SIZE:-4096}"
THREADS="${LLAMACPP_THREADS:-$(nproc)}"
GPU_LAYERS="${LLAMACPP_GPU_LAYERS:-0}"

mkdir -p "$RUNTIME_DIR"

if [ ! -x "$BIN_PATH" ]; then
  echo "llama-server not found or not executable: $BIN_PATH" >&2
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "model file not found: $MODEL_PATH" >&2
  exit 1
fi

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
  echo "llama-server already running (pid $(cat "$PID_FILE"))"
  exit 0
fi

nohup "$BIN_PATH" \
  --model "$MODEL_PATH" \
  --host "$HOST" \
  --port "$PORT" \
  --ctx-size "$CTX_SIZE" \
  --threads "$THREADS" \
  --n-gpu-layers "$GPU_LAYERS" \
  --no-webui >"$LOG_FILE" 2>&1 &

echo "$!" >"$PID_FILE"
echo "llama-server pid: $(cat "$PID_FILE")"

for i in {1..60}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "llama-server healthy: http://127.0.0.1:${PORT}"
    exit 0
  fi
  sleep 1
done

echo "llama-server failed health check. See log: $LOG_FILE" >&2
exit 1
