# LAWRENCE Windows Host UI

First native target: Windows on ARM64, with LAWRENCE services running in WSL
Ubuntu and the visible Tauri UI running natively on Windows.

Run from Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\Build-HostUi.ps1
```

After the build:

```powershell
powershell -ExecutionPolicy Bypass -File .\Start-HostUi.ps1
```

Defaults:

- WSL distro: `Ubuntu`
- WSL repo: `/home/user/LAWRENCE`
- Windows source cache: `%LOCALAPPDATA%\LAWRENCE\host-ui-src`
- build caches: `%LOCALAPPDATA%\LAWRENCE\cache`
- install dir: `%LOCALAPPDATA%\LAWRENCE`
- Rust target: `aarch64-pc-windows-msvc`

The script refreshes the WSL handoff config, mirrors `apps/desktop` into a
native Windows cache, installs npm dependencies, uses cached Rust/npm build
directories, builds the Tauri app for Windows ARM64, and copies the executable,
bundle artifacts, helper scripts, and `host-ui.json` into the install directory.

`Start-HostUi.ps1` starts only the WSL bridge/services and then launches the
native Windows executable. It does not start the WSLg popup.

Required on Windows:

- Node.js/npm for Windows ARM64
- Rust/rustup with MSVC support
- Microsoft C++ build tools / Visual Studio Build Tools
- WebView2 runtime
- WSL with the LAWRENCE repo available in the configured distro

Transport choice:

- Data plane: loopback HTTP/SSE to the WSL bridge (`127.0.0.1:8765` and
  `127.0.0.1:8766/events`) with local token auth planned.
- Control plane: Windows host helper or named-pipe-backed helper for complex
  lifecycle operations as the system grows. The current script uses `wsl.exe`
  for setup/config handoff.
