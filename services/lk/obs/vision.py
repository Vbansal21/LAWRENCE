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
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..ctx import ContextStore, vision_gate
from ..ctx import distill as D
from ..ctx import gate as _gate

# ── default tunables (instance attrs on VisionObserver, overridable live) ────

LOW_RES        = (640, 360)    # larger → tesseract reads text at Windows DPI scales
HIGH_RES       = (1280, 720)
POLL_INTERVAL  = 10.0          # seconds between capture attempts
MIN_WRITE_SECS = 60            # minimum gap between context writes


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


def capture_frame(out: Path, w: int, h: int) -> bool:
    return _powershell_capture(out, w, h) or _scrot_capture(out, w, h)


def capture_now(out: Path) -> Path:
    """Synchronous high-res screenshot. Raises RuntimeError on failure."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if not capture_frame(out, *HIGH_RES):
        raise RuntimeError("screenshot capture failed — need powershell.exe (WSL) or scrot")
    return out


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
        self._idx += 1
        low = self.tmp_dir / f"vis-{self._idx % 8}.png"
        if not capture_frame(low, *LOW_RES):
            return

        curr_bytes = _load_grey(low)
        score = pixel_change_score(self._prev_bytes, curr_bytes)

        if score < _gate.gate_config.vision_pixel_min and self._prev_bytes is not None:
            return

        ts = datetime.now(timezone.utc).isoformat()
        curr_ocr = run_ocr(low)
        diff = heuristic_diff(self._prev_ocr, curr_ocr, score)
        hi_path: Path | None = None

        if score >= _gate.gate_config.vision_high:
            hi = self.tmp_dir / f"vis-hi-{self._idx}.png"
            if capture_frame(hi, *HIGH_RES):
                curr_ocr = run_ocr(hi, max_chars=800)
                hi_path  = hi
                self.pending_hi = hi

        self.latest = LatestFrame(
            ts=ts, change_score=score, ocr_text=curr_ocr,
            heuristic_diff=diff, hi_path=hi_path,
        )

        now = time.monotonic()
        if vision_gate(score, self._prev_written_ocr, curr_ocr):
            if now - self._last_written_time >= self.min_write_secs:
                compact, detailed = D.vision(ts, score, curr_ocr, diff)
                self._ctx.append(ts=ts, kind="vision", compact=compact, detailed=detailed)
                self._prev_written_ocr = curr_ocr
                self._last_written_time = now
                if self._on_event:
                    self._on_event("vision", compact)

        self._prev_bytes = curr_bytes
        self._prev_ocr   = curr_ocr
