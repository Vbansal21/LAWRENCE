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
import queue
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
# WSLg's RDP virtual mic captures at a low level; -42 dB rejected real speech and
# -45 left the loop silent (N-63). -55 lets quiet speech through to whisper (which
# has its own VAD). This is the SINGLE source of truth for the speech-energy floor:
# the streaming capture VAD (`vad_db` below) defaults to it. Tunable via
# LK_AUDIO_SILENCE_DB; LK_AUDIO_VAD_DB still overrides the live capture value.
SILENCE_DB           = float(os.environ.get("LK_AUDIO_SILENCE_DB", "-55"))
NORMALIZE_PEAK_DB    = -3.0   # opt-in (LK_AUDIO_GAIN) peak target for quiet mics
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


# ── Windows-host capture (N-63 workaround for the degraded WSLg virtual mic) ────
# Under WSL the RDP virtual mic is quiet/unreliable. When enabled, capture from the
# REAL Windows audio device by driving a Windows-side ffmpeg.exe over WSL interop,
# reading raw PCM from its stdout — bypassing PulseAudio/WSLg entirely. Opt-in
# (LK_AUDIO_WIN_CAPTURE=1) and self-disabling when the tooling isn't present, so the
# default WSLg path is untouched and it degrades gracefully (I4). Drop an ffmpeg.exe
# under C:\ (or set LK_FFMPEG_WIN) and pick the mic with LK_AUDIO_WIN_DEVICE.

_win_device_cache: str | None = None


def _win_capture_enabled() -> bool:
    return os.environ.get("LK_AUDIO_WIN_CAPTURE", "").strip().lower() in ("1", "true", "yes", "on")


def _win_ffmpeg_exe() -> str | None:
    explicit = os.environ.get("LK_FFMPEG_WIN", "").strip()
    if explicit and Path(explicit).exists():
        return explicit
    found = shutil.which("ffmpeg.exe")     # Windows PATH exposed via WSL interop
    if found:
        return found
    for cand in ("/mnt/c/ffmpeg/bin/ffmpeg.exe", "/mnt/c/ffmpeg.exe",
                 "/mnt/c/Windows/System32/ffmpeg.exe"):
        if Path(cand).exists():
            return cand
    return None


