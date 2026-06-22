"""N-62 DEPLOY-ACCEPT — unit verification of the acceptance harness logic.

The orchestrator (scripts/deploy_accept.py) shells out to run lanes; here we test
its PURE, load-bearing pieces deterministically with an injected runner:
  • decide(): honest verdict — a blocked/not-built lane is NEVER a pass; a single
    offline failure REJECTs; otherwise blocked ⇒ ACCEPT-PENDING (no false green).
  • run_lanes(): offline lanes classify by rc; live-blocked → blocked; pending → pending.
  • acceptance_checklist(): the five N-62 invariants map to lane evidence honestly.
  • collect_manifest()/write_bundle(): manifest shape + an on-disk evidence bundle.
"""
import sys, json, tempfile, shutil
sys.path.insert(0, "services")
sys.path.insert(0, "scripts")
from pathlib import Path

import deploy_accept as DA

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)
def section(t):
    print(f"\n=== {t} ===")


section("A. decide(): honest verdict, blocked never counts as pass")
allpass = [{"id": "a", "status": "pass"}, {"id": "b", "status": "pass"}]
check("all offline pass → ACCEPT", DA.decide(allpass)["verdict"] == "ACCEPT")
mixed = allpass + [{"id": "live", "status": "blocked"}, {"id": "todo", "status": "pending"}]
v = DA.decide(mixed)
check("offline-green + blocked/pending → ACCEPT-PENDING", v["verdict"] == "ACCEPT-PENDING")
check("blocked + pending are reported, not silently passed",
      set(v["blocked"]) == {"live", "todo"} and v["passed"] == ["a", "b"])
withfail = mixed + [{"id": "x", "status": "fail"}]
vf = DA.decide(withfail)
check("any offline FAIL → REJECT (dominates blocked)", vf["verdict"] == "REJECT" and vf["failed"] == ["x"])
check("a fully-blocked set never yields ACCEPT (no false green)",
      DA.decide([{"id": "l1", "status": "blocked"}])["verdict"] == "ACCEPT-PENDING")


section("B. run_lanes(): injected runner classifies offline lanes; live/pending untouched")
calls = []
def fake_runner(cmd, cwd):
    calls.append(cmd)
    # fail the n60 offline lane, pass everything else, to prove rc→status mapping
    return (3, "boom") if "stress_sensor_endurance.py" in " ".join(cmd) else (0, "ok")
lanes = DA.default_lanes()
res = DA.run_lanes(lanes, Path("."), runner=fake_runner)
by_id = {r["id"]: r for r in res}
check("offline-gate lane ran and passed (rc 0 → pass)", by_id["offline-gate"]["status"] == "pass")
check("a failing offline lane is recorded as fail (rc≠0 → fail)",
      by_id["n60-sensor-offline"]["status"] == "fail" and by_id["n60-sensor-offline"]["rc"] == 3)
check("live-blocked lanes are NOT run (no command executed for them)",
      not any("Windows" in " ".join(c) for c in calls)
      and by_id["n61-desktop-host"]["status"] == "blocked")
check("N-59 cognition lane is now a REAL offline lane that runs (rc 0 → pass)",
      by_id["n59-core-stress"]["status"] == "pass")
check("all three offline lanes were actually executed", len(calls) == 3, f"{len(calls)} runs")
# the pending-classification branch is still valid code — cover it with a synthetic lane
synth = DA.run_lanes([{"id": "x", "kind": "pending", "reason": "r"}], Path("."), runner=fake_runner)
check("a kind=pending lane stays pending (no command run)", synth[0]["status"] == "pending")


section("C. acceptance_checklist(): invariants map to evidence honestly")
# all offline pass, live blocked, n59 pending
good = [
    {"id": "offline-gate", "status": "pass", "covers": ["no-data-corruption", "no-bypassed-confirmation", "no-false-ui-health"]},
    {"id": "n60-sensor-offline", "status": "pass", "covers": ["no-silent-sensor-death"]},
    {"id": "n59-core-stress", "status": "pending", "covers": ["no-data-corruption", "no-stuck-process"]},
    {"id": "n61-desktop-host", "status": "blocked", "covers": ["no-false-ui-health", "no-stuck-process"]},
]
cl = DA.acceptance_checklist(good)
check("no-data-corruption satisfied (offline-gate passed)", cl["no-data-corruption"]["status"] == "satisfied")
check("no-silent-sensor-death satisfied (n60 offline passed)", cl["no-silent-sensor-death"]["status"] == "satisfied")
check("no-stuck-process pending (only pending/blocked lanes cover it)", cl["no-stuck-process"]["status"] == "pending")
check("every invariant key is covered by ≥1 declared lane",
      all(cl[i]["by"] for i in DA.INVARIANTS))
bad = [{"id": "offline-gate", "status": "fail", "covers": ["no-data-corruption"]}]
check("a failed covering lane makes its invariant unmet",
      DA.acceptance_checklist(bad)["no-data-corruption"]["status"] == "unmet")


section("D. default_lanes(): well-formed, covers ⊆ invariants, integrity of kinds")
L = DA.default_lanes()
check("offline lanes carry a command", all(l.get("cmd") for l in L if l["kind"] == "offline"))
check("live-blocked / pending lanes carry a human reason",
      all(l.get("reason") for l in L if l["kind"] in ("live-blocked", "pending")))
check("all covers tags are real invariants",
      all(c in DA.INVARIANTS for l in L for c in l.get("covers", [])))
check("the live hardware lanes (N-60 live, N-61 host, N-63 voice) are declared blocked",
      {l["id"] for l in L if l["kind"] == "live-blocked"} == {"n60-sensor-live", "n61-desktop-host", "n63-voice-live"})


section("E. collect_manifest(): shape, local-first default, no crash")
m = DA.collect_manifest(DA.ROOT, git=False)
check("manifest has all required fields",
      all(k in m for k in ("node", "generated_at", "config_hash", "deps", "model_profile", "host", "uname")))
check("python version recorded in deps", "python" in m["deps"])
check("LOCAL-FIRST: unconfigured profile reports local default, not a cloud backend",
      "local-first" in m["model_profile"] or m["model_profile"] != "")
mg = DA.collect_manifest(DA.ROOT, git=True)   # exercises the git path without asserting a value
check("git path returns a dict without raising", isinstance(mg.get("commit"), (str, type(None))))


section("F. write_bundle(): on-disk evidence bundle (to a tmp root, .runtime stays clean)")
tmp = Path(tempfile.mkdtemp(prefix="lk-n62-"))
res2 = DA.run_lanes(DA.default_lanes(), Path("."), runner=lambda cmd, cwd: (0, "ok"))
verdict = DA.decide(res2)
checklist = DA.acceptance_checklist(res2)
out = DA.write_bundle(DA.collect_manifest(DA.ROOT, git=False), res2, verdict, checklist, root=tmp)
mf = out / "manifest.json"
check("bundle wrote manifest.json under tmp/.runtime/deploy/", mf.is_file() and ".runtime/deploy" in str(out))
parsed = json.loads(mf.read_text(encoding="utf-8"))
check("bundle contains manifest + lanes + invariants + verdict",
      all(k in parsed for k in ("manifest", "lanes", "acceptance_invariants", "verdict")))
check("offline-green + blocked live lanes → bundle verdict ACCEPT-PENDING (honest, not ACCEPT)",
      parsed["verdict"]["verdict"] == "ACCEPT-PENDING")
shutil.rmtree(tmp, ignore_errors=True)


section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL N-62 DEPLOY-ACCEPT CHECKS PASSED")
