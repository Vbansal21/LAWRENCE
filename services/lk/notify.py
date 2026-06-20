"""Desktop notification — best-effort, never raises (plan P4.T2).

Used for proactive findings + reminders surfaced unprompted. Tries notify-send
(Linux), then a PowerShell balloon (WSL → Windows host). Silently no-ops when
neither exists or fails — a notification must never break the loop that sent it.

Storm control (root-causes the aspnet_compiler/powershell/msiexec process bloat
seen on the Windows host): every PowerShell balloon spawns a fresh, heavyweight
``powershell.exe`` that loads System.Windows.Forms — which drags in the .NET
JIT/NGEN compiler chain and assembly self-repair. A burst of notifications (e.g.
a proactive flurry) therefore spawns a burst of compiler/installer processes. We
gate that here, at the single choke point, with three independent limits:

  * **dedupe**   — identical (title, body) within ``_DEDUPE_S`` is dropped.
  * **throttle** — a global minimum spacing ``_MIN_INTERVAL_S`` between balloons.
  * **cap**      — at most ``_MAX_INFLIGHT`` PowerShell balloons alive at once;
                   finished ones are reaped each call so the cap is truthful.

All three are counted via ``debuglog`` so /metrics + tests can prove the gate.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time

from .debuglog import bump, debug
from .policy import PolicyState, audit

# Windows-valid CWD for powershell.exe (avoids the 0xc0000142 dialog under WSL).
_WIN_CWD = "/mnt/c" if os.path.isdir("/mnt/c") else None

# Storm-control knobs (env-overridable so the launcher/tests can tune them).
_MIN_INTERVAL_S = float(os.environ.get("LK_NOTIFY_MIN_INTERVAL", "4"))
_DEDUPE_S = float(os.environ.get("LK_NOTIFY_DEDUPE", "120"))
_MAX_INFLIGHT = int(os.environ.get("LK_NOTIFY_MAX_INFLIGHT", "3"))

_LOCK = threading.Lock()
_last_fired = 0.0
_recent: dict[str, float] = {}            # key -> monotonic time last shown
_inflight: list[subprocess.Popen] = []    # live powershell balloon processes


def _reap() -> int:
    """Drop finished balloon processes; return how many are still alive."""
    _inflight[:] = [p for p in _inflight if p.poll() is None]
    return len(_inflight)


def _gate(title: str, body: str) -> bool:
    """Apply dedupe + throttle + cap. True ⇒ caller may spawn a balloon now."""
    global _last_fired
    now = time.monotonic()
    key = f"{title}{body}"
    with _LOCK:
        # prune dedupe table so it cannot grow unbounded
        for k, t in list(_recent.items()):
            if now - t > _DEDUPE_S:
                _recent.pop(k, None)
        if key in _recent:
            bump("notify", "deduped")
            debug("notify", "deduped", title=title)
            return False
        if now - _last_fired < _MIN_INTERVAL_S:
            bump("notify", "throttled")
            debug("notify", "throttled", since=round(now - _last_fired, 2))
            return False
        if _reap() >= _MAX_INFLIGHT:
            bump("notify", "capped")
            debug("notify", "capped", inflight=len(_inflight))
            return False
        _last_fired = now
        _recent[key] = now
        return True


def notify(title: str, body: str = "") -> bool:
    decision = PolicyState.current().allow("notification")
    audit("notification", decision, f"{title}\n{body}")
    if not decision.allowed:
        debug("notify", "policy-denied", title=title)
        return False
    title = (title or "LAWRENCE")[:120]
    body = (body or "")[:240]
    try:
        if shutil.which("notify-send"):
            # notify-send is cheap (no .NET) — only dedupe/throttle, no cap needed.
            if not _gate(title, body):
                return False
            subprocess.run(["notify-send", "-a", "LAWRENCE", title, body],
                           timeout=5, capture_output=True)
            bump("notify", "sent_linux")
            debug("notify", "sent", via="notify-send", title=title)
            return True
        if shutil.which("powershell.exe"):          # WSL → Windows balloon tip
            if not _gate(title, body):
                return False
            safe_t = title.replace("'", "''")
            safe_b = body.replace("'", "''")
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n=New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon=[System.Drawing.SystemIcons]::Information;"
                "$n.Visible=$true;"
                f"$n.ShowBalloonTip(8000,'{safe_t}','{safe_b}',"
                "[System.Windows.Forms.ToolTipIcon]::Info);"
                "Start-Sleep -Seconds 1;$n.Dispose()"
            )
            proc = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=_WIN_CWD,
            )
            with _LOCK:
                _inflight.append(proc)
            bump("notify", "sent_windows")
            debug("notify", "sent", via="powershell", inflight=len(_inflight), title=title)
            return True
    except Exception as exc:
        debug("notify", "error", err=exc)
    return False
