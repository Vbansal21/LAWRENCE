#!/usr/bin/env python3
"""LAWRENCE out-of-process sensor agent launcher. Run from repo root:

    python3 lk_sensor.py --spool memory/spool [--no-vision] [--no-audio]

Captures + preprocesses screen/audio and publishes events to a spool dir for a
(possibly headless / containerized) kernel started with --ingest-spool.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "services"))
from lk.sensor import main

if __name__ == "__main__":
    sys.exit(main())
