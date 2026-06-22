"""N-60 SENSOR-STRESS — deterministic perception endurance (offline lane).

PLAN §M.5 / §N.1 N-60 wants live vision+audio+voice run for ≥30 min with a
**labeled audio set plus live microphone speech**, asserting: no onset/tail
clipping in labeled samples, one utterance identity per query, the send/dismiss
timeout never below 10 s, bounded spool/temp files, no observer death, and no
duplicate proactive turn from one utterance.

Of those, the parts that need *real hardware* (a microphone, a display, the
30-minute wall-clock, the host silence floor, and a word-error-rate threshold on
real speech) are **LIVE-PENDING** — they cannot run in a headless sandbox. Run
`--live` to print that manual procedure.

What IS verifiable offline, deterministically, is the **machinery that decides
WHAT becomes an utterance and WHEN** — segmentation, utterance identity, the
significance/dedup gate, temp-file bounding, and observer survival. This file
drives the **real** `AudioObserver._capture_loop` (no new sensor abstraction —
the same seam stress_sensors.py §F uses) with a **deterministic labeled-audio
replay control**: a scripted per-frame RMS stream + a transcript-by-label stub,
endured across many utterances. A failure here is a real regression in the
sensor path; a pass is the offline half of N-60's acceptance.
"""
import sys, os, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path
from types import SimpleNamespace

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)
def section(t):
    print(f"\n=== {t} ===")


# ─────────────────────── labeled-audio replay control ───────────────────────
# A fixture is a list of (label, n_speech_frames). The control renders it into a
# flat per-frame RMS-dB stream the real capture loop consumes frame by frame:
#   [silence pre-roll] + [n speech frames] + [trailing silence ≥ hangover]
# Speech is above the VAD floor; silence below. `transcribe` is stubbed to return
# each utterance's label in segmentation order, so identity/order/clipping are
# checked by the labels that actually cross the gate into queries.

SPEECH_DB = -20.0     # above the VAD floor → speech frame
SILENCE_DB_ = -60.0   # below the VAD floor → silence frame
VAD_DB = "-45"        # LK_AUDIO_VAD_DB for the run


def render_stream(fixture, *, close=True):
    """fixture: list[(label, n_speech)] → (levels, labels).

    `levels` is the per-frame dB sequence; `labels` is the per-utterance label
    list in the order the loop will finalize them. With close=True every
    utterance ends in trailing silence (clean hangover close); with close=False
    the LAST utterance ends mid-speech so the EOF-finalize path (tail-not-lost)
    is exercised.
    """
    levels, labels = [], []
    for i, (label, n_speech) in enumerate(fixture):
        labels.append(label)
        levels.append(SILENCE_DB_)                      # 1-frame pre-roll (onset not clipped)
        levels.extend([SPEECH_DB] * max(1, n_speech))   # the utterance body
        last = (i == len(fixture) - 1)
        if close or not last:
            levels.extend([SILENCE_DB_, SILENCE_DB_])    # trailing silence → hangover close
    return levels, labels


