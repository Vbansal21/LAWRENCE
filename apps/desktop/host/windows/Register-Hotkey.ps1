param(
  [string]$WslDistro = "Ubuntu",
  [string]$WslDesktop = "/home/user/LAWRENCE/apps/desktop"
)

$ErrorActionPreference = "Stop"

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class LawrenceHotkey {
  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool UnregisterHotKey(IntPtr hWnd, int id);

  [DllImport("user32.dll")]
  public static extern sbyte GetMessage(out MSG lpMsg, IntPtr hWnd, uint wMsgFilterMin, uint wMsgFilterMax);

  [StructLayout(LayoutKind.Sequential)]
  public struct MSG {
    public IntPtr hwnd;
    public uint message;
    public UIntPtr wParam;
    public IntPtr lParam;
    public uint time;
    public int pt_x;
    public int pt_y;
  }
}
"@

$id = 0x4C4B
$modControl = 0x0002
$modShift = 0x0004
$vkL = 0x4C
$wmHotkey = 0x0312

if (-not [LawrenceHotkey]::RegisterHotKey([IntPtr]::Zero, $id, $modControl -bor $modShift, $vkL)) {
  throw "Could not register Ctrl+Shift+L. Another app may already own it."
}

Write-Host "[LAWRENCE] Ctrl+Shift+L registered on Windows. Press Ctrl+C to stop."
try {
  while ($true) {
    $msg = New-Object LawrenceHotkey+MSG
    $result = [LawrenceHotkey]::GetMessage([ref]$msg, [IntPtr]::Zero, 0, 0)
    if ($result -eq 0) {
      break
    }
    if ($msg.message -eq $wmHotkey -and $msg.wParam.ToUInt32() -eq $id) {
      Start-Process -WindowStyle Hidden -FilePath "wsl.exe" -ArgumentList @(
        "-d", $WslDistro,
        "--cd", $WslDesktop,
        "--", "bash", "scripts/desktopctl.sh", "toggle"
      )
    }
  }
}
finally {
  [LawrenceHotkey]::UnregisterHotKey([IntPtr]::Zero, $id) | Out-Null
}