def _win_audio_device(ffmpeg: str) -> str | None:
    """The dshow device name to record: LK_AUDIO_WIN_DEVICE, else the first audio
    device ffmpeg.exe reports. Cached (the probe is slow)."""
    global _win_device_cache
    if _win_device_cache is not None:
        return _win_device_cache or None
    dev = os.environ.get("LK_AUDIO_WIN_DEVICE", "").strip()
    if not dev:
        try:
            import re
            r = subprocess.run(
                [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True, text=True, timeout=15,
            )
            for line in (r.stderr or "").splitlines():
                if "(audio)" in line.lower():
                    m = re.search(r'"([^"]+)"', line)
                    if m:
                        dev = m.group(1)
                        break
        except Exception:
            dev = ""
    _win_device_cache = dev
    return dev or None


def _win_pcm_stream_cmd() -> list[str] | None:
    """argv for a long-lived Windows-host recorder emitting s16le mono PCM on stdout,
    or None when the workaround is disabled/unavailable (→ fall back to WSLg)."""
    if not _win_capture_enabled():
        return None
    ff = _win_ffmpeg_exe()
    if not ff:
        return None
    dev = _win_audio_device(ff)
    if not dev:
        return None
    return [ff, "-hide_banner", "-loglevel", "error", "-f", "dshow",
            "-i", f"audio={dev}", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"]


def _win_window(out: Path, secs: float) -> bool:
    cmd = _win_pcm_stream_cmd()
    if cmd is None:
        return False
    n_bytes = int(SAMPLE_RATE * 2 * secs)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        data = proc.stdout.read(n_bytes) if proc.stdout else b""
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        return False
    if len(data) < n_bytes // 2:
        return False
    _write_wav(out, data)
    return out.exists()


def record_window(out: Path, secs: float) -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    return _win_window(out, secs) or _parec(out, secs) or _arecord(out, secs) or _ffmpeg(out, secs)


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
    # Gain normalization is NOT applied here by default: pumping a near-silent
    # window up to -3 dBFS (~20x) amplified the ambient noise floor into something
    # whisper confabulates fluent speech from (false transcripts on silence). The
    # opt-in boost (LK_AUDIO_GAIN=1) is applied by the streaming path in
    # _transcribe_buf, where the audio has already passed the per-frame VAD energy
    # gate (so it is confirmed speech, not silence). VAD + the per-segment
    # confidence guards in _faster_whisper remain the real speech test.
    return _faster_whisper(wav) or _whisper_cli(wav) or ""


def _gain_enabled() -> bool:
    return os.environ.get("LK_AUDIO_GAIN", "").strip().lower() in ("1", "true", "yes", "on")


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
    Windows-host capture first when enabled (N-63 workaround), else the WSLg
    recorders in preference order (parec works on WSLg)."""
    win = _win_pcm_stream_cmd()
    if win is not None:
        return win
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
        # N-63: decode runs on its own thread so whisper never blocks the capture
        # loop (a blocked loop stops draining proc.stdout → pipe overflow → dropped
        # audio + cut-off/repeated speech). The capture loop enqueues PCM jobs; this
        # worker decodes them. Bounded so a decode backlog can't grow unbounded.
        self._jobs: "queue.Queue[tuple[str, str, bytes] | None]" = queue.Queue(maxsize=8)
        self._worker: threading.Thread | None = None
        # capture tunables (read per (re)start so `lk config` changes take effect).
        # VAD floor defaults to the single source of truth (SILENCE_DB = -55);
        # LK_AUDIO_VAD_DB overrides it for the live capture value.
        self.vad_db        = float(os.environ.get("LK_AUDIO_VAD_DB", str(SILENCE_DB)))
        self.frame_ms      = max(50, int(os.environ.get("LK_AUDIO_FRAME_MS", "300")))
        self.preroll_ms    = max(0, int(os.environ.get("LK_AUDIO_PREROLL_MS", "600")))
        self.hangover_ms   = max(self.frame_ms, int(os.environ.get("LK_AUDIO_HANGOVER_MS", "800")))
        self.max_utterance_s = float(os.environ.get("LK_AUDIO_MAX_UTTERANCE_S", "30"))
        self.partial_interval_ms = max(self.frame_ms,
                                       int(os.environ.get("LK_AUDIO_PARTIAL_INTERVAL_MS", "1500")))

    def stop(self) -> None:
        self._stop_evt.set()
        self.active = False
        try:
            self._jobs.put_nowait(None)   # wake the decode worker so it can exit
        except queue.Full:
            pass

    def run(self) -> None:
        self.active = True
        # start the off-thread decoder once; capture loops below only enqueue PCM.
        if self._worker is None:
            self._worker = threading.Thread(target=self._decode_worker,
                                            name="audio-decode", daemon=True)
            self._worker.start()
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
                # recorder ended / short read — finalize any open utterance first so
                # its tail isn't lost (N-63), then let the outer loop reopen.
                if in_speech and buf:
                    self._finish_utterance(uid, bytes(buf))
                break
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
                self._submit("partial", uid, bytes(buf))

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
        if _gain_enabled():        # opt-in boost on VAD-confirmed (already-speech) audio
            _normalize_gain(wav)
        return transcribe(wav)

    def _emit_segment(self, uid: str, text: str, final: bool) -> None:
        if self._on_segment:
            try:
                self._on_segment(uid, text, final)
            except Exception:
                pass

    # ── off-thread decode (N-63) ────────────────────────────────────────────────

    def _submit(self, kind: str, uid: str, pcm: bytes) -> None:
        """Hand a decode job to the worker so the capture loop never blocks. When the
        worker isn't running (e.g. a unit test driving _capture_loop directly), decode
        inline so behavior is unchanged for callers that don't go through run()."""
        if self._worker is not None and self._worker.is_alive():
            try:
                self._jobs.put_nowait((kind, uid, pcm))
            except queue.Full:
                # capture must never stall on a decode backlog — drop the oldest job.
                try:
                    self._jobs.get_nowait()
                    self._jobs.put_nowait((kind, uid, pcm))
                except (queue.Empty, queue.Full):
                    pass
            return
        # inline fallback
        if kind == "partial":
            text = self._transcribe_buf(pcm)
            if text:
                self._emit_segment(uid, text, final=False)
        else:
            self._finalize_decoded(uid, pcm)

    def _decode_worker(self) -> None:
        while not self._stop_evt.is_set():
            try:
                job = self._jobs.get(timeout=0.5)
            except queue.Empty:
                continue
            if job is None:
                break
            kind, uid, pcm = job
            try:
                if kind == "partial":
                    if not self._jobs.empty():
                        continue    # a newer job is waiting — skip this stale partial
                    text = self._transcribe_buf(pcm)
                    if text:
                        self._emit_segment(uid, text, final=False)
                else:
                    self._finalize_decoded(uid, pcm)
            except Exception:
                pass

    def _finish_utterance(self, uid: str, pcm: bytes) -> None:
        self._submit("final", uid, pcm)

    def _finalize_decoded(self, uid: str, pcm: bytes) -> None:
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
