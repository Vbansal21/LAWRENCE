param(
  [string]$WslDistro = "Ubuntu",
  [string]$WslRepo = "/home/user/LAWRENCE",
  [string]$WorkDir = "$env:LOCALAPPDATA\LAWRENCE\host-ui-src",
  [string]$InstallDir = "$env:LOCALAPPDATA\LAWRENCE",
  [switch]$SkipBuild,
  [switch]$CreateShortcut
)

$ErrorActionPreference = "Stop"

function Require-Command($Name, $Hint) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name is required. $Hint"
  }
}

function WslPathToUnc($Distro, $Path) {
  $relative = $Path.TrimStart("/") -replace "/", "\"
  return "\\wsl.localhost\$Distro\$relative"
}

$cacheRoot = Join-Path $env:LOCALAPPDATA "LAWRENCE\cache"
$npmCache = Join-Path $cacheRoot "npm"
$cargoHome = Join-Path $cacheRoot "cargo-home"
$rustupHome = Join-Path $cacheRoot "rustup"
$targetDir = Join-Path $cacheRoot "cargo-target"
$bundleDir = Join-Path $InstallDir "bundle"
$configDir = Join-Path $InstallDir "config"
$scriptsDir = Join-Path $InstallDir "scripts"

New-Item -ItemType Directory -Force -Path $WorkDir, $InstallDir, $bundleDir, $configDir, $scriptsDir, $npmCache, $cargoHome, $rustupHome, $targetDir | Out-Null

Require-Command "wsl.exe" "Install WSL and the Ubuntu distro first."
Require-Command "node" "Install Node.js for Windows ARM64."
Require-Command "npm" "Install Node.js/npm for Windows ARM64."
Require-Command "cargo" "Install Rust for Windows with MSVC support."
Require-Command "rustup" "Install Rust through rustup for Windows."

$wslDesktop = Join-Path (WslPathToUnc $WslDistro $WslRepo) "apps\desktop"
if (-not (Test-Path $wslDesktop)) {
  throw "Cannot read WSL desktop path: $wslDesktop"
}

Write-Host "[LAWRENCE] Refreshing WSL host UI config"
wsl.exe -d $WslDistro --cd "$WslRepo/apps/desktop" -- bash scripts/desktopctl.sh host-config --write | Write-Host

Write-Host "[LAWRENCE] Syncing desktop source into Windows cache: $WorkDir"
robocopy $wslDesktop $WorkDir /MIR /XD node_modules src-tauri\target /XF .DS_Store | Out-Host
if ($LASTEXITCODE -gt 7) {
  throw "robocopy failed with exit code $LASTEXITCODE"
}

$env:npm_config_cache = $npmCache
$env:CARGO_HOME = $cargoHome
$env:RUSTUP_HOME = $rustupHome
$env:CARGO_TARGET_DIR = $targetDir

Push-Location $WorkDir
try {
  if (Test-Path "package-lock.json") {
    npm ci
  } else {
    npm install
  }

  rustup target add aarch64-pc-windows-msvc

  if (-not $SkipBuild) {
    npm run build:raw -- --target aarch64-pc-windows-msvc
  }

  $built = Join-Path $targetDir "aarch64-pc-windows-msvc\release"
  if (-not (Test-Path $built)) {
    throw "Expected Windows ARM64 target output missing: $built"
  }

  $exe = Join-Path $built "lawrence-desktop.exe"
  if (-not (Test-Path $exe)) {
    throw "Expected Windows ARM64 executable missing: $exe"
  }
  Copy-Item $exe $InstallDir -Force
  if (Test-Path (Join-Path $built "bundle")) {
    Copy-Item (Join-Path $built "bundle\*") $bundleDir -Recurse -Force
  }

  $hostConfigWsl = WslPathToUnc $WslDistro "$WslRepo/.runtime/desktop/host-ui.json"
  if (Test-Path $hostConfigWsl) {
    Copy-Item $hostConfigWsl (Join-Path $configDir "host-ui.json") -Force
  }
  Copy-Item (Join-Path $WorkDir "host\windows\*.ps1") $scriptsDir -Force

  $summary = @{
    schemaVersion = 1
    target = "windows-arm64-tauri"
    installedAt = (Get-Date).ToUniversalTime().ToString("o")
    installDir = $InstallDir
    workDir = $WorkDir
    cacheRoot = $cacheRoot
    executable = (Join-Path $InstallDir "lawrence-desktop.exe")
    config = (Join-Path $configDir "host-ui.json")
    startScript = (Join-Path $scriptsDir "Start-HostUi.ps1")
    hotkeyHelper = (Join-Path $scriptsDir "Register-Hotkey.ps1")
    wslDistro = $WslDistro
    wslRepo = $WslRepo
  }
  $summary | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $InstallDir "host-ui-install.json")

  if ($CreateShortcut) {
    $shortcutDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    $shortcut = Join-Path $shortcutDir "LAWRENCE.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($shortcut)
    $link.TargetPath = (Join-Path $InstallDir "lawrence-desktop.exe")
    $link.WorkingDirectory = $InstallDir
    $link.Save()
  }

  Write-Host "[LAWRENCE] Host UI install summary:"
  Get-Content (Join-Path $InstallDir "host-ui-install.json")
}
finally {
  Pop-Location
}
