#!/usr/bin/env python3
"""Start, exercise, and stop the current LAWRENCE MVP service runtime."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "apps" / "desktop" / "scripts" / "desktopctl.sh"
LOCK = ROOT / "memory" / ".writer.lock"
BASE = f"http://127.0.0.1:{os.environ.get('LK_UI_PORT', '8765')}"


def request_json(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"{path} returned HTTP {exc.code}: {detail}") from exc


def current_health() -> dict | None:
    try:
        return request_json("/health")
    except Exception:
        return None


def run_control(action: str) -> None:
    subprocess.run([str(CONTROL), action], cwd=ROOT, check=True)


def wait_for_health(expected: bool, seconds: float = 20) -> dict | None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        health = current_health()
        if bool(health) is expected:
            return health
        time.sleep(0.25)
    raise RuntimeError(f"bridge did not become {'healthy' if expected else 'stopped'}")


def wait_for_job(job_id: str, seconds: float = 180) -> dict:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        job = request_json(f"/jobs/{job_id}")
        if job.get("state") in {"done", "error", "cancelled"}:
            return job
        time.sleep(0.5)
    raise RuntimeError(f"turn job {job_id} did not finish within {seconds:.0f}s")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_writer() -> None:
    owner = json.loads(LOCK.read_text(encoding="utf-8"))
    require(owner.get("role") == "ui-bridge", f"unexpected writer owner: {owner}")
    os.kill(int(owner["pid"]), 0)


def main() -> int:
    started = current_health() is None
    try:
        if started:
            run_control("services-start")
        health = wait_for_health(True)
        require(bool(health and health.get("modelHealth")), "configured model backend is not healthy")
        require(health["runtime"]["writer"] == "ui-bridge", "bridge does not report writer ownership")
        require(health["runtime"]["tick"], "cognitive tick is disabled")
        require(health["runtime"]["journal"], "autonomous journal is disabled")
        require(health["memory"]["nodes"] > 0, "startup backfill produced an empty memory index")
        verify_writer()

        before = int(health["memory"]["nodes"])
        marker = uuid.uuid4().hex[:10]
        queued = request_json("/turn/async", {
            "source": "mvp-smoke",
            "turn": {
                "text": (
                    f"MVP smoke marker {marker}. Using LAWRENCE's own memory, current PLAN, "
                    "original project paper, and cached web knowledge, summarize the core vision "
                    "briefly with citations."
                ),
                "config": {
                    "mode": "Text",
                    "retrieval": True,
                    "maxTokens": 192,
                    "timeout": 180,
                },
            },
        })
        job = wait_for_job(str(queued["jobId"]))
        require(job.get("state") == "done", f"turn failed: {job.get('error') or job}")
        result = job.get("result") or {}
        answer = str(result.get("answer") or "").strip()
        require(bool(answer), "turn returned an empty answer")
        require("Sources" in answer and "[1]" in answer, "grounded turn returned no cited sources")
        require(bool(result.get("userMsgId") and result.get("assistantMsgId")),
                "turn was not persisted to the active chat")

        after = request_json("/health")
        require(int(after["memory"]["nodes"]) >= before + 2,
                f"turn was not indexed: nodes {before} -> {after['memory']['nodes']}")
        print(f"MVP SMOKE: PASS ({after['backend']}; memory {before} -> {after['memory']['nodes']})")
        return 0
    finally:
        if started:
            run_control("services-stop")
            wait_for_health(False)


if __name__ == "__main__":
    raise SystemExit(main())
