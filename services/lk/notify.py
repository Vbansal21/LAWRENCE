"""Desktop notification — best-effort, never raises (plan P4.T2).

Used for proactive findings surfaced unprompted. Tries notify-send (Linux),
then a PowerShell toast (WSL → Windows host). Silently no-ops when neither
exists or fails — a notification must never break the loop that sent it.
"""
from __future__ import annotations

import shutil
import subprocess


def notify(title: str, body: str = "") -> bool:
    title = (title or "LAWRENCE")[:120]
    body = (body or "")[:240]
    try:
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", "-a", "LAWRENCE", title, body],
                           timeout=5, capture_output=True)
            return True
        if shutil.which("powershell.exe"):          # WSL → Windows balloon tip
            safe_t = title.replace("'", "''")
            safe_b = body.replace("'", "''")
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n=New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon=[System.Drawing.SystemIcons]::Information;"
                "$n.Visible=$true;"
                f"$n.ShowBalloonTip(8000,'{safe_t}','{safe_b}',"
                "[System.Windows.Forms.ToolTipIcon]::Info);"
                "Start-Sleep -Seconds 1"
            )
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-Command", ps],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
    except Exception:
        pass
    return False
