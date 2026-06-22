#!/usr/bin/env python3
"""N-62 DEPLOY-ACCEPT — current-tree MVP deployment acceptance harness.

PLAN §M.5 / §N.1 N-62: the diamond convergence — N-59 core stress, N-60 sensor
endurance, and N-61 desktop/host stress must all pass against the SAME commit and
configuration. N-62 only **collects evidence and declares pass/fail; it does not
repair failures.**

The live lanes (N-60 live mic/display + 30-min wall-clock, N-61 Tauri rebuild +
Windows ARM64 host, N-63 live voice) cannot run in a headless sandbox. This harness
therefore:
  • runs every OFFLINE lane it can and records the result,
  • records each live lane as explicitly BLOCKED (never silently passed — gate #1
    integrity: no false green),
  • assembles one evidence bundle (manifest + per-lane logs) under .runtime/deploy/
    (git-ignored), and
  • returns an HONEST verdict:
      ACCEPT          all required lanes (incl. live) green
      ACCEPT-PENDING  every offline lane green; ≥1 live/not-built lane blocked
      REJECT          ≥1 offline lane FAILED  → that lane returns to the frontier

The pure decision/manifest logic is import-tested by
services/lk/tests/test_deploy_accept.py; only the orchestration shells out.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The five acceptance invariants from PLAN §N.1 N-62 ("Acceptance requires no
# unresolved data corruption, stuck process, false UI health, silent sensor
# death, or bypassed confirmation."). Each lane declares which it provides
# evidence for via its "covers" tags.
INVARIANTS = {
    "no-data-corruption":       "no unresolved data corruption (no torn durable records)",
    "no-stuck-process":         "no stuck job / orphaned process; clean shutdown",
    "no-false-ui-health":       "no false UI health (the popup is honest about state)",
    "no-silent-sensor-death":   "no silent sensor / observer death",
    "no-bypassed-confirmation": "no bypassed confirmation (agency / policy gate holds)",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────── manifest collection ───────────────────────────────

def _git(root: Path, args: list[str]) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True,
                             text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def _config_hash(root: Path) -> str | None:
    """A stable digest over the deployment-relevant config so the same evidence
    bundle is tied to one configuration (PLAN: 'against the same … configuration')."""
    candidates = [
        root / "apps" / "desktop" / "src-tauri" / "tauri.conf.json",
        root / "apps" / "desktop" / "src-tauri" / "Cargo.toml",
        root / "pyproject.toml",
        root / "scripts" / "check.sh",
    ]
    h = hashlib.sha256()
    seen = False
    for p in sorted(candidates):
        try:
            h.update(p.read_bytes())
            h.update(b"\0")
            seen = True
        except OSError:
            continue
    return h.hexdigest() if seen else None


def _deps() -> dict[str, str]:
    info = {"python": platform.python_version()}
    for mod in ("PIL", "faster_whisper"):
        try:
            m = __import__(mod)
            info[mod] = getattr(m, "__version__", "present")
        except Exception:
            info[mod] = "absent"
    return info


def _model_profile(root: Path) -> str:
    """Best-effort active model-profile name; never raises. LOCAL-FIRST: an
    unconfigured tree reports the local default, not a cloud backend."""
    for cfg in (Path.home() / ".lawrence" / "lk.json", root / "lk.json"):
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            prof = data.get("model_profile") or data.get("modelProfile") or data.get("profile")
            if prof:
                return str(prof)
        except Exception:
            continue
    return "unconfigured (local-first default)"


def collect_manifest(root: Path = ROOT, *, git: bool = True) -> dict:
    return {
        "node": "N-62",
        "generated_at": iso_now(),
        "commit": _git(root, ["rev-parse", "HEAD"]) if git else None,
        "branch": _git(root, ["rev-parse", "--abbrev-ref", "HEAD"]) if git else None,
        "dirty": bool(_git(root, ["status", "--porcelain"])) if git else None,
        "config_hash": _config_hash(root),
        "deps": _deps(),
        "model_profile": _model_profile(root),
        "host": platform.platform(),
        "uname": " ".join(platform.uname()),
    }


# ─────────────────────────────── lanes ───────────────────────────────

def default_lanes(root: Path = ROOT) -> list[dict]:
    py = sys.executable or "python3"
    return [
        {"id": "offline-gate", "name": "offline contract gate (scripts/check.sh suites)",
         "kind": "offline", "cmd": ["bash", str(root / "scripts" / "check.sh")],
         "covers": ["no-data-corruption", "no-bypassed-confirmation", "no-false-ui-health"]},
        {"id": "n60-sensor-offline", "name": "N-60 sensor endurance (offline deterministic lane)",
         "kind": "offline", "cmd": [py, str(root / "services" / "lk" / "tests" / "stress_sensor_endurance.py")],
         "covers": ["no-silent-sensor-death"]},
        {"id": "n59-core-stress", "name": "N-59 core/runtime stress orchestrator (offline lane)",
         "kind": "offline", "cmd": [py, str(root / "services" / "lk" / "tests" / "stress_core.py")],
         "covers": ["no-data-corruption", "no-stuck-process"]},
        {"id": "n60-sensor-live", "name": "N-60 live mic/display + 30-min endurance + WER",
         "kind": "live-blocked", "reason": "requires real microphone + display + 30-min wall-clock (hardware)",
         "covers": ["no-silent-sensor-death"]},
        {"id": "n61-desktop-host", "name": "N-61 desktop lifecycle + Windows ARM64 host",
         "kind": "live-blocked", "reason": "requires Tauri rebuild + Windows ARM64 host (hardware)",
         "covers": ["no-false-ui-health", "no-stuck-process"]},
        {"id": "n63-voice-live", "name": "N-63 live-mic voice capture verify",
         "kind": "live-blocked", "reason": "requires a live microphone under WSLg (hardware)",
         "covers": ["no-silent-sensor-death"]},
    ]


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=1800)
        tail = "\n".join((out.stdout + out.stderr).splitlines()[-30:])
        return out.returncode, tail
    except Exception as exc:
        return 1, f"runner error: {exc!r}"


def run_lanes(lanes: list[dict], root: Path = ROOT, *, runner=_run) -> list[dict]:
    """Execute offline lanes; record live/pending lanes as not-green WITHOUT running.
    `runner` is injectable so the unit test drives this deterministically."""
    results = []
    for ln in lanes:
        r = dict(ln)
        if ln["kind"] == "offline":
            rc, tail = runner(ln["cmd"], root)
            r["status"] = "pass" if rc == 0 else "fail"
            r["rc"] = rc
            r["tail"] = tail
        elif ln["kind"] == "pending":
            r["status"] = "pending"
        else:  # live-blocked
            r["status"] = "blocked"
        results.append(r)
    return results


# ─────────────────────────────── decision (pure) ───────────────────────────────

def decide(results: list[dict]) -> dict:
    """Honest verdict. A blocked/pending lane is NEVER counted as a pass."""
    failed = [r["id"] for r in results if r["status"] == "fail"]
    blocked = [r["id"] for r in results if r["status"] in ("blocked", "pending")]
    passed = [r["id"] for r in results if r["status"] == "pass"]
    if failed:
        verdict, reason = "REJECT", f"{len(failed)} offline lane(s) FAILED: {failed} — return to frontier"
    elif blocked:
        verdict = "ACCEPT-PENDING"
        reason = (f"all {len(passed)} offline lane(s) green; {len(blocked)} lane(s) "
                  f"blocked/not-built (hardware or pending): {blocked}")
    else:
        verdict, reason = "ACCEPT", "all required lanes green"
    return {"verdict": verdict, "reason": reason,
            "failed": failed, "blocked": blocked, "passed": passed}


def acceptance_checklist(results: list[dict]) -> dict:
    """Map the five N-62 acceptance invariants onto lane evidence:
      satisfied — a PASSED offline lane covers it
      unmet     — a covering lane FAILED
      pending   — only blocked/not-built lanes cover it (no offline proof yet)
    """
    out = {}
    for inv, desc in INVARIANTS.items():
        lanes = [r for r in results if inv in r.get("covers", [])]
        if any(r["status"] == "fail" for r in lanes):
            status = "unmet"
        elif any(r["status"] == "pass" for r in lanes):
            status = "satisfied"
        else:
            status = "pending"
        out[inv] = {"status": status, "desc": desc, "by": [r["id"] for r in lanes]}
    return out


# ─────────────────────────────── evidence bundle ───────────────────────────────

def write_bundle(manifest: dict, results: list[dict], verdict: dict,
                 checklist: dict, root: Path = ROOT) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = root / ".runtime" / "deploy" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    # per-lane logs (tails) as separate files; keep the manifest compact
    lanes_summary = []
    for r in results:
        entry = {k: r.get(k) for k in ("id", "name", "kind", "status", "rc", "reason", "covers")}
        if r.get("tail"):
            (out_dir / f"lane-{r['id']}.log").write_text(r["tail"], encoding="utf-8")
        lanes_summary.append(entry)
    bundle = {
        "manifest": manifest,
        "lanes": lanes_summary,
        "acceptance_invariants": checklist,
        "verdict": verdict,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_dir


# ─────────────────────────────── orchestration ───────────────────────────────

def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv          # collect manifest + declare lanes, run nothing
    manifest = collect_manifest(ROOT)
    lanes = default_lanes(ROOT)
    if dry:
        results = [{**ln, "status": ("pending" if ln["kind"] == "pending"
                                     else "blocked" if ln["kind"] == "live-blocked"
                                     else "not-run")} for ln in lanes]
    else:
        results = run_lanes(lanes, ROOT)
    verdict = decide(results)
    checklist = acceptance_checklist(results)
    out_dir = write_bundle(manifest, results, verdict, checklist, ROOT)

    print("=== N-62 DEPLOY-ACCEPT ===")
    print(f"commit {manifest['commit']}  branch {manifest['branch']}  dirty={manifest['dirty']}")
    print(f"config_hash {manifest['config_hash']}")
    print(f"model_profile {manifest['model_profile']}")
    print(f"host {manifest['host']}")
    print("\nlanes:")
    for r in results:
        extra = f"  rc={r['rc']}" if "rc" in r else (f"  ({r.get('reason')})" if r.get("reason") else "")
        print(f"  [{r['status']:>7}] {r['id']:<20} {r['name']}{extra}")
    print("\nacceptance invariants:")
    for inv, c in checklist.items():
        print(f"  [{c['status']:>9}] {inv:<26} via {c['by']}")
    print(f"\nVERDICT: {verdict['verdict']} — {verdict['reason']}")
    print(f"evidence bundle: {out_dir}")
    # exit nonzero only on a true REJECT; ACCEPT-PENDING is an honest, non-failing state
    return 1 if verdict["verdict"] == "REJECT" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
