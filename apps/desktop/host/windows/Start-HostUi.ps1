param(
  [string]$WslDistro = "Ubuntu",
  [string]$WslDesktop = "/home/user/LAWRENCE/apps/desktop",
  [string]$InstallDir = "$env:LOCALAPPDATA\LAWRENCE"
)

$ErrorActionPreference = "Stop"

$exe = Join-Path $InstallDir "lawrence-desktop.exe"
if (-not (Test-Path $exe)) {
  throw "LAWRENCE host UI is not installed at $exe. Run Build-HostUi.ps1 first."
}

wsl.exe -d $WslDistro --cd $WslDesktop -- npm run services:start | Write-Host
wsl.exe -d $WslDistro --cd $WslDesktop -- npm run host:config:write | Write-Host

Start-Process -FilePath $exe -WorkingDirectory $InstallDir
