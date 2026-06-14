#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash -n scripts/desktopctl.sh
python3 -m json.tool package.json >/tmp/lawrence-desktop-package-check.json

python3 - <<'PY'
import json
from pathlib import Path

package = json.loads(Path("package.json").read_text())
scripts = package.get("scripts", {})
required_scripts = {
    "popup": "bash scripts/desktopctl.sh start",
    "popup:show": "bash scripts/desktopctl.sh show",
    "popup:status": "bash scripts/desktopctl.sh status",
    "popup:doctor": "bash scripts/desktopctl.sh doctor",
    "services:start": "bash scripts/desktopctl.sh services-start",
    "services:stop": "bash scripts/desktopctl.sh services-stop",
    "services:restart": "bash scripts/desktopctl.sh services-restart",
    "host:config": "bash scripts/desktopctl.sh host-config",
    "host:config:write": "bash scripts/desktopctl.sh host-config --write",
    "host:install-plan": "bash scripts/desktopctl.sh host-install-plan",
    "host:install-plan:write": "bash scripts/desktopctl.sh host-install-plan --write",
    "host:windows:script": "node -e \"console.log('Run from Windows PowerShell: apps/desktop/host/windows/Build-HostUi.ps1')\"",
    "host:windows:start": "node -e \"console.log('Run from Windows PowerShell: apps/desktop/host/windows/Start-HostUi.ps1')\"",
    "host:windows:hotkey": "node -e \"console.log('Run from Windows PowerShell: apps/desktop/host/windows/Register-Hotkey.ps1')\"",
}
for name, command in required_scripts.items():
    if scripts.get(name) != command:
        raise SystemExit(f"package script mismatch for {name}: {scripts.get(name)!r}")

ctl = Path("scripts/desktopctl.sh").read_text()
main_rs = Path("src-tauri/src/main.rs").read_text()
required_fragments = [
    "bridge http: healthy on 127.0.0.1:$LK_UI_PORT",
    "bridge events:",
    "desktop HTTP bridge",
    "desktop SSE event stream",
    "non-LAWRENCE process; not touching it",
    "ollama server (not used by LAWRENCE)",
    "host ui config:",
    "\"uiRuntime\": \"host-native\"",
    "host install plan:",
    "host-to-wsl-ipc",
    "windows-arm64-tauri",
    "Build-HostUi.ps1",
    "Start-HostUi.ps1",
    "Register-Hotkey.ps1",
    "services-start",
    "services:restart",
    "loopback-http-sse-with-local-token",
]
missing = [frag for frag in required_fragments if frag not in ctl]
if missing:
    raise SystemExit("desktopctl runtime contract missing: " + ", ".join(missing))

required_rust_fragments = [
    "LAWRENCE_HOST_UI_CONFIG",
    "LOCALAPPDATA",
    'join("config").join("host-ui.json")',
    'config_str(&config, &["bridge", "httpUrl"])',
    'config_str(&config, &["ui", "hotkey"])',
    'ui.get("hideOnBlur")',
]
missing_rust = [frag for frag in required_rust_fragments if frag not in main_rs]
if missing_rust:
    raise SystemExit("Tauri host config contract missing: " + ", ".join(missing_rust))

host_script = Path("host/windows/Build-HostUi.ps1")
if not host_script.exists():
    raise SystemExit("Windows host build script missing")
script = host_script.read_text()
required_script_fragments = [
    "wsl.exe",
    "robocopy",
    "aarch64-pc-windows-msvc",
    "CARGO_TARGET_DIR",
    "LAWRENCE\\cache",
    "host-ui-src",
    "host-ui-install.json",
    "Start-HostUi.ps1",
    "Register-Hotkey.ps1",
    "Expected Windows ARM64 executable missing",
]
missing_script = [frag for frag in required_script_fragments if frag not in script]
if missing_script:
    raise SystemExit("Windows host build script contract missing: " + ", ".join(missing_script))

start_script = Path("host/windows/Start-HostUi.ps1")
if not start_script.exists():
    raise SystemExit("Windows host UI start script missing")
starter = start_script.read_text()
required_start_fragments = [
    "lawrence-desktop.exe",
    "services:start",
    "host:config:write",
    "Start-Process",
]
missing_start = [frag for frag in required_start_fragments if frag not in starter]
if missing_start:
    raise SystemExit("Windows host UI start script contract missing: " + ", ".join(missing_start))

