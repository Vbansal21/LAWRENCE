#!/usr/bin/env python3
"""LAWRENCE v0.1 launcher. Run from repo root: python lk.py [options]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "services"))
from lk.cli import main

if __name__ == "__main__":
    sys.exit(main())
