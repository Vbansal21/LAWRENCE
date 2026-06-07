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

npm run build:raw