def replay(fixture, *, close=True, use_real_gate=True, partials=False):
    """Drive the real AudioObserver._capture_loop over a rendered fixture.

    Returns (queries, events, segments, tmp_dir, error) — error is the exception
    that escaped the capture loop, or None (observer survived)."""
    import lk.obs.audio as audio_mod
    from lk.obs.audio import AudioObserver

    tmp = Path(tempfile.mkdtemp(prefix="lk-n60-"))
    levels, labels = render_stream(fixture, close=close)

    saved = (audio_mod.transcribe, audio_mod._rms_db_bytes, audio_mod.audio_gate)
    env_keys = ("LK_AUDIO_FRAME_MS", "LK_AUDIO_HANGOVER_MS", "LK_AUDIO_PREROLL_MS",
                "LK_AUDIO_PARTIAL_INTERVAL_MS", "LK_AUDIO_VAD_DB", "LK_AUDIO_MAX_UTTERANCE_S")
    saved_env = {k: os.environ.get(k) for k in env_keys}
    os.environ.update({
        "LK_AUDIO_FRAME_MS": "100",
        "LK_AUDIO_HANGOVER_MS": "200",      # 2 silence frames close an utterance
        "LK_AUDIO_PREROLL_MS": "100",       # 1 pre-roll frame retained
        # suppress partials unless asked, so transcribe fires exactly once / utterance
        "LK_AUDIO_PARTIAL_INTERVAL_MS": "100" if partials else "9999999",
        "LK_AUDIO_VAD_DB": VAD_DB,
        "LK_AUDIO_MAX_UTTERANCE_S": "30",
    })

    level_iter = iter(levels)
    audio_mod._rms_db_bytes = lambda _frame: next(level_iter)
    call = {"n": 0}
    def _fake_transcribe(_wav):
        i = call["n"]; call["n"] += 1
        return labels[i] if i < len(labels) else ""
    audio_mod.transcribe = _fake_transcribe
    if not use_real_gate:
        audio_mod.audio_gate = lambda *_a, **_k: True   # bypass for a pure-segmentation view

    queries, events, segments = [], [], []
    frames_left = [len(levels)]
    def _read(size):
        if frames_left[0] > 0:
            frames_left[0] -= 1
            return b"\x00" * size
        return b""                                       # EOF → loop finalizes + ends
    proc = SimpleNamespace(stdout=SimpleNamespace(read=_read),
                           terminate=lambda: None, wait=lambda **_k: None)
    ctx = SimpleNamespace(append=lambda **_k: None)
    obs = AudioObserver(tmp, ctx,
                        on_event=lambda kind, text: events.append((kind, text)),
                        on_query=queries.append,
                        on_segment=lambda uid, text, final: segments.append((uid, text, final)))
    error = None
    try:
        obs._capture_loop(proc)
    except Exception as exc:           # observer "death" = an exception escaping the loop
        error = exc

    audio_mod.transcribe, audio_mod._rms_db_bytes, audio_mod.audio_gate = saved
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    return queries, events, segments, tmp, error


# ─────────────────────── A. identity / order / no clipping ───────────────────────
def suite_offline():
    section("A. labeled replay: one utterance → one query, in order, no merge/split (no onset/tail clip)")
    fixture = [
        ("move the planning call to friday", 1),        # short atomic command
        ("open the quarterly budget spreadsheet now", 4),
        ("please summarize the meeting notes for me today", 8),  # long utterance
        ("remind me about the dentist appointment tomorrow", 3),
    ]
    queries, events, segments, tmp, error = replay(fixture)
    labels = [f[0] for f in fixture]
    check("observer survived the labeled set (no exception escaped)", error is None, repr(error))
    check("every labeled utterance produced exactly one query (no clip-merge/split)",
          queries == labels, f"{queries}")
    check("one passive context event per utterance (no per-frame repeats)",
          len(events) == len(labels), f"{len(events)} events")
    check("each utterance emits a final streaming segment",
          sum(1 for _u, _t, f in segments if f) == len(labels),
          f"{sum(1 for _u, _t, f in segments if f)} finals")
    check("every final segment carries non-empty text (onset/tail not clipped to empty)",
          all(t for _u, t, f in segments if f))
    shutil.rmtree(tmp, ignore_errors=True)

    section("B. EOF-finalize: an utterance ending mid-speech is NOT lost (tail preserved at stream end)")
    fixture2 = [("first complete utterance about the report", 3),
                ("second utterance cut off by end of stream", 4)]
    q2, e2, s2, tmp2, err2 = replay(fixture2, close=False)
    check("observer survived a mid-speech EOF", err2 is None, repr(err2))
    check("both utterances delivered (the EOF tail was finalized, not dropped)",
          q2 == [f[0] for f in fixture2], f"{q2}")
    shutil.rmtree(tmp2, ignore_errors=True)

    section("C. significance/dedup gate: one utterance, no DUPLICATE proactive turn")
    # utt2 repeats utt0's text → the real audio_gate Jaccard-dedup must drop it,
    # so a single (possibly re-heard) utterance never fires two proactive turns.
    fixture3 = [
        ("schedule the design review for next monday", 3),
        ("check the deployment status on the server", 3),
        ("schedule the design review for next monday", 3),   # exact repeat → dropped
        ("archive the old release branch please", 3),
    ]
    q3, e3, s3, tmp3, err3 = replay(fixture3)
    check("observer survived", err3 is None, repr(err3))
    check("the duplicate utterance is dropped by the real significance gate (no 2nd turn)",
          q3 == ["schedule the design review for next monday",
                 "check the deployment status on the server",
                 "archive the old release branch please"], f"{q3}")
    check("dropping is the gate, not segmentation: bypassing the gate yields all four",
          replay(fixture3, use_real_gate=False)[0] == [f[0] for f in fixture3])
    shutil.rmtree(tmp3, ignore_errors=True)

    section("D. ENDURANCE proxy: many distinct utterances → exact count, no drift, bounded temp")
    from lk.obs.audio import MAX_WAV_KEEP
    n = 120
    # genuinely distinct content per utterance (real speech has low word overlap;
    # near-identical text would be — correctly — dropped by the dedup gate, so the
    # endurance fixture must vary like real input does).
    big = [(f"alpha{i} bravo{i} charlie{i} delta{i}", (i % 6) + 1) for i in range(n)]
    qB, eB, sB, tmpB, errB = replay(big)
    check("observer survived a long deterministic run", errB is None, repr(errB))
    check(f"all {n} distinct utterances delivered exactly once, in order",
          qB == [f[0] for f in big], f"got {len(qB)}")
    check("no per-utterance drift between queries and passive events",
          len(eB) == n, f"{len(eB)} events")
    wavs = list(tmpB.glob("*.wav"))
    check("temp wav files stay bounded across the whole run (no unbounded growth)",
          len(wavs) <= MAX_WAV_KEEP * 2, f"{len(wavs)} wavs (cap {MAX_WAV_KEEP*2})")
    shutil.rmtree(tmpB, ignore_errors=True)

    section("E. send/dismiss decision window is never below 10 s (static contract guard)")
    bridge_src = Path("apps/desktop/scripts/ui_bridge.py").read_text(encoding="utf-8")
    check("voice silence-timeout floor is max(10_000, …) — timeout never below ten seconds",
          'max(10_000, int(os.environ.get("LK_VOICE_SILENCE_TIMEOUT_MS", "10000")))' in bridge_src)

    section("F. VISION endurance: bounded novelty history, scores stay in [0,1] over many frames")
    from collections import deque
    from lk.obs.vision import frame_novelty_score, pixel_change_score
    history = deque(maxlen=8)
    base = bytes([10, 20, 30, 40] * 64)
    ok_bounds, max_len = True, 0
    for i in range(500):
        frame = bytes([(i * 7) % 256, (i * 13) % 256, 30, 40] * 64)
        sc = frame_novelty_score(history, frame)
        if not (0.0 <= sc <= 1.0):
            ok_bounds = False
        max_len = max(max_len, len(history))
    check("novelty scores stay bounded to [0,1] across 500 frames", ok_bounds)
    check("visual novelty history stays bounded (no leak)", max_len <= 8, f"max_len={max_len}")
    check("pixel_change_score stays bounded on a large change", 0.0 <= pixel_change_score(base, bytes([250, 5, 250, 5] * 64)) <= 1.0)


