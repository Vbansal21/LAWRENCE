#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$ROOT_DIR/infra/n8n/.env"
EXAMPLE_FILE="$ROOT_DIR/infra/n8n/.env.example"
COMPOSE_FILE="$ROOT_DIR/infra/n8n/docker-compose.yml"
WORKFLOW_DIR="$ROOT_DIR/modules/connectors/n8n/workflows"
RUNTIME_DIR="$ROOT_DIR/.runtime"
PID_FILE="$RUNTIME_DIR/n8n.pid"
LOG_FILE="$RUNTIME_DIR/n8n.log"
MODE="${N8N_RUNTIME:-auto}"
AUTO_ACTIVATE_CORE="${N8N_AUTO_ACTIVATE_CORE:-true}"

CORE_WORKFLOW_IDS=(
  "wf-00-agentic-kernel-loop"
  "wf-02-web-search"
  "wf-03-zettel-ingest-link"
  "wf-05-llamacpp-fast-slow"
)

mkdir -p "$RUNTIME_DIR"

if [ ! -f "$ENV_FILE" ]; then
  cp "$EXAMPLE_FILE" "$ENV_FILE"
  echo "Created $ENV_FILE from template. Update credentials/URLs as needed."
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${N8N_PORT:=5678}"
: "${N8N_HOST:=0.0.0.0}"
: "${N8N_BLOCK_ENV_ACCESS_IN_NODE:=false}"
: "${LAWRENCE_KERNEL_BASE:=http://127.0.0.1:8000}"
: "${LLAMACPP_BASE:=http://127.0.0.1:8080}"
: "${LMSTUDIO_BASE:=http://127.0.0.1:1234}"

if [[ "$MODE" != "docker" ]]; then
  LAWRENCE_KERNEL_BASE="${LAWRENCE_KERNEL_BASE/host.docker.internal/127.0.0.1}"
  LLAMACPP_BASE="${LLAMACPP_BASE/host.docker.internal/127.0.0.1}"
  LMSTUDIO_BASE="${LMSTUDIO_BASE/host.docker.internal/127.0.0.1}"
fi

export N8N_PORT N8N_HOST N8N_BLOCK_ENV_ACCESS_IN_NODE LAWRENCE_KERNEL_BASE LLAMACPP_BASE LMSTUDIO_BASE

docker_ready() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

n8n_cmd() {
  if command -v n8n >/dev/null 2>&1; then
    n8n "$@"
    return
  fi

  if [ -s "$HOME/.nvm/nvm.sh" ]; then
    local escaped
    escaped="$(printf '%q ' "$@")"
    # shellcheck disable=SC2086
    bash -lc "source \"$HOME/.nvm/nvm.sh\" && n8n ${escaped}"
    return
  fi

  echo "n8n CLI not found. Install n8n or load nvm before running this script." >&2
  exit 1
}

wait_for_health() {
  echo "Waiting for n8n health..."
  for i in {1..60}; do
    if curl -fsS "http://127.0.0.1:${N8N_PORT}/healthz" >/dev/null 2>&1; then
      echo "n8n is healthy"
      return 0
    fi
    sleep 2
  done
  echo "n8n health check timed out" >&2
  return 1
}

activate_core_local() {
  if [[ "$AUTO_ACTIVATE_CORE" != "true" ]]; then
    return 0
  fi
  for wid in "${CORE_WORKFLOW_IDS[@]}"; do
    n8n_cmd update:workflow --id="$wid" --active=true >/dev/null || true
  done
}

activate_core_docker() {
  if [[ "$AUTO_ACTIVATE_CORE" != "true" ]]; then
    return 0
  fi
  for wid in "${CORE_WORKFLOW_IDS[@]}"; do
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T n8n \
      n8n update:workflow --id="$wid" --active=true >/dev/null || true
  done
}

start_docker() {
  echo "Starting n8n (docker mode)..."
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
  wait_for_health

  echo "Importing workflows..."
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T n8n \
    n8n import:workflow --separate --input="/seed-workflows" >/dev/null

  activate_core_docker
  echo "Imported workflows from: $WORKFLOW_DIR"
}

start_local() {
  echo "Starting n8n (local mode)..."

  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
    echo "n8n already running (pid $(cat "$PID_FILE"))"
  elif curl -fsS "http://127.0.0.1:${N8N_PORT}/healthz" >/dev/null 2>&1; then
    echo "n8n is already serving on port ${N8N_PORT}"
  else
    if command -v n8n >/dev/null 2>&1; then
      nohup n8n start --host "$N8N_HOST" --port "$N8N_PORT" >"$LOG_FILE" 2>&1 &
    elif [ -s "$HOME/.nvm/nvm.sh" ]; then
      nohup bash -lc "source \"$HOME/.nvm/nvm.sh\" && n8n start --host \"$N8N_HOST\" --port \"$N8N_PORT\"" >"$LOG_FILE" 2>&1 &
    else
      echo "n8n CLI not found. Install n8n or source nvm before running this script." >&2
      exit 1
    fi
    echo "$!" >"$PID_FILE"
    echo "n8n pid: $(cat "$PID_FILE")"
  fi

  wait_for_health

  echo "Importing workflows..."
  n8n_cmd import:workflow --separate --input="$WORKFLOW_DIR" >/dev/null
  activate_core_local
  echo "Imported workflows from: $WORKFLOW_DIR"
}

case "$MODE" in
  docker)
    docker_ready || {
      echo "docker mode requested but docker is not available in this WSL distro." >&2
      exit 1
    }
    start_docker
    ;;
  local)
    start_local
    ;;
  auto)
    if docker_ready; then
      start_docker
    else
      start_local
    fi
    ;;
  *)
    echo "Unknown N8N_RUNTIME=$MODE (expected: auto|docker|local)" >&2
    exit 1
    ;;
esac

echo "Done. Open: http://127.0.0.1:${N8N_PORT}"