hotkey_script = Path("host/windows/Register-Hotkey.ps1")
if not hotkey_script.exists():
    raise SystemExit("Windows hotkey helper missing")
hotkey = hotkey_script.read_text()
required_hotkey_fragments = [
    "RegisterHotKey",
    "Ctrl+Shift+L",
    "wsl.exe",
    "popup:show",
]
missing_hotkey = [frag for frag in required_hotkey_fragments if frag not in hotkey]
if missing_hotkey:
    raise SystemExit("Windows hotkey helper contract missing: " + ", ".join(missing_hotkey))

print("runtime contract ok")
PY

plan="$(bash scripts/desktopctl.sh host-install-plan)"
python3 - "$plan" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
phases = {item.get("id"): item for item in data.get("phases", [])}
target_dir = data.get("detected", {}).get("defaultWindowsInstallDir", "").lower()
checks = {
    "schemaVersion": data.get("schemaVersion") == 1,
    "intent": data.get("intent") == "install-or-update-host-native-ui-from-wsl-manager",
    "wslServices": phases.get("wsl-services", {}).get("status") == "implemented",
    "handoffConfig": phases.get("handoff-config", {}).get("status") == "implemented",
    "windowsTarget": data.get("target", {}).get("rustTarget") == "aarch64-pc-windows-msvc",
    "nativeBuildLocation": data.get("target", {}).get("buildLocation") == "windows-native",
    "hostNativeBuild": phases.get("host-native-build", {}).get("status") == "scripted-pending-host-run",
    "hostBuildScript": phases.get("host-native-build", {}).get("script") == "apps/desktop/host/windows/Build-HostUi.ps1",
    "hostInstall": phases.get("host-native-install", {}).get("status") == "scripted-pending-host-run",
    "hostRun": phases.get("host-native-run", {}).get("script") == "apps/desktop/host/windows/Start-HostUi.ps1",
    "ipcData": phases.get("host-to-wsl-ipc", {}).get("dataPlane") == "loopback-http-sse-with-local-token",
    "ipcControl": phases.get("host-to-wsl-ipc", {}).get("controlPlane") == "windows-host-helper-or-named-pipe",
    "notSystemProfile": not any(part in target_dir for part in ["/all users/", "/default/", "/default user/", "/public/"]),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("host install plan contract failed: " + ", ".join(failed))
PY

config="$(bash scripts/desktopctl.sh host-config)"
python3 - "$config" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
checks = {
    "schemaVersion": data.get("schemaVersion") == 1,
    "serviceManager": data.get("roles", {}).get("serviceManager") == "wsl",
    "uiRuntime": data.get("roles", {}).get("uiRuntime") == "host-native",
    "bridgeHttp": data.get("bridge", {}).get("httpUrl", "").startswith("http://127.0.0.1:"),
    "bridgeEvents": data.get("bridge", {}).get("eventsUrl", "").endswith("/events"),
    "managerCommands": "writeHostConfig" in data.get("manager", {}).get("commands", {}),
    "serviceStartCommand": data.get("manager", {}).get("commands", {}).get("startServices") == "npm run services:start",
    "serviceRestartCommand": data.get("manager", {}).get("commands", {}).get("restartServices") == "npm run services:restart",
    "hostExpectedRuntime": data.get("ui", {}).get("expectedRuntime") == "native-host",
    "nativeTarget": data.get("ui", {}).get("nativeTarget") == "windows-arm64-tauri",
    "startScript": data.get("ui", {}).get("windowsStartScript") == "apps/desktop/host/windows/Start-HostUi.ps1",
    "hotkeyHelper": data.get("ui", {}).get("windowsHotkeyHelper") == "apps/desktop/host/windows/Register-Hotkey.ps1",
    "dataPlane": data.get("security", {}).get("dataPlane") == "loopback-http-sse",
    "controlPlane": data.get("security", {}).get("controlPlane") == "windows-host-helper-or-named-pipe",
    "adjacentPolicy": data.get("adjacentServices", {}).get("policy") == "warn-only",
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("host config contract failed: " + ", ".join(failed))
PY
