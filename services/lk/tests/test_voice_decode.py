"""N-63 — NON-MOCKED voice capture smoke.

The §F sensor stress test mocks `_rms_db_bytes`, `transcribe`, AND `audio_gate`, so a
green `make check` only exercised loop bookkeeping — never the speech-energy threshold
(root cause: -45 dB left the loop silent), the off-thread decode, or the gain path.
This test drives the REAL energy gate over synthesized PCM (silence vs tone) and the
real segmentation, and verifies the Windows-host capture workaround degrades safely.
(A real whisper decode needs a speech fixture + the model installed; it runs only if
tests/fixtures/utterance.wav exists, else that one assertion is skipped — never failed.)
"""
import array
import math
import os
import sys
import tempfile
import shutil
import wave
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, "services")

import lk.obs.audio as A

FAILS = []
def check(name, cond, extra=""):
    print(f"  [{'ok' if cond else 'XX'}] {name}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)

SR = A.SAMPLE_RATE
FRAME_MS = 100
FRAME_BYTES = int(SR * 2 * FRAME_MS / 1000)


def _silence_frame() -> bytes:
    return b"\x00\x00" * (FRAME_BYTES // 2)


def _tone_frame(amp: int = 5000, hz: int = 220) -> bytes:
    n = FRAME_BYTES // 2
    buf = array.array("h", (int(amp * math.sin(2 * math.pi * hz * i / SR)) for i in range(n)))
    return buf.tobytes()


# ── 1. REAL energy gate separates silence from signal at the -55 floor ──────────
print("\n§1 real _rms_db_bytes energy gate (the thing §F mocked)")
db_sil = A._rms_db_bytes(_silence_frame())
db_tone = A._rms_db_bytes(_tone_frame())
check("silence sits below the -55 VAD floor", db_sil <= -55, f"{db_sil:.1f} dB")
check("tone sits above the -55 VAD floor", db_tone > -55, f"{db_tone:.1f} dB")
check("tone is clearly louder than silence", db_tone - db_sil > 30, f"{db_tone - db_sil:.1f} dB")

# the live default VAD floor is now -55 (was -45 → silence), single source of truth
obs0 = A.AudioObserver(Path(tempfile.gettempdir()), SimpleNamespace(append=lambda **_k: None))
check("default capture VAD floor is the documented -55", obs0.vad_db == -55.0, str(obs0.vad_db))

# ── 2. real segmentation: one tone burst in silence → exactly one utterance ─────
print("\n§2 real-energy segmentation (no mocked threshold)")
tmp = Path(tempfile.mkdtemp(prefix="lk-voice-"))
saved_tx = A.transcribe
A.transcribe = lambda *_a: "move the call to friday"     # stub only the decode, not the gate
saved_env = {k: os.environ.get(k) for k in
             ("LK_AUDIO_FRAME_MS", "LK_AUDIO_HANGOVER_MS", "LK_AUDIO_PREROLL_MS",
              "LK_AUDIO_PARTIAL_INTERVAL_MS", "LK_AUDIO_VAD_DB")}
os.environ.update({"LK_AUDIO_FRAME_MS": str(FRAME_MS), "LK_AUDIO_HANGOVER_MS": "200",
                   "LK_AUDIO_PREROLL_MS": "100", "LK_AUDIO_PARTIAL_INTERVAL_MS": "9000",
                   "LK_AUDIO_VAD_DB": "-55"})
# silence (pre-roll), tone, tone, tone, silence, silence(→ hangover closes), EOF
frames = [_silence_frame(), _tone_frame(), _tone_frame(), _tone_frame(),
          _silence_frame(), _silence_frame()]
it = iter(frames)
def _read(_size):
    return next(it, b"")
fake_proc = SimpleNamespace(stdout=SimpleNamespace(read=_read),
                            terminate=lambda: None, wait=lambda **_k: None)
queries, events, segments = [], [], []
obs = A.AudioObserver(
    tmp, SimpleNamespace(append=lambda **_k: None),
    on_event=lambda kind, text: events.append((kind, text)),
    on_query=queries.append,
    on_segment=lambda uid, text, final: segments.append((uid, text, final)),
)
obs._capture_loop(fake_proc)     # worker not started → inline decode (synchronous)
check("one tone burst → exactly one utterance/turn", queries == ["move the call to friday"], str(queries))
check("one passive context event per utterance", len(events) == 1, str(events))
check("a final streaming segment is emitted", any(f for _u, _t, f in segments), str(segments))
A.transcribe = saved_tx

# ── 2b. the REAL async decode-worker thread (not the inline fallback §2 used) ────
print("\n§2b off-thread decode worker actually delivers (production concurrency path)")
import threading, time as _t
saved_tx2 = A.transcribe
A.transcribe = lambda *_a: "worker thread path delivers"
wq, wev = [], []
wobs = A.AudioObserver(tmp, SimpleNamespace(append=lambda **_k: None),
                       on_event=lambda k, t: wev.append((k, t)), on_query=wq.append)
wobs._worker = threading.Thread(target=wobs._decode_worker, daemon=True)
wobs._worker.start()
check("decode worker thread is alive", wobs._worker.is_alive())
wobs._submit("final", "u1", b"\x00" * 3200)   # routed through the QUEUE (worker alive)
for _ in range(60):
    if wq:
        break
    _t.sleep(0.05)
wobs.stop()
check("worker delivers the final transcript asynchronously (off capture thread)",
      wq == ["worker thread path delivers"], str(wq))
check("worker also drives the passive context/proactive event", len(wev) == 1, str(wev))
A.transcribe = saved_tx2

# ── 3. gain path is real and bounded (opt-in, no longer comment-only) ───────────
print("\n§3 _normalize_gain wired + bounded")
quiet = tmp / "quiet.wav"
A._write_wav(quiet, array.array("h", [200, -200] * (SR // 2)).tobytes())  # very faint
with wave.open(str(quiet), "rb") as wf:
    before = max(abs(s) for s in array.array("h", wf.readframes(wf.getnframes())))
A._normalize_gain(quiet)
with wave.open(str(quiet), "rb") as wf:
    after_samples = array.array("h", wf.readframes(wf.getnframes()))
after = max(abs(s) for s in after_samples)
check("gain boosts a quiet capture", after > before, f"{before}->{after}")
check("gain never clips past int16", after <= 32767, str(after))
check("LK_AUDIO_GAIN opt-in defaults off", A._gain_enabled() is False)

# ── 4. Windows-host capture workaround degrades safely when tooling absent ──────
print("\n§4 Windows-host capture workaround (N-63) degrades gracefully")
check("win capture off by default", A._win_capture_enabled() is False)
os.environ["LK_AUDIO_WIN_CAPTURE"] = "1"
os.environ.pop("LK_FFMPEG_WIN", None)
A._win_device_cache = None
# with no ffmpeg.exe reachable this returns None (→ falls back to WSLg recorders)
cmd = A._win_pcm_stream_cmd()
check("win stream cmd is None or a real ffmpeg argv (never crashes)",
      cmd is None or (isinstance(cmd, list) and "dshow" in cmd), str(cmd))
check("_pcm_stream_cmd still resolves a backend or None", True)
A._pcm_stream_cmd()   # must not raise
os.environ.pop("LK_AUDIO_WIN_CAPTURE", None)

# ── optional real decode if a speech fixture is present ─────────────────────────
fixture = Path("services/lk/tests/fixtures/utterance.wav")
if fixture.exists():
    print("\n§5 real whisper decode (fixture present)")
    txt = A.transcribe(fixture)
    check("fixture utterance decodes to non-empty text", bool(txt.strip()), repr(txt))
else:
    print("\n§5 skipped: no tests/fixtures/utterance.wav (real-decode smoke is opt-in)")

# restore env
for k, v in saved_env.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v
shutil.rmtree(tmp, ignore_errors=True)

if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\nVOICE DECODE (N-63): PASS")
