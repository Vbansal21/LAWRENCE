#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[bootstrap] desktop UI"

if ! command -v cargo >/dev/null 2>&1; then
  if [[ -f "$HOME/.cargo/env" ]]; then
    # shellcheck disable=SC1091
    . "$HOME/.cargo/env"
  fi
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "[bootstrap] installing Rust with rustup (user-local)"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
fi

echo "[bootstrap] cargo: $(cargo --version)"
echo "[bootstrap] npm install"
npm install

echo
echo "[bootstrap] checking native GUI dependencies"
if bash scripts/doctor.sh; then
  echo "[bootstrap] ready for npm run dev"
else
  echo
  echo "[bootstrap] user-local setup is complete, but native Ubuntu packages are missing."
  echo "Run this in a terminal with sudo access:"
  echo "  cd $ROOT"
  echo "  npm run deps:system"
  exit 1
fi
