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
import time
import wave
from collections import deque
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
# whisper hallucinates fluent text on silence/noise; reject segments it is unsure of.
NO_SPEECH_MAX        = 0.6    # drop a segment whose no-speech probability exceeds this
MIN_AVG_LOGPROB      = -1.0   # drop a low-confidence (likely confabulated) segment


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
        # vad_filter (Silero) drops non-speech regions; the per-segment guards reject
        # whisper's well-known hallucinations on silence/noise (it confabulates fluent
        # text from quiet audio — those segments carry a high no_speech_prob / low
        # avg_logprob). This is the actual "is it speech" test, not the RMS gate.
        segs, _ = m.transcribe(  # type: ignore[union-attr]
            str(wav), language=None, vad_filter=True, no_speech_threshold=NO_SPEECH_MAX,
        )
        kept = [
            s.text.strip() for s in segs
            if s.no_speech_prob < NO_SPEECH_MAX
            and s.avg_logprob > MIN_AVG_LOGPROB
            and s.text.strip()
        ]
        text = " ".join(kept).strip()
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
    # Deliberately NOT gain-normalised here: pumping a near-silent window up to
    # -3 dBFS (~20x) amplified the ambient noise floor into something whisper
    # confabulates fluent speech from (false transcripts on silence). VAD + the
    # per-segment confidence guards in _faster_whisper are the real speech test.
    # (_normalize_gain is kept for an explicit, calibrated opt-in if a genuinely
    # quiet mic ever needs a *mild* boost on already-VAD-confirmed speech.)
    return _faster_whisper(wav) or _whisper_cli(wav) or ""


# ── streaming capture (utterance segmentation, N-53) ───────────────────────────

def _rms_db_bytes(frame: bytes) -> float:
    """RMS dBFS of a raw s16le mono frame (the per-frame VAD energy)."""
    if len(frame) < 2:
        return -96.0
    samples = array.array("h")
    samples.frombytes(frame[: len(frame) - (len(frame) % 2)])
    if not samples:
        return -96.0
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    return -96.0 if rms < 1 else 20 * math.log10(rms / 32768.0)


def _write_wav(out: Path, pcm: bytes) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)


def _pcm_stream_cmd() -> list[str] | None:
    """argv for a long-lived recorder that emits raw s16le mono PCM on stdout.
    Same recorder preference as the windowed path (parec works on WSLg)."""
    if shutil.which("parec"):
        if "PULSE_SERVER" not in os.environ and Path("/mnt/wslg/PulseServer").exists():
            os.environ["PULSE_SERVER"] = "unix:/mnt/wslg/PulseServer"
        return ["parec", "--format=s16le", f"--rate={SAMPLE_RATE}", "--channels=1"]
    if shutil.which("arecord"):
        return ["arecord", "-q", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", "-t", "raw"]
    if shutil.which("ffmpeg"):
        return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "pulse", "-i", "default",
                "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"]
    return None


# ── observer daemon ───────────────────────────────────────────────────────────

