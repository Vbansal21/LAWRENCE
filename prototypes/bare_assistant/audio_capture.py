from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def record_audio(out_path: Path, seconds: float) -> Path:
    if seconds <= 0:
        raise RuntimeError("record duration must be greater than zero.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    arecord = shutil.which("arecord")
    if arecord:
        subprocess.run(
            [arecord, "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(int(seconds)), str(out_path)],
            check=True,
        )
        return out_path

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "pulse",
                "-i",
                "default",
                "-t",
                str(seconds),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(out_path),
            ],
            check=True,
        )
        return out_path

    raise RuntimeError("no WSL recorder found. Install arecord/ffmpeg or use /audio PATH.")

