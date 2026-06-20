"""Persistent Windows powershell host — the real N-78 bloat fix.

**Why this exists.** Spawning a fresh ``powershell.exe`` per screen capture and
per window probe runs ``Add-Type -AssemblyName System.Windows.Forms,System.Drawing``
EVERY time. Loading those .NET assemblies triggers the JIT/NGEN compiler chain
(``aspnet_compiler.exe``) and assembly self-repair (``msiexec`` / Windows
Installer). At a ~10s vision poll that accretes 100+ host processes over a
session — the user-reported "bloat process zombies". D-52 fixed the notification
and window-layout paths but NOT the screen-capture path, which is the most
frequent .NET-loading spawn of all.

**The fix.** Keep ONE long-lived powershell reading commands from stdin in a
loop: the assemblies are ``Add-Type``'d exactly ONCE at startup, then every
capture/probe is just a command to the already-warm runtime — no per-call .NET
load, no compiler/installer spawns, **one process total** for the whole session.

Robustness:
  * **single-flight** — a lock serializes commands (one in-flight at a time);
  * **self-healing** — a dead/wedged host is detected and respawned on next use;
  * **bounded** — each command has a wall-clock timeout; a timeout kills the
    (wedged) host so the next call starts clean;
  * **degrades (I4)** — if powershell is absent or won't start, ``run`` returns
    (False, "") and callers fall back to their other backends.

Pure stdlib. The host is a lazy module-level singleton (``host()``).
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

from ..debuglog import bump, debug

# WSL→powershell.exe needs a valid *Windows* CWD or the loader pops a 0xc0000142
# dialog; point it at C:\ (none of our scripts use a relative CWD).
_WIN_CWD = "/mnt/c" if os.path.isdir("/mnt/c") else None

_SENTINEL = "<<<LKDONE>>>"
_OK = "LK_OK"
_ERR = "LK_ERR"

# Bootstrap: load the assemblies + the P/Invoke class + the capture FUNCTIONS
# exactly ONCE, then serve one-line commands (function calls) in a loop. The hot
# paths (LkForeground every ~10s) thus never re-run Add-Type / the C# compiler —
# which was the aspnet_compiler.exe + msiexec storm. Each request is framed with
# OK/ERR + a sentinel so the reader knows the command finished.
_PREP = r'''
try { Add-Type -AssemblyName System.Windows.Forms,System.Drawing } catch {}
try {
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class LkN {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
} catch {}
try { [void][LkN]::SetProcessDPIAware() } catch {}
function LkScaled($p,$w,$h){
  $b=[System.Windows.Forms.SystemInformation]::VirtualScreen
  $src=New-Object System.Drawing.Bitmap $b.Width,$b.Height
  $g=[System.Drawing.Graphics]::FromImage($src)
  $g.CopyFromScreen($b.Left,$b.Top,0,0,$b.Size)
  $dst=New-Object System.Drawing.Bitmap ([int]$w),([int]$h)
  $g2=[System.Drawing.Graphics]::FromImage($dst)
  $g2.DrawImage($src,0,0,$dst.Width,$dst.Height)
  $dst.Save($p,[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose();$g2.Dispose();$src.Dispose();$dst.Dispose()
}
function LkFullres($p){
  $b=[System.Windows.Forms.SystemInformation]::VirtualScreen
  $src=New-Object System.Drawing.Bitmap $b.Width,$b.Height
  $g=[System.Drawing.Graphics]::FromImage($src)
  $g.CopyFromScreen($b.Left,$b.Top,0,0,$b.Size)
  $src.Save($p,[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose();$src.Dispose()
  Write-Output "$($b.Width),$($b.Height),$($b.Left),$($b.Top)"
}
function LkForeground($p){
  $h=[LkN]::GetForegroundWindow()
  $sb=New-Object System.Text.StringBuilder 512
  [void][LkN]::GetWindowText($h,$sb,512)
  $r=New-Object LkN+RECT
  [void][LkN]::GetWindowRect($h,[ref]$r)
  $w=$r.Right-$r.Left; $hh=$r.Bottom-$r.Top
  if($w -lt 40 -or $hh -lt 40 -or [LkN]::IsIconic($h)){ Write-Output 'ERR none'; return }
  $bmp=New-Object System.Drawing.Bitmap $w,$hh
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  try{ $g.CopyFromScreen($r.Left,$r.Top,0,0,$bmp.Size) }catch{ Write-Output 'ERR capture'; return }
  $bmp.Save($p,[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose();$bmp.Dispose()
  Write-Output "$($r.Left),$($r.Top),$w,$hh`t$($sb.ToString())"
}
function LkWindows(){
  $res=New-Object System.Collections.ArrayList
  $cb=[LkN+EnumWindowsProc]{ param($h,$l)
    if([LkN]::IsWindowVisible($h)){
      $len=[LkN]::GetWindowTextLength($h)
      if($len -gt 0){
        $sb=New-Object System.Text.StringBuilder ($len+1)
        [void][LkN]::GetWindowText($h,$sb,$sb.Capacity)
        $r=New-Object LkN+RECT
        [void][LkN]::GetWindowRect($h,[ref]$r)
        [void]$res.Add("$($r.Left),$($r.Top),$($r.Right),$($r.Bottom)`t$($sb.ToString())")
      }
    }
    return $true
  }
  [void][LkN]::EnumWindows($cb,[IntPtr]::Zero)
  $vs=[System.Windows.Forms.SystemInformation]::VirtualScreen
  Write-Output "VS`t$($vs.Left)`t$($vs.Top)`t$($vs.Width)`t$($vs.Height)"
  $res | ForEach-Object { Write-Output $_ }
}
'''

_LOOP = (
    "while ($true) {"
    "  $line = [Console]::In.ReadLine();"
    "  if ($line -eq $null) { break };"
    "  if ($line -eq 'LK_EXIT') { break };"
    "  try { Invoke-Expression $line; Write-Output '" + _OK + "' }"
    "  catch { Write-Output '" + _ERR + "' };"
    "  Write-Output '" + _SENTINEL + "';"
    "  [Console]::Out.Flush()"
    "}"
)

_BOOTSTRAP = _PREP + "\n" + _LOOP


def enabled() -> bool:
    """LK_WINHOST=0 forces the legacy per-call subprocess path (safety valve)."""
    return os.environ.get("LK_WINHOST", "1") not in ("0", "false", "")


class PowerShellHost:
    """One warm powershell.exe serving framed one-line commands over stdin."""

    def __init__(self, exe: str | None = None, *, bootstrap: str = _BOOTSTRAP,
                 cwd: str | None = _WIN_CWD, argv: list[str] | None = None):
        # exe defaults to powershell.exe; tests inject a fake interpreter via argv.
        self._exe = exe
        self._bootstrap = bootstrap
        self._cwd = cwd
        self._argv = argv          # full argv override (tests); None = build PS argv
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._q: "queue.Queue[str | None]" = queue.Queue()
        self.starts = 0          # how many host processes spawned (bloat metric)

    # ── lifecycle ────────────────────────────────────────────────────────────
    def _exe_path(self) -> str | None:
        if self._argv:
            return self._argv[0]
        if self._exe:
            return self._exe
        return shutil.which("powershell.exe")

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _start(self) -> bool:
        exe = self._exe_path()
        if not exe:
            return False
        try:
            argv = self._argv or [exe, "-NoProfile", "-NonInteractive",
                                   "-ExecutionPolicy", "Bypass", "-Command", self._bootstrap]
            self._proc = subprocess.Popen(
                argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, bufsize=1, cwd=self._cwd,
            )
        except Exception:
            self._proc = None
            return False
        self.starts += 1
        bump("winhost", "start")
        debug("winhost", "start", pid=getattr(self._proc, "pid", -1))
        self._q = queue.Queue()
        threading.Thread(target=self._read_loop, args=(self._proc,),
                         name="winhost-read", daemon=True).start()
        return True

    def _read_loop(self, proc: subprocess.Popen) -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                self._q.put(line.rstrip("\n"))
        except Exception:
            pass
        finally:
            self._q.put(None)   # EOF marker → run() learns the host died

    def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=1)
            except Exception:
                pass
        bump("winhost", "kill")

    # ── request/response ─────────────────────────────────────────────────────
    def run(self, script: str, *, timeout: float = 15.0) -> tuple[bool, str]:
        """Run a ONE-LINE command in the warm host. Returns (ok, output_text).

        ok is True iff the command completed without a PowerShell exception. A
        dead/wedged host is respawned (death) or killed (timeout) so the next
        call is clean. Degrades to (False, "") when powershell is unavailable.
        """
        script = script.replace("\n", " ").strip()
        with self._lock:
            if not self._alive():
                if not self._start():
                    return False, ""
            ok, out = self._exchange(script, timeout)
            if ok is None:                       # host died mid-command → one retry
                self._kill()
                if not self._start():
                    return False, ""
                ok, out = self._exchange(script, timeout)
                if ok is None:
                    self._kill()
                    return False, ""
            return ok, out

    def _exchange(self, script: str, timeout: float) -> tuple[bool | None, str]:
        """Write one command, read until the sentinel. (None, _) == host died."""
        try:
            assert self._proc is not None and self._proc.stdin is not None
            self._proc.stdin.write(script + "\n")
            self._proc.stdin.flush()
        except Exception:
            return None, ""
        deadline = time.monotonic() + timeout
        ok = False
        lines: list[str] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                bump("winhost", "timeout")
                self._kill()                     # wedged → drop it
                return False, "\n".join(lines)
            try:
                line = self._q.get(timeout=remaining)
            except queue.Empty:
                bump("winhost", "timeout")
                self._kill()
                return False, "\n".join(lines)
            if line is None:                     # EOF: the host process exited
                return None, "\n".join(lines)
            if line == _SENTINEL:
                bump("winhost", "served")
                return ok, "\n".join(lines)
            if line == _OK:
                ok = True
            elif line == _ERR:
                ok = False
            else:
                lines.append(line)

    def shutdown(self) -> None:
        with self._lock:
            if self._alive():
                try:
                    assert self._proc is not None and self._proc.stdin is not None
                    self._proc.stdin.write("LK_EXIT\n")
                    self._proc.stdin.flush()
                except Exception:
                    pass
            self._kill()


# ── module singleton ─────────────────────────────────────────────────────────
_HOST: PowerShellHost | None = None
_HOST_LOCK = threading.Lock()


def host() -> PowerShellHost:
    global _HOST
    with _HOST_LOCK:
        if _HOST is None:
            _HOST = PowerShellHost()
        return _HOST


def available() -> bool:
    """True iff a powershell.exe exists to host (callers degrade otherwise)."""
    return host()._exe_path() is not None


def shutdown() -> None:
    """Stop the singleton host if running (idempotent)."""
    global _HOST
    with _HOST_LOCK:
        if _HOST is not None:
            _HOST.shutdown()


# Belt-and-braces: the host self-exits on stdin EOF when its parent dies, but
# also reap it explicitly at interpreter exit so a clean stop leaves nothing.
import atexit as _atexit  # noqa: E402
_atexit.register(shutdown)
