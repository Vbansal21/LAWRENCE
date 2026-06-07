#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
fi

missing=0

check_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf "ok   %-18s %s\n" "$name" "$(command -v "$name")"
  else
    printf "miss %-18s\n" "$name"
    missing=1
  fi
}

check_pkg() {
  local name="$1"
  if dpkg -s "$name" >/dev/null 2>&1; then
    printf "ok   %-32s\n" "$name"
  else
    printf "miss %-32s\n" "$name"
    missing=1
    MISSING_APT+=("$name")
  fi
}

MISSING_APT=()

echo "[desktop doctor]"
check_cmd node
check_cmd npm
check_cmd cargo
check_cmd rustc
check_cmd cc
check_cmd pkg-config

if [[ -f package-lock.json ]]; then
  echo "ok   package-lock.json"
else
  echo "miss package-lock.json"
  missing=1
fi

echo
echo "[ubuntu native packages]"
if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  echo "os   ${PRETTY_NAME:-unknown}"
fi

check_pkg pkg-config
check_pkg libglib2.0-dev
check_pkg libgtk-3-dev
check_pkg libwebkit2gtk-4.1-dev
check_pkg libjavascriptcoregtk-4.1-dev
check_pkg libsoup-3.0-dev
check_pkg libxdo-dev
check_pkg libayatana-appindicator3-dev
check_pkg librsvg2-dev
check_pkg libssl-dev
check_pkg libnspr4
check_pkg libnss3
check_pkg libasound2t64

echo
if (( ${#MISSING_APT[@]} > 0 )); then
  echo "Missing apt packages:"
  printf "  %s\n" "${MISSING_APT[@]}"
  echo
  echo "Install them with:"
  echo "  npm run deps:system"
fi

exit "$missing"
