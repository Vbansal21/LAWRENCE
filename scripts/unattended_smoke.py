#!/usr/bin/env python3
"""Run LAWRENCE without user turns and report operational autonomy."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "apps" / "desktop" / "scripts" / "desktopctl.sh"
BASE = "http://127.0.0.1:8765"


def request(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method="POST" if data else "GET",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())


def count_lines(path: Path) -> int:
    try:
        return sum(1 for line in path.open(encoding="utf-8") if line.strip())
    except OSError:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=3600)
    args = parser.parse_args()
    started = False
    env = os.environ.copy()
    env.update({
        "LK_PROACTIVE_INTERVAL": "900",
        "LK_JOURNAL_MIN_INTERVAL": "900",
        "LK_JOURNAL_MAX_INTERVAL": "1800",
    })
    day = time.strftime("%Y-%m-%d", time.gmtime())
    event_log = ROOT / "memory" / f"context-{day}.log"
    journal = ROOT / "memory" / "journal" / f"{day}.mdx"
    before_log = count_lines(event_log)
    before_journal = journal.stat().st_size if journal.exists() else 0
    try:
        try:
            before = request("/health")
        except Exception:
            subprocess.run([str(CONTROL), "services-start"], cwd=ROOT, env=env, check=True)
            started = True
            for _ in range(80):
                try:
                    before = request("/health")
                    break
                except Exception:
                    time.sleep(0.25)
            else:
                raise RuntimeError("bridge did not become healthy")

        request("/observer", {"observer": "vision", "enabled": True})
        checks = 0
        max_jobs = 0
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            health = request("/health")
            if not health.get("modelHealth"):
                raise RuntimeError("model became unhealthy")
            if not health.get("runtime", {}).get("tick"):
                raise RuntimeError("cognitive tick stopped")
            max_jobs = max(max_jobs, health.get("jobs", {}).get("queued", 0)
                           + health.get("jobs", {}).get("running", 0))
            checks += 1
            time.sleep(min(10, max(0, deadline - time.monotonic())))

        after = request("/health")
        report = {
            "ok": True,
            "seconds": args.seconds,
            "healthChecks": checks,
            "maxJobs": max_jobs,
            "contextChars": {"before": before["context"]["used"], "after": after["context"]["used"]},
            "memoryNodes": {"before": before["memory"]["nodes"], "after": after["memory"]["nodes"]},
            "objectiveLogLines": {"before": before_log, "after": count_lines(event_log)},
            "journalBytes": {
                "before": before_journal,
                "after": journal.stat().st_size if journal.exists() else 0,
            },
        }
        if report["contextChars"]["after"] <= report["contextChars"]["before"]:
            raise RuntimeError(f"watcher context did not advance: {report}")
        if report["objectiveLogLines"]["after"] <= report["objectiveLogLines"]["before"]:
            raise RuntimeError(f"objective log did not advance: {report}")
        if args.seconds >= 1800 and report["journalBytes"]["after"] <= report["journalBytes"]["before"]:
            raise RuntimeError(f"journal did not advance: {report}")
        path = ROOT / ".runtime" / "unattended-report.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if started:
            subprocess.run([str(CONTROL), "services-stop"], cwd=ROOT, env=env, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
