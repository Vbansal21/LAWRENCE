"""Audio observer — record → VAD → transcribe → gate → distill → context store.

Runs as a daemon thread. Records WINDOW_SECONDS of audio every POLL_INTERVAL
seconds. VAD via RMS energy. Transcription via faster-whisper or whisper-cli.
Only segments that pass the significance gate (speech, non-duplicate) are
written to the context store.

In --audio-query mode the transcript is handed to on_query (a full turn);
on_event may also fire so the desktop UI can display/store the transcript.
"""
from __future__ import annotations

import array
import math
import os
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
# WSLg's RDP virtual mic captures at a low level; -42 dB rejected real speech.
# -55 lets quiet speech through to whisper (which has its own VAD), tunable via
# LK_AUDIO_SILENCE_DB. Gain normalization (below) then boosts it for whisper.
SILENCE_DB           = float(os.environ.get("LK_AUDIO_SILENCE_DB", "-55"))
NORMALIZE_PEAK_DB    = -3.0   # boost quiet captures to this peak before transcribe
MAX_WAV_KEEP         = 5
MAX_RECENT_KEEP      = 12   # recent transcripts kept for dedup gate


# ── recording ─────────────────────────────────────────────────────────────────

def _parec(out: Path, secs: float) -> bool:
    """Native PulseAudio capture via parec — the recorder that works on WSLg
    without sudo (conda-forge pulseaudio-client). Reads exactly secs of raw
    s16le mono PCM and wraps it in a wav header ourselves."""
    if not shutil.which("parec"):
        return False
    if "PULSE_SERVER" not in os.environ and Path("/mnt/wslg/PulseServer").exists():
        os.environ["PULSE_SERVER"] = "unix:/mnt/wslg/PulseServer"
    n_bytes = int(SAMPLE_RATE * 2 * secs)
    try:
        proc = subprocess.Popen(
            ["parec", "--format=s16le", f"--rate={SAMPLE_RATE}", "--channels=1"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        data = proc.stdout.read(n_bytes) if proc.stdout else b""
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        return False
    if len(data) < n_bytes // 2:
        return False        # device produced (almost) nothing — try next recorder
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(data)
    return out.exists()


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
    return _parec(out, secs) or _arecord(out, secs) or _ffmpeg(out, secs)


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


def _normalize_gain(wav: Path, target_peak_db: float = NORMALIZE_PEAK_DB) -> None:
    """Scale a 16-bit mono wav in place so its peak hits target_peak_db. Quiet
    WSLg-mic captures (peak well below 0 dBFS) are otherwise too faint for
    reliable transcription. No-op on silence or read errors."""
    try:
        with wave.open(str(wav), "rb") as wf:
            if wf.getsampwidth() != 2:
                return
            params = wf.getparams()
            raw = wf.readframes(wf.getnframes())
        samples = array.array("h", raw)
        if not samples:
            return
        peak = max(abs(s) for s in samples)
        if peak < 64:                         # essentially silent — nothing to boost
            return
        target = 32768.0 * (10 ** (target_peak_db / 20.0))
        gain = target / peak
        if gain <= 1.05:                      # already loud enough
            return
        gain = min(gain, 20.0)                # cap so noise floors don't explode
        for i, s in enumerate(samples):
            v = int(s * gain)
            samples[i] = 32767 if v > 32767 else -32768 if v < -32768 else v
        with wave.open(str(wav), "wb") as wf:
            wf.setparams(params)
            wf.writeframes(samples.tobytes())
    except Exception:
        return


def transcribe(wav: Path) -> str:
    _normalize_gain(wav)
    return _faster_whisper(wav) or _whisper_cli(wav) or ""


# ── observer daemon ───────────────────────────────────────────────────────────

class AudioObserver(threading.Thread):
    """Daemon thread: records audio windows, gates on significance, writes to ContextStore.

    Callback modes can be combined:
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
        self._stop_evt     = threading.Event()
        self._idx      = 0
        self._recent_transcripts: list[str] = []   # for dedup gate
        self.active       = False
        self.recording_ok = True   # False when mic/recorder unavailable

    def stop(self) -> None:
        self._stop_evt.set()
        self.active = False

    def run(self) -> None:
        self.active = True
        while not self._stop_evt.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop_evt.wait(POLL_INTERVAL)

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
        if self._on_event:
            # passive event: update UI/context even when speech also becomes a turn
            self._on_event("audio", compact)
        if self._on_query:
            # active mode: treat speech as a query (handles retrieval internally)
            self._on_query(text)

        self._recent_transcripts.append(text)
        if len(self._recent_transcripts) > MAX_RECENT_KEEP:
            self._recent_transcripts.pop(0)
