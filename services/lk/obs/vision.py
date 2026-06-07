"""Screen observer — capture → heuristic gate → distill → context store.

Runs as a daemon thread. Captures screen at LOW_RES every poll_interval seconds.
When pixel change exceeds threshold AND text is sufficiently novel, the frame is
distilled (two forms: compact line + detailed block) and written to ContextStore.

High-res capture triggers on significant change for image attachment to model turns.
The pending_hi path is consumed by the kernel at turn time.

Tunables poll_interval and min_write_secs are instance attributes so the CLI's
/set command can change them live without restarting the observer.  Gate thresholds
(vision_high, vision_pixel_min, vision_novelty_min) are on gate.gate_config — also
live-patchable.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..ctx import ContextStore, vision_gate
from ..ctx import distill as D
from ..ctx import gate as _gate
from .regions import RegionTracker, WinRect, screen_windows

# ── default tunables (instance attrs on VisionObserver, overridable live) ────

LOW_RES        = (640, 360)    # larger → tesseract reads text at Windows DPI scales
HIGH_RES       = (1280, 720)
POLL_INTERVAL  = 10.0          # seconds between capture attempts
MIN_WRITE_SECS = 60            # minimum gap between context writes

# Region pipeline: per-window OCR on the full-res frame, change-tracked per box.
REGION_EMA        = 0.4        # box coordinate smoothing (higher = snappier)
REGION_CHANGE_MIN = 0.06       # per-region pixel change (raw grey) to re-OCR
REGION_MIN_SIDE   = 80         # ignore region crops smaller than this


# ── frame snapshot (in-memory, for /obs display) ─────────────────────────────

@dataclass
class LatestFrame:
    ts: str
    change_score: float
    ocr_text: str
    heuristic_diff: str
    hi_path: Path | None = None


# ── screen capture ────────────────────────────────────────────────────────────

def _wsl_win_path(p: Path) -> str:
    return subprocess.check_output(["wslpath", "-w", str(p)], text=True).strip()


def _powershell_capture(out: Path, w: int, h: int) -> bool:
    if not shutil.which("powershell.exe"):
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    wp = _wsl_win_path(out)
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
        "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
        "$src=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
        "$g=[System.Drawing.Graphics]::FromImage($src);"
        "$g.CopyFromScreen($b.Left,$b.Top,0,0,$b.Size);"
        f"$dst=New-Object System.Drawing.Bitmap {w},{h};"
        "$g2=[System.Drawing.Graphics]::FromImage($dst);"
        "$g2.DrawImage($src,0,0,$dst.Width,$dst.Height);"
        f"$dst.Save('{wp}',[System.Drawing.Imaging.ImageFormat]::Png);"
        "$g.Dispose();$g2.Dispose();$src.Dispose();$dst.Dispose();"
    )
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    return r.returncode == 0 and out.exists()


def _scrot_capture(out: Path, w: int, h: int) -> bool:
    if not shutil.which("scrot"):
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["scrot", "--quality", "80", str(out)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0 or not out.exists():
        return False
    if shutil.which("convert"):
        subprocess.run(["convert", str(out), "-resize", f"{w}x{h}", str(out)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def _grim_capture(out: Path, w: int, h: int) -> bool:
    """Wayland screenshot via grim. Resizes with convert/sips if available."""
    if not shutil.which("grim") or not os.environ.get("WAYLAND_DISPLAY"):
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["grim", str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0 or not out.exists():
        return False
    if shutil.which("convert"):
        subprocess.run(["convert", str(out), "-resize", f"{w}x{h}!", str(out)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def _screencapture_macos(out: Path, w: int, h: int) -> bool:
    """macOS screenshot via screencapture + sips resize."""
    if sys.platform != "darwin" or not shutil.which("screencapture"):
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["screencapture", "-x", "-t", "png", str(out)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0 or not out.exists():
        return False
    if shutil.which("sips"):
        subprocess.run(
            ["sips", "-Z", str(max(w, h)), str(out)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    return True


def capture_frame(out: Path, w: int, h: int) -> bool:
    return (
        _powershell_capture(out, w, h)
        or _grim_capture(out, w, h)
        or _screencapture_macos(out, w, h)
        or _scrot_capture(out, w, h)
    )


def capture_now(out: Path) -> Path:
    """Synchronous high-res screenshot. Raises RuntimeError on failure."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if not capture_frame(out, *HIGH_RES):
        raise RuntimeError("screenshot capture failed — need powershell.exe (WSL) or scrot")
    return out