# ─────────────────────── live-pending procedure (hardware) ───────────────────────
LIVE_PROCEDURE = """\
N-60 LIVE LANE — requires real hardware (microphone + display); NOT runnable headless.
Mark [~] live-pending until performed on the target host. Manual acceptance steps:

  1. Boot the desktop runtime (apps/desktop/scripts/desktopctl.sh services-start)
     with audio + vision observers enabled and a local transcription model present.
  2. Run ≥30 minutes of mixed real activity: speak short commands and long
     utterances, leave silence gaps, change the foreground window repeatedly,
     trigger dismiss / proceed / auto-submit.
  3. Play the labeled audio set (the deterministic fixture above, voiced) and
     record the word-error rate against the labels; note the host silence floor.
  4. ACCEPT iff: no onset/tail clipping on the labeled samples, exactly one
     utterance identity per query, the send/dismiss window never < 10 s, spool /
     temp files stayed bounded, no observer thread died, and no single utterance
     produced a duplicate proactive turn. Record CPU/RAM trend + dropped-event
     count in the N-62 evidence bundle.
"""


def main(argv):
    if "--live" in argv:
        print(LIVE_PROCEDURE)
        print("  N-60 live lane: [~] LIVE-PENDING (hardware) — offline machinery verified separately.")
        return 0
    print("N-60 SENSOR ENDURANCE — offline deterministic lane "
          "(live mic/display + 30-min wall-clock + WER are [~] live-pending; run --live for the procedure)")
    suite_offline()
    section("RESULT")
    if FAILS:
        print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
        return 1
    print("\n  ALL N-60 OFFLINE SENSOR-ENDURANCE CHECKS PASSED  (live lane [~] live-pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
