#!/usr/bin/env bash
set -euo pipefail

if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
fi

if [[ "${ID:-}" != "ubuntu" && "${ID_LIKE:-}" != *"debian"* ]]; then
  echo "This installer is for Ubuntu/Debian-like systems. Detected: ${PRETTY_NAME:-unknown}"
  exit 1
fi

APT=(apt-get)
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required to install system packages. Re-run as root or install sudo."
    exit 1
  fi
  if [[ ! -t 0 ]]; then
    echo "System package installation needs sudo in an interactive terminal."
    echo "Run this manually:"
    echo "  cd $(pwd)"
    echo "  npm run deps:system"
    exit 1
  fi
  APT=(sudo apt-get)
fi

PACKAGES=(
  build-essential
  curl
  wget
  file
  pkg-config
  libglib2.0-dev
  libgtk-3-dev
  libwebkit2gtk-4.1-dev
  libjavascriptcoregtk-4.1-dev
  libsoup-3.0-dev
  libxdo-dev
  libayatana-appindicator3-dev
  librsvg2-dev
  libssl-dev
  libnspr4
  libnss3
  libasound2t64
)

echo "[deps] installing Ubuntu packages for Tauri + browser QA"
"${APT[@]}" update
"${APT[@]}" install -y "${PACKAGES[@]}"