# ── full-resolution capture (for the region pipeline) ─────────────────────────

_PS_FULLRES = r'''
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
Add-Type @"
using System.Runtime.InteropServices;
public class LkDpi { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
"@
[void][LkDpi]::SetProcessDPIAware()
$b=[System.Windows.Forms.SystemInformation]::VirtualScreen
$src=New-Object System.Drawing.Bitmap $b.Width,$b.Height
$g=[System.Drawing.Graphics]::FromImage($src)
$g.CopyFromScreen($b.Left,$b.Top,0,0,$b.Size)
$src.Save('__OUT__',[System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose();$src.Dispose()
Write-Output "$($b.Width),$($b.Height),$($b.Left),$($b.Top)"
'''


def capture_fullres(out: Path) -> tuple[int, int, int, int] | None:
    """Capture the whole virtual screen at native (physical) resolution, DPI-aware
    so it aligns with regions.screen_windows(). Returns (width, height, origin_x,
    origin_y) — origin = virtual-screen top-left — or None on failure."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("powershell.exe"):
        ps = _PS_FULLRES.replace("__OUT__", _wsl_win_path(out))
        try:
            r = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                capture_output=True, text=True, timeout=20,
            )
        except Exception:
            return None
        if r.returncode != 0 or not out.exists():
            return None
        for line in reversed(r.stdout.splitlines()):
            nums = line.strip().split(",")
            if len(nums) == 4:
                try:
                    w, h, ox, oy = (int(x) for x in nums)
                    return (w, h, ox, oy)
                except ValueError:
                    continue
        return None
    # Wayland: grim captures the compositor's virtual screen at native size; origin (0,0)
    if shutil.which("grim") and os.environ.get("WAYLAND_DISPLAY"):
        try:
            r = subprocess.run(["grim", str(out)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0 and out.exists():
                from PIL import Image  # type: ignore
                with Image.open(out) as im:
                    return (im.width, im.height, 0, 0)
        except Exception:
            pass

    # macOS: screencapture captures the full display; origin (0,0)
    if sys.platform == "darwin" and shutil.which("screencapture"):
        try:
            r = subprocess.run(["screencapture", "-x", "-t", "png", str(out)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0 and out.exists():
                from PIL import Image  # type: ignore
                with Image.open(out) as im:
                    return (im.width, im.height, 0, 0)
        except Exception:
            pass

    # Linux/X11: scrot captures the root window at native size; origin (0,0)
    if shutil.which("scrot"):
        try:
            r = subprocess.run(["scrot", "--quality", "90", str(out)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0 and out.exists():
                from PIL import Image  # type: ignore
                with Image.open(out) as im:
                    return (im.width, im.height, 0, 0)
        except Exception:
            return None
    return None


# ── pixel change ──────────────────────────────────────────────────────────────

def _load_grey(path: Path) -> bytes | None:
    try:
        from PIL import Image  # type: ignore
        img = Image.open(path).convert("L").resize(LOW_RES)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        try:
            return path.read_bytes()
        except Exception:
            return None


def pixel_change_score(prev: bytes | None, curr: bytes | None) -> float:
    if prev is None or curr is None:
        return 1.0
    n = min(len(prev), len(curr), 8192)
    if n == 0:
        return 1.0
    return min(sum(abs(a - b) for a, b in zip(prev[:n], curr[:n])) / (n * 255), 1.0)


def _crop_signature(crop) -> bytes:
    """Raw 48×48 greyscale bytes of a region crop — for cheap per-region change
    detection (raw pixels, not PNG, so byte-diff tracks visual change)."""
    try:
        return crop.convert("L").resize((48, 48)).tobytes()
    except Exception:
        return b""


# ── OCR ───────────────────────────────────────────────────────────────────────

def run_ocr(path: Path, max_chars: int = 600) -> str:
    if shutil.which("tesseract"):
        try:
            r = subprocess.run(
                ["tesseract", str(path), "stdout", "--psm", "11", "--dpi", "150", "-l", "eng"],
                capture_output=True, text=True, timeout=15,
            )
            t = r.stdout.strip()
            if t:
                return t[:max_chars]
        except Exception:
            pass
    try:
        digest = hashlib.sha1(path.read_bytes()).hexdigest()[:12]
        return f"[ocr-unavailable:{digest}]"
    except Exception:
        return "[ocr-unavailable]"


# ── heuristic diff ────────────────────────────────────────────────────────────

_NOISE = {"the", "a", "an", "is", "to", "of", "in", "and", "or", "for", "with", "on", "at", "it"}


def heuristic_diff(prev_ocr: str, curr_ocr: str, score: float) -> str:
    """Human-readable summary of what changed between two frames."""
    if score < _gate.gate_config.vision_pixel_min:
        return ""
    prev_w = set(prev_ocr.lower().split()) - _NOISE if prev_ocr else set()
    curr_w = set(curr_ocr.lower().split()) - _NOISE if curr_ocr else set()
    appeared = sorted([w for w in (curr_w - prev_w) if len(w) > 2])[:5]
    vanished = sorted([w for w in (prev_w - curr_w) if len(w) > 2])[:5]
    level = "Significant layout change" if score >= _gate.gate_config.vision_high else "Minor change"
    parts = [f"{level} (Δ={score:.2f})"]
    if appeared:
        parts.append(f"appeared: {', '.join(appeared)}")
    if vanished:
        parts.append(f"removed: {', '.join(vanished)}")
    if not appeared and not vanished:
        parts.append("visual shift, no text delta")
    return "; ".join(parts)


# ── observer daemon ───────────────────────────────────────────────────────────

class VisionObserver(threading.Thread):
    """Daemon thread: polls screen, gates on significance, writes to ContextStore.

    poll_interval and min_write_secs are instance attributes — patch them live:
        observer.poll_interval  = 5.0   # check every 5s instead of 10s
        observer.min_write_secs = 30    # allow writes every 30s
    Gate thresholds (vision_high, etc.) live on gate.gate_config — also live.
    """
    daemon = True

    def __init__(
        self,
        tmp_dir: Path,
        ctx: ContextStore,
        on_event: Callable[[str, str], None] | None = None,
        poll_interval:  float = POLL_INTERVAL,
        min_write_secs: int   = MIN_WRITE_SECS,
    ) -> None:
        super().__init__(name="vision-obs")
        self.tmp_dir        = tmp_dir
        self._ctx           = ctx
        self._on_event      = on_event
        self._stop          = threading.Event()
        self._prev_bytes:   bytes | None = None
        self._prev_ocr:     str  = ""
        self._prev_written_ocr: str = ""
        self._last_written_time: float = 0.0
        self._idx           = 0
        self.active         = False
        self.latest:        LatestFrame | None = None
        self.pending_hi:    Path | None = None

        # live-patchable tunables
        self.poll_interval  = poll_interval
        self.min_write_secs = min_write_secs

        # region pipeline (per-window OCR). Disabled automatically if a frame
        # can't be segmented (no Pillow / no window source) — falls back to
        # whole-screen OCR. Tracker gives boxes stable ids + EMA smoothing.
        self.regions          = True
        self.region_change_min = REGION_CHANGE_MIN
        self._tracker         = RegionTracker(ema=REGION_EMA)
        self._regions_ok      = True   # flips False after a fallback, retried periodically

    def stop(self) -> None:
        self._stop.set()
        self.active = False

    def consume_pending_hi(self) -> Path | None:
        p, self.pending_hi = self.pending_hi, None
        return p

    def pull_hires(self, out: Path) -> Path | None:
        """Capture a fresh hi-res frame right now on model request."""
        out.parent.mkdir(parents=True, exist_ok=True)
        if capture_frame(out, *HIGH_RES):
            self.pending_hi = out
            return out
        return None

    def run(self) -> None:
        self.active = True
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop.wait(self.poll_interval)   # live-patchable interval

    def _tick(self) -> None:
        # ── cheap gate: low-res capture decides whether anything is worth a full read
        self._idx += 1
        low = self.tmp_dir / f"vis-{self._idx % 8}.png"
        if not capture_frame(low, *LOW_RES):
            return
        curr_bytes = _load_grey(low)
        score = pixel_change_score(self._prev_bytes, curr_bytes)
        self._prev_bytes = curr_bytes
        if score < _gate.gate_config.vision_pixel_min and score < 1.0:
            return   # nothing meaningful changed

        ts = datetime.now(timezone.utc).isoformat()
        # ── useful change → full read. Try per-region pipeline, else whole-screen.
        if self.regions and self._regions_ok:
            if self._tick_regions(ts, score):
                return
            self._regions_ok = False   # fell back; retry regions every ~30 frames
        elif self.regions and self._idx % 30 == 0:
            self._regions_ok = True
        self._tick_whole(ts, score, low)

    def _emit(self, ts: str, score: float, ocr: str, diff: str, hi: Path | None) -> None:
        """Shared: update /obs snapshot, gate, distill, write to context."""
        self.latest = LatestFrame(ts=ts, change_score=score, ocr_text=ocr,
                                  heuristic_diff=diff, hi_path=hi)
        now = time.monotonic()
        if vision_gate(score, self._prev_written_ocr, ocr):
            if now - self._last_written_time >= self.min_write_secs:
                compact, detailed = D.vision(ts, score, ocr, diff)
                self._ctx.append(ts=ts, kind="vision", compact=compact, detailed=detailed)
                self._prev_written_ocr = ocr
                self._last_written_time = now
                if self._on_event:
                    self._on_event("vision", compact)
        self._prev_ocr = ocr

    def _tick_whole(self, ts: str, score: float, low: Path) -> None:
        """Whole-screen OCR (fallback when regions are unavailable)."""
        curr_ocr = run_ocr(low)
        hi_path: Path | None = None
        if score >= _gate.gate_config.vision_high:
            hi = self.tmp_dir / f"vis-hi-{self._idx}.png"
            if capture_frame(hi, *HIGH_RES):
                curr_ocr = run_ocr(hi, max_chars=800)
                hi_path = self.pending_hi = hi
        diff = heuristic_diff(self._prev_ocr, curr_ocr, score)
        self._emit(ts, score, curr_ocr, diff, hi_path)

    def _tick_regions(self, ts: str, score: float) -> bool:
        """Per-window pipeline: full-res capture → window boxes → tracked regions →
        per-region change detection → OCR only changed regions → structured text.
        Returns False (caller falls back) if segmentation isn't possible."""
        try:
            from PIL import Image  # type: ignore
        except Exception:
            return False
        sw = screen_windows()
        if not sw:
            return False
        wins, _bounds = sw

        full = self.tmp_dir / f"vis-full-{self._idx % 4}.png"
        cap = capture_fullres(full)
        if not cap:
            return False
        img_w, img_h, ox, oy = cap
        try:
            img = Image.open(full).convert("RGB")
        except Exception:
            return False

        # map window rects (virtual coords) → image-pixel coords, clamp to frame
        rects: list[WinRect] = []
        for w in wins:
            l, t = max(0, w.left - ox), max(0, w.top - oy)
            r, b = min(img_w, w.right - ox), min(img_h, w.bottom - oy)
            if r - l >= REGION_MIN_SIDE and b - t >= REGION_MIN_SIDE:
                rects.append(WinRect(w.title, l, t, r, b))
        if not rects:
            return False

        tracked = self._tracker.update(rects)

        # OCR only the regions whose pixels changed (or first sight)
        for reg in tracked:
            l, t, r, b = reg.ibox
            l, t = max(0, l), max(0, t)
            r, b = min(img_w, r), min(img_h, b)
            if r - l < REGION_MIN_SIDE or b - t < REGION_MIN_SIDE:
                continue
            crop = img.crop((l, t, r, b))
            sig = _crop_signature(crop)
            if reg.sig is None or pixel_change_score(reg.sig, sig) >= self.region_change_min:
                cpath = self.tmp_dir / f"vis-reg-{reg.rid % 16}.png"
                try:
                    crop.save(cpath)
                    reg.ocr = run_ocr(cpath, max_chars=400)
                except Exception:
                    reg.ocr = reg.ocr or ""
                reg.sig = sig

        # assemble structured text, top-to-bottom / left-to-right, drop empties
        blocks: list[str] = []
        for reg in sorted(tracked, key=lambda x: (x.ibox[1], x.ibox[0])):
            txt = reg.ocr.strip()
            if txt and not txt.startswith("[ocr-unavailable"):
                blocks.append(f"[{reg.title[:60]}]\n{txt}")
        combined = "\n".join(blocks)
        if not combined:
            return False

        self.pending_hi = full   # full-res frame available for model attachment
        diff = heuristic_diff(self._prev_ocr, combined, score)
        self._emit(ts, score, combined, diff, full)
        return True
