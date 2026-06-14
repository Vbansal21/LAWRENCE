#!/usr/bin/env bash
# Audio pipeline diagnosis (P0.T2) — finds the exact broken stage.
# Read-only: records 2s to /tmp, changes nothing in the repo.
set -u
cd "$(dirname "$0")/.."
WAV=/tmp/lk-diag-audio.wav

stage() { printf "STAGE %-22s: %s\n" "$1" "$2"; }

# 1. recorder binaries
command -v arecord >/dev/null && stage "arecord" "OK $(command -v arecord)" \
    || stage "arecord" "FAIL not installed (alsa-utils)"
command -v ffmpeg >/dev/null && stage "ffmpeg" "OK $(command -v ffmpeg)" \
    || stage "ffmpeg" "FAIL not installed"
command -v parec >/dev/null && stage "parec" "OK $(command -v parec) (native pulse — preferred on WSLg)" \
    || stage "parec" "FAIL not installed (conda install -c conda-forge pulseaudio-client)"

# 2. PulseAudio reachability (WSLg serves /mnt/wslg/PulseServer)
PULSE="${PULSE_SERVER:-}"
if [ -z "$PULSE" ] && [ -S /mnt/wslg/PulseServer ]; then
    PULSE="unix:/mnt/wslg/PulseServer"
    stage "pulse-env" "FAIL \$PULSE_SERVER unset (WSLg socket exists — export PULSE_SERVER=$PULSE)"
else
    stage "pulse-env" "OK PULSE_SERVER=${PULSE:-'(default)'}"
fi
if command -v pactl >/dev/null; then
    if PULSE_SERVER="${PULSE#unix:}" pactl info >/dev/null 2>&1 || pactl info >/dev/null 2>&1; then
        SRC=$(pactl list short sources 2>/dev/null | grep -v monitor | head -1)
        stage "pulse-daemon" "OK (source: ${SRC:-NONE — no input device!})"
    else
        stage "pulse-daemon" "FAIL pactl cannot reach a PulseAudio server"
    fi
else
    stage "pulse-daemon" "SKIP pactl not installed"
fi

# 3. record 2s through the kernel's own code path
python3 - <<'PY'
import sys
sys.path.insert(0, "services")
from pathlib import Path
from lk.obs.audio import record_window, rms_db
wav = Path("/tmp/lk-diag-audio.wav")
wav.unlink(missing_ok=True)
ok = record_window(wav, 2.0)
if not ok:
    print("STAGE record_window        : FAIL both arecord and ffmpeg+pulse recorders failed")
    sys.exit(0)
size = wav.stat().st_size
print(f"STAGE record_window        : OK {size} bytes")
db = rms_db(wav)
if db is None:
    print("STAGE rms_db               : FAIL unreadable wav")
elif db <= -90:
    print(f"STAGE rms_db               : FAIL {db:.1f} dB — pure silence (mic not routed?)")
else:
    gate = "passes" if db > -42 else "below"
    print(f"STAGE rms_db               : OK {db:.1f} dB ({gate} the -42dB speech gate)")
PY

# 4. transcription stack
python3 - <<'PY'
import shutil, sys
sys.path.insert(0, "services")
try:
    import faster_whisper  # noqa: F401
    print("STAGE faster-whisper       : OK importable")
except ImportError as e:
    print(f"STAGE faster-whisper       : FAIL {e} (pip install -e '.[audio]')")
cli = shutil.which("whisper-cli") or shutil.which("whisper")
print(f"STAGE whisper-cli          : {'OK ' + cli if cli else 'absent (fallback unavailable)'}")
from pathlib import Path
wav = Path("/tmp/lk-diag-audio.wav")
if wav.exists() and wav.stat().st_size > 1000:
    from lk.obs.audio import transcribe
    text = transcribe(wav)
    print(f"STAGE transcribe           : {'OK ' + repr(text[:60]) if text else 'empty (silence or no transcriber)'}")
else:
    print("STAGE transcribe           : SKIP no recording from stage 3")
PY
