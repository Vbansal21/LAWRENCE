# LAWRENCE global hotkey — runs on the WINDOWS side so the shortcut is truly
# global (a shortcut registered inside WSLg only fires while a WSLg window has
# focus). On press it connects to the app's control socket inside WSL —
# WSL2 forwards localhost, so 127.0.0.1:<port> reaches the Linux listener —
# and sends "toggle". No wsl.exe spawn per keypress.
#
# Robustness (this script must NEVER become a CPU hog or an orphan):
#   * non-blocking PeekMessage + Sleep — uses ~0% CPU, never busy-loops on error
#   * self-terminates ~30s after the LAWRENCE control socket goes away
#     (i.e. when you stop the kernel) — so it cannot outlive the app
#   * a named mutex prevents a second copy registering the same key
#   * window title set so `lk stop` / desktopctl can find and kill it
param(
  [int]$Port = 8767,
  [int]$Modifiers = 6,   # MOD_CONTROL(2) | MOD_SHIFT(4)
  [int]$Vk = 0x4C        # 'L'
)
$ErrorActionPreference = "Stop"
$host.UI.RawUI.WindowTitle = "LAWRENCE-GlobalHotkey"

$created = $false
$mutex = New-Object System.Threading.Mutex($true, "LAWRENCE_GlobalHotkey_$Port", [ref]$created)
if (-not $created) { return }   # another listener already owns this key

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class LkHk {
  [DllImport("user32.dll", SetLastError=true)] public static extern bool RegisterHotKey(IntPtr h, int id, uint mods, uint vk);
  [DllImport("user32.dll", SetLastError=true)] public static extern bool UnregisterHotKey(IntPtr h, int id);
  [DllImport("user32.dll")] public static extern bool PeekMessage(out MSG m, IntPtr h, uint min, uint max, uint remove);
  [StructLayout(LayoutKind.Sequential)] public struct MSG {
    public IntPtr hwnd; public uint message; public UIntPtr wParam; public IntPtr lParam;
    public uint time; public int pt_x; public int pt_y;
  }
}
"@

function Test-AppAlive {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $iar = $c.BeginConnect("127.0.0.1", $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(400)
    $c.Close()
    return $ok
  } catch { return $false }
}

# Don't register until the app is actually up (avoids a stray listener if the
# launcher fires before the control socket binds). Give it up to ~15s.
$waited = 0
while (-not (Test-AppAlive) -and $waited -lt 30) { Start-Sleep -Milliseconds 500; $waited++ }
if (-not (Test-AppAlive)) { $mutex.ReleaseMutex(); return }

$id = 0x4C4B
if (-not [LkHk]::RegisterHotKey([IntPtr]::Zero, $id, [uint32]$Modifiers, [uint32]$Vk)) {
  $mutex.ReleaseMutex(); return
}

$WM_HOTKEY = 0x0312
$PM_REMOVE = 1
$misses = 0
$lastCheck = [DateTime]::UtcNow
try {
  while ($true) {
    $msg = New-Object LkHk+MSG
    if ([LkHk]::PeekMessage([ref]$msg, [IntPtr]::Zero, 0, 0, $PM_REMOVE)) {
      if ($msg.message -eq $WM_HOTKEY -and $msg.wParam.ToUInt32() -eq $id) {
        try {
          $c = New-Object System.Net.Sockets.TcpClient
          $c.Connect("127.0.0.1", $Port)
          $b = [System.Text.Encoding]::ASCII.GetBytes("toggle`n")
          $c.GetStream().Write($b, 0, $b.Length); $c.Close()
        } catch { }
      }
    } else {
      Start-Sleep -Milliseconds 200          # idle: ~0% CPU, never spins
    }
    # every ~10s, self-terminate if the app (control socket) has gone away
    if (([DateTime]::UtcNow - $lastCheck).TotalSeconds -ge 10) {
      $lastCheck = [DateTime]::UtcNow
      if (Test-AppAlive) { $misses = 0 } else { $misses++ }
      if ($misses -ge 3) { break }           # gone ~30s → exit, don't orphan
    }
  }
} finally {
  [LkHk]::UnregisterHotKey([IntPtr]::Zero, $id) | Out-Null
  $mutex.ReleaseMutex()
}
