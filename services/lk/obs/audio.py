"""Audio observer — record → VAD → transcribe → gate → distill → context store.

Runs as a daemon thread. Records WINDOW_SECONDS of audio every POLL_INTERVAL
seconds. VAD via RMS energy. Transcription via faster-whisper or whisper-cli.
Only segments that pass SignificanceGate (speech, non-duplicate) are written.
WAV files for recent speech are retained for native Gemma audio attachment.
"""
from __future__ import annotations

import array
import math
import shutil
import subprocess
import threading
import wave
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from ..ctx import ContextStore, audio_gate
from ..ctx import distill as D

# ── tunables ──────────────────────────────────────────────────────────────────

WINDOW_SECONDS       = 4.0
POLL_INTERVAL        = 4.0
SAMPLE_RATE          = 16_000
SILENCE_DB           = -42.0
MAX_WAV_KEEP         = 5
MAX_RECENT_KEEP      = 12   # recent transcripts kept for dedup gate


# ── recording ─────────────────────────────────────────────────────────────────

def _arecord(out: Path, secs: float) -> bool:
    if not shutil.which("arecord"):
        return False
    r = subprocess.run(
        ["arecord", "-q", "-f", "S16_LE", "-r", str(SAMPLE_RATE),
         "-c", "1", "-d", str(int(secs)), str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0 and out.exists()


def _ffmpeg(out: Path, secs: float) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "pulse", "-i", "default",
         "-t", str(secs), "-ac", "1", "-ar", str(SAMPLE_RATE), str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0 and out.exists()


def record_window(out: Path, secs: float) -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    return _arecord(out, secs) or _ffmpeg(out, secs)


def record_now(out: Path, secs: float) -> Path:
    """Blocking synchronous record. Raises RuntimeError on failure."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if not record_window(out, secs):
        raise RuntimeError("audio recording failed — need arecord or ffmpeg+pulseaudio")
    return out


# ── VAD ───────────────────────────────────────────────────────────────────────

def rms_db(wav: Path) -> float | None:
    try:
        with wave.open(str(wav), "rb") as wf:
            if wf.getsampwidth() != 2:
                return None
            raw = wf.readframes(wf.getnframes())
        samples = array.array("h", raw)
        if not samples:
            return None
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        return -96.0 if rms < 1 else 20 * math.log10(rms / 32768.0)
    except Exception:
        return None


# ── transcription ─────────────────────────────────────────────────────────────

_whisper_model: object = None   # WhisperModel singleton — loaded once on first use


def _get_whisper() -> object:
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel  # type: ignore
            _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception:
            pass
    return _whisper_model


def _faster_whisper(wav: Path) -> str | None:
    m = _get_whisper()
    if m is None:
        return None
    try:
        segs, _ = m.transcribe(str(wav), language=None)  # type: ignore[union-attr]
        text = " ".join(s.text.strip() for s in segs).strip()
        return text or None
    except Exception:
        return None


def _whisper_cli(wav: Path) -> str | None:
    cache = Path.home() / ".cache" / "whisper"
    model = next(
        (str(p) for p in [cache / "ggml-base.en.bin", cache / "ggml-base.bin"] if p.exists()),
        None,
    )
    for binary in ("whisper-cli", "whisper"):
        if not shutil.which(binary):
            continue
        cmd = [binary, "--no-timestamps", "-l", "auto", "-f", str(wav)]
        if model:
            cmd = [binary, "-m", model, "--no-timestamps", "-l", "auto", "-f", str(wav)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            continue
    return None


def transcribe(wav: Path) -> str:
    return _faster_whisper(wav) or _whisper_cli(wav) or ""


# ── observer daemon ───────────────────────────────────────────────────────────

class AudioObserver(threading.Thread):
    """Daemon thread: records audio windows, gates on significance, writes to ContextStore.

    Two callback modes (mutually exclusive — on_query takes precedence):
      on_event(kind, compact) — passive: writes context, triggers proactive retrieval
      on_query(transcript)    — active:  treats speech as a user query (full turn)
    """
    daemon = True

    def __init__(
        self,
        tmp_dir: Path,
        ctx: ContextStore,
        on_event: Callable[[str, str], None] | None = None,
        on_query: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(name="audio-obs")
        self.tmp_dir   = tmp_dir
        self._ctx      = ctx
        self._on_event = on_event
        self._on_query = on_query   # when set: audio → full turn, not just context
        self._stop     = threading.Event()
        self._idx      = 0
        self._recent_transcripts: list[str] = []   # for dedup gate
        self._recent_wavs: list[Path] = []          # for native audio attachment
        self.active       = False
        self.recording_ok = True   # False when mic/recorder unavailable

    def stop(self) -> None:
        self._stop.set()
        self.active = False

    def recent_speech_wavs(self) -> list[Path]:
        return [p for p in self._recent_wavs if p.exists()]

    def run(self) -> None:
        self.active = True
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop.wait(POLL_INTERVAL)

    def _tick(self) -> None:
        self._idx += 1
        wav = self.tmp_dir / f"audio-{self._idx % (MAX_WAV_KEEP * 2)}.wav"
        ts  = datetime.now(timezone.utc).isoformat()

        if not record_window(wav, WINDOW_SECONDS):
            self.recording_ok = False
            return   # thread keeps running; will retry next tick
        self.recording_ok = True

        db = rms_db(wav)
        if db is None or db < SILENCE_DB:
            return  # silence — don't even transcribe

        text = transcribe(wav)
        if not text:
            return

        if not audio_gate(text, self._recent_transcripts):
            return  # not significant / duplicate

        compact, detailed = D.audio(ts, text, db)
        self._ctx.append(ts=ts, kind="audio", compact=compact, detailed=detailed)
        if self._on_query:
            # active mode: treat speech as a query (handles retrieval internally)
            self._on_query(text)
        elif self._on_event:
            # passive mode: trigger proactive background retrieval only
            self._on_event("audio", compact)

        self._recent_transcripts.append(text)
        if len(self._recent_transcripts) > MAX_RECENT_KEEP:
            self._recent_transcripts.pop(0)

        self._recent_wavs.append(wav)
        if len(self._recent_wavs) > MAX_WAV_KEEP:
            self._recent_wavs.pop(0)
