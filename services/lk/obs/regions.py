"""Screen region detection + tracking for the vision pipeline.

Splits the screen into windows/sections so OCR runs per-region — and only on
regions that actually changed — and so each region's extracted text is tracked
over time instead of being re-derived from scratch every frame.

Region boxes come from the OS window manager:
  - WSL/Windows : PowerShell + user32 P/Invoke (EnumWindows / GetWindowRect),
                  DPI-aware so rects line up with the physical-pixel capture.
  - Linux X11   : `wmctrl -lG`.
When neither is available the caller falls back to a single whole-screen region
(the original behaviour), so vision still works headless or without a WM.

RegionTracker gives boxes a stable identity across frames (IoU + title match) and
smooths their coordinates with an EMA — "visually moving" boxes that glide rather
than jitter, and that keep their cached OCR when a window only nudges a little.
This is pure logic (no I/O) and is unit-tested.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


# ── raw window rectangle (virtual-screen pixel coords) ────────────────────────

@dataclass
class WinRect:
    title: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:  return self.right - self.left
    @property
    def height(self) -> int: return self.bottom - self.top
    @property
    def area(self) -> int:   return max(0, self.width) * max(0, self.height)
    @property
    def box(self) -> tuple[int, int, int, int]: return (self.left, self.top, self.right, self.bottom)


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


# ── tracked region (identity persists across frames) ──────────────────────────

@dataclass
class TrackedRegion:
    rid:   int
    title: str
    box:   tuple[float, float, float, float]      # EMA-smoothed (l, t, r, b)
    last_seen: int
    ocr:   str = ""                               # cached extracted text
    sig:   bytes | None = None                    # last crop signature (change detect)

    @property
    def ibox(self) -> tuple[int, int, int, int]:
        return tuple(int(round(v)) for v in self.box)  # type: ignore[return-value]


class RegionTracker:
    """Assigns stable ids to window rectangles across frames and EMA-smooths their
    boxes. ema in (0,1]: higher = snappier, lower = smoother/laggier."""

    def __init__(self, ema: float = 0.4, iou_match: float = 0.30, ttl: int = 4) -> None:
        self.ema       = ema
        self.iou_match = iou_match
        self.ttl       = ttl
        self._regions: dict[int, TrackedRegion] = {}
        self._next_id  = 1
        self._frame    = 0

    def _smooth(self, old: tuple, new: tuple) -> tuple:
        a = self.ema
        return tuple(a * n + (1 - a) * o for o, n in zip(old, new))

    def update(self, rects: list[WinRect]) -> list[TrackedRegion]:
        self._frame += 1
        unmatched = set(self._regions)

        for r in rects:
            nb = (float(r.left), float(r.top), float(r.right), float(r.bottom))
            # best existing region: same title preferred, else best IoU above threshold
            best_id, best_score = None, 0.0
            for rid, reg in self._regions.items():
                if rid not in unmatched:
                    continue
                iou = _iou(reg.box, nb)
                score = iou + (0.5 if reg.title == r.title and r.title else 0.0)
                if score > best_score and (iou >= self.iou_match or reg.title == r.title):
                    best_id, best_score = rid, score

            if best_id is not None:
                reg = self._regions[best_id]
                reg.box = self._smooth(reg.box, nb)
                reg.title = r.title or reg.title
                reg.last_seen = self._frame
                unmatched.discard(best_id)
            else:
                rid = self._next_id
                self._next_id += 1
                self._regions[rid] = TrackedRegion(rid=rid, title=r.title, box=nb,
                                                   last_seen=self._frame)

        # evict regions not seen for ttl frames
        for rid in [rid for rid in unmatched
                    if self._frame - self._regions[rid].last_seen > self.ttl]:
            del self._regions[rid]

        return [reg for reg in self._regions.values() if reg.last_seen == self._frame]

    def active(self) -> list[TrackedRegion]:
        return list(self._regions.values())


# ── OS window providers ───────────────────────────────────────────────────────

_PS_WINDOWS = r'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class LkW {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr l);
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
[void][LkW]::SetProcessDPIAware()
$res = New-Object System.Collections.ArrayList
$cb = [LkW+EnumWindowsProc]{
  param($h,$l)
  if ([LkW]::IsWindowVisible($h)) {
    $len = [LkW]::GetWindowTextLength($h)
    if ($len -gt 0) {
      $sb = New-Object System.Text.StringBuilder ($len + 1)
      [void][LkW]::GetWindowText($h, $sb, $sb.Capacity)
      $r = New-Object LkW+RECT
      [void][LkW]::GetWindowRect($h, [ref]$r)
      [void]$res.Add("$($r.Left),$($r.Top),$($r.Right),$($r.Bottom)`t$($sb.ToString())")
    }
  }
  return $true
}
[void][LkW]::EnumWindows($cb, [IntPtr]::Zero)
$vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
Write-Output "VS`t$($vs.Left)`t$($vs.Top)`t$($vs.Width)`t$($vs.Height)"
$res | ForEach-Object { Write-Output $_ }
'''

MIN_WIN_SIDE = 80     # ignore slivers / tooltips
OFFSCREEN    = -10000 # minimized windows report large negative coords


def _powershell_windows() -> tuple[list[WinRect], tuple[int, int, int, int]] | None:
    if not shutil.which("powershell.exe"):
        return None
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _PS_WINDOWS],
            capture_output=True, text=True, timeout=12,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
    except Exception:
        return None

    bounds = (0, 0, 0, 0)
    wins: list[WinRect] = []
    for line in r.stdout.splitlines():
        if line.startswith("VS\t"):
            try:
                _, l, t, w, h = line.split("\t")
                bounds = (int(l), int(t), int(w), int(h))
            except Exception:
                pass
            continue
        if "\t" not in line:
            continue
        coords, _, title = line.partition("\t")
        try:
            l, t, rr, b = (int(x) for x in coords.split(","))
        except Exception:
            continue
        if l < OFFSCREEN or t < OFFSCREEN:
            continue                         # minimized
        win = WinRect(title.strip(), l, t, rr, b)
        if win.width >= MIN_WIN_SIDE and win.height >= MIN_WIN_SIDE:
            wins.append(win)
    if not bounds[2]:
        return None
    return wins, bounds


def _wmctrl_windows() -> tuple[list[WinRect], tuple[int, int, int, int]] | None:
    if not shutil.which("wmctrl"):
        return None
    try:
        r = subprocess.run(["wmctrl", "-lG"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return None
    except Exception:
        return None
    wins: list[WinRect] = []
    max_r = max_b = 0
    for line in r.stdout.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        try:
            x, y, w, h = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
        except ValueError:
            continue
        title = parts[7]
        win = WinRect(title.strip(), x, y, x + w, y + h)
        if win.width >= MIN_WIN_SIDE and win.height >= MIN_WIN_SIDE:
            wins.append(win)
            max_r, max_b = max(max_r, x + w), max(max_b, y + h)
    if not wins:
        return None
    return wins, (0, 0, max_r, max_b)


MAX_REGIONS = 10      # cap OCR work per frame


def _dedup_overlapping(wins: list[WinRect], thresh: float = 0.85) -> list[WinRect]:
    """Drop windows largely occluded by an earlier (higher Z-order) one. Providers
    return windows topmost-first, so keeping the first of an overlapping pair keeps
    the visible window and discards the ones hidden behind it (e.g. several
    maximized apps that all report the full-screen rect)."""
    kept: list[WinRect] = []
    for w in wins:
        if any(_iou(w.box, k.box) >= thresh for k in kept):
            continue
        kept.append(w)
    return kept


def screen_windows() -> tuple[list[WinRect], tuple[int, int, int, int]] | None:
    """Return (windows, virtual-screen-bounds) in physical pixels, or None if no
    window-manager source is available. Bounds = (left, top, width, height).
    Overlapping/occluded windows are removed and the count is capped."""
    res = _powershell_windows() or _wmctrl_windows()
    if res is None:
        return None
    wins, bounds = res
    return _dedup_overlapping(wins)[:MAX_REGIONS], bounds