class AudioObserver(threading.Thread):
    """Daemon thread: continuous capture → VAD-segmented utterances → transcribe.

    Unlike the old fixed-4s-window scheme (which clipped utterance onsets/tails,
    repeated text across window boundaries, and rejected short atomic commands),
    this reads short frames continuously, keeps a rolling pre-roll buffer so the
    onset is never clipped, opens an utterance on speech energy, and closes it
    after a trailing-silence *hangover* so the tail is never clipped. One utterance
    → one ContextStore entry (no per-window repeats).

    Callback modes (combinable):
      on_event(kind, compact)        — passive: write context + drive proactive
      on_query(transcript)           — active: a finished utterance becomes a turn
      on_segment(uid, text, final)   — streaming display: partials then the final,
                                       all keyed by one utterance id (one UI entry)
    """
    daemon = True

    def __init__(
        self,
        tmp_dir: Path,
        ctx: ContextStore,
        on_event: Callable[[str, str], None] | None = None,
        on_query: Callable[[str], None] | None = None,
        on_segment: Callable[[str, str, bool], None] | None = None,
    ) -> None:
        super().__init__(name="audio-obs")
        self.tmp_dir    = tmp_dir
        self._ctx       = ctx
        self._on_event  = on_event
        self._on_query  = on_query     # when set: a finished utterance → full turn
        self._on_segment = on_segment  # when set: stream partial/final text to the UI
        self._stop_evt  = threading.Event()
        self._idx       = 0
        self._recent_transcripts: list[str] = []   # for dedup gate
        self.active       = False
        self.recording_ok = True   # False when mic/recorder unavailable
        # capture tunables (read per (re)start so `lk config` changes take effect).
        self.vad_db        = float(os.environ.get("LK_AUDIO_VAD_DB", "-45"))
        self.frame_ms      = max(50, int(os.environ.get("LK_AUDIO_FRAME_MS", "300")))
        self.preroll_ms    = max(0, int(os.environ.get("LK_AUDIO_PREROLL_MS", "600")))
        self.hangover_ms   = max(self.frame_ms, int(os.environ.get("LK_AUDIO_HANGOVER_MS", "800")))
        self.max_utterance_s = float(os.environ.get("LK_AUDIO_MAX_UTTERANCE_S", "30"))
        self.partial_interval_ms = max(self.frame_ms,
                                       int(os.environ.get("LK_AUDIO_PARTIAL_INTERVAL_MS", "1500")))

    def stop(self) -> None:
        self._stop_evt.set()
        self.active = False

    def run(self) -> None:
        self.active = True
        while not self._stop_evt.is_set():
            cmd = _pcm_stream_cmd()
            if cmd is None:
                self.recording_ok = False
                self._stop_evt.wait(2.0)   # no recorder — retry, don't spin
                continue
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except Exception:
                self.recording_ok = False
                self._stop_evt.wait(2.0)
                continue
            self.recording_ok = True
            started = time.monotonic()
            try:
                self._capture_loop(proc)
            except Exception:
                pass
            finally:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    pass
            # fell out of the loop (recorder died / short read) — reopen unless
            # stopped; back off if the recorder exited almost immediately so a
            # broken device can't spin a tight Popen loop.
            if time.monotonic() - started < 1.0:
                self._stop_evt.wait(2.0)

    def _capture_loop(self, proc: subprocess.Popen) -> None:
        frame_bytes = int(SAMPLE_RATE * 2 * self.frame_ms / 1000)
        preroll_frames = max(1, self.preroll_ms // self.frame_ms)
        preroll: deque[bytes] = deque(maxlen=preroll_frames)
        in_speech   = False
        buf         = bytearray()
        silence_ms  = 0
        spoken_ms   = 0
        last_partial_ms = 0
        uid         = ""

        while not self._stop_evt.is_set():
            chunk = proc.stdout.read(frame_bytes) if proc.stdout else b""
            if not chunk or len(chunk) < frame_bytes:
                break   # recorder ended / short read — outer loop reopens
            is_speech = _rms_db_bytes(chunk) > self.vad_db

            if not in_speech:
                preroll.append(chunk)
                if is_speech:                       # ── utterance onset ──
                    in_speech   = True
                    uid         = f"utt-{int(time.time() * 1000)}"
                    buf         = bytearray(b"".join(preroll))   # incl. pre-roll → no onset clip
                    preroll.clear()
                    silence_ms  = 0
                    spoken_ms   = self.frame_ms
                    last_partial_ms = 0
                continue

            # ── inside an utterance ──
            buf += chunk
            spoken_ms += self.frame_ms
            silence_ms = 0 if is_speech else silence_ms + self.frame_ms

            # stream a partial transcription (UI only) on a bounded cadence
            if (self._on_segment and is_speech
                    and spoken_ms - last_partial_ms >= self.partial_interval_ms):
                last_partial_ms = spoken_ms
                text = self._transcribe_buf(bytes(buf))
                if text:
                    self._emit_segment(uid, text, final=False)

            # close on trailing-silence hangover (→ no tail clip) or the hard cap
            if silence_ms >= self.hangover_ms or spoken_ms >= self.max_utterance_s * 1000:
                self._finish_utterance(uid, bytes(buf))
                in_speech, buf, silence_ms, spoken_ms = False, bytearray(), 0, 0
                preroll.clear()

    def _transcribe_buf(self, pcm: bytes) -> str:
        self._idx = (self._idx + 1) % (MAX_WAV_KEEP * 2)
        wav = self.tmp_dir / f"audio-{self._idx}.wav"
        try:
            _write_wav(wav, pcm)
        except Exception:
            return ""
        return transcribe(wav)

    def _emit_segment(self, uid: str, text: str, final: bool) -> None:
        if self._on_segment:
            try:
                self._on_segment(uid, text, final)
            except Exception:
                pass

    def _finish_utterance(self, uid: str, pcm: bytes) -> None:
        ts   = datetime.now(timezone.utc).isoformat()
        text = self._transcribe_buf(pcm)
        # whisper's silence/no_speech guards already dropped pure-noise utterances;
        # min_words=1 lets a VAD-confirmed atomic command through, dedup blocks repeats.
        if not text or not audio_gate(text, self._recent_transcripts, min_words=1):
            return
        self._emit_segment(uid, text, final=True)
        compact, detailed = D.audio(ts, text, None)
        self._ctx.append(ts=ts, kind="audio", compact=compact, detailed=detailed)
        if self._on_event:
            self._on_event("audio", compact)     # passive context (drives proactive)
        if self._on_query:
            self._on_query(text)                  # active: becomes a turn (N-54 gates it)
        self._recent_transcripts.append(text)
        if len(self._recent_transcripts) > MAX_RECENT_KEEP:
            self._recent_transcripts.pop(0)
