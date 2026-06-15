"""Memory stress harness — by LOGIC, not by model.

Probes the rolling ContextStore's concurrency + schema discipline with a stubbed
(sleeping) compact_fn standing in for model latency. We care about:

  A. LOST-WRITE RACE — compaction snapshots the raw layer, drops the lock for the
     (slow) model call, then rewrites the file to the snapshot's tail. Do appends
     that land DURING that window survive, or are they clobbered?
  B. NO TORN READS    — tail_for_model() during compaction never yields half-written
     JSON (atomic os.replace contract).
  C. CASCADE          — l1→l2→l3 promotion fires and the top layer archives (drops).
  D. SCHEMA RESILIENCE— a corrupt/garbage line in a layer file is skipped, never
     crashes a read or a compaction.
"""
import sys, os, json, time, threading, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path
from lk.ctx.store import ContextStore

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

def _valid(line):
    try:
        json.loads(line); return True
    except Exception:
        return False

def fresh():
    d = Path(tempfile.mkdtemp(prefix="lk-mem-"))
    return d


# ─────────────────────── A. lost-write race during compaction ───────────────────────
section("A. appends during the compaction model-call window must survive")
d = fresh()
started, release = threading.Event(), threading.Event()
def slow_compact(text, layer):
    started.set()            # snapshot taken; we're now "in the model call"
    release.wait(3.0)        # hold here while the main thread appends
    return "SUMMARY-OF-OLD"

store = ContextStore(mem_dir=d, idle_secs=10**9, compact_fn=slow_compact)
for i in range(40):
    store.append(ts=f"2026-06-15T00:00:{i:02d}", kind="turn",
                 compact=f"old{i}", detailed=f"OLD-EVENT-{i}")

th = threading.Thread(target=store._compact_layer, args=(0,), daemon=True)
th.start()
started.wait(3.0)
# These five land while the lock is free and the "model" is running.
for i in range(5):
    store.append(ts=f"2026-06-15T00:01:{i:02d}", kind="turn",
                 compact=f"new{i}", detailed=f"NEW-EVENT-{i}")
release.set()
th.join(5)

raw_lines = [l for l in (d / "rolling-l1.jsonl").read_text().splitlines() if l.strip()]
raw_details = []
for l in raw_lines:
    try: raw_details.append(json.loads(l)["detailed"])
    except Exception: pass
survivors = [i for i in range(5) if f"NEW-EVENT-{i}" in raw_details]
check("all 5 appends made during compaction survive in the raw layer",
      len(survivors) == 5, f"only {len(survivors)}/5 survived — {sorted(survivors)} (LOST-WRITE RACE)")
# size accounting should match the file on disk
disk = len((d / "rolling-l1.jsonl").read_text())
check("size accounting matches disk after the race window", store._l1_size == disk,
      f"tracked={store._l1_size} disk={disk}")
shutil.rmtree(d, ignore_errors=True)


# ─────────────────────── B. no torn reads during compaction ───────────────────────
section("B. tail_for_model never returns torn JSON while compaction rewrites files")
d = fresh()
rel2 = threading.Event()
def slow_compact2(text, layer):
    time.sleep(0.05)
    return "S"
store = ContextStore(mem_dir=d, idle_secs=10**9, compact_fn=slow_compact2)
for i in range(60):
    store.append(ts=f"2026-06-15T00:00:{i:02d}", kind="turn", compact=f"c{i}", detailed=f"D{i}")
torn = {"n": 0}
stop = threading.Event()
def reader():
    while not stop.is_set():
        t = store.tail_for_model()
        # tail_for_model already json-parses defensively; assert it's a clean str
        if t is None or "\x00" in t:
            torn["n"] += 1
def writer():
    for i in range(200):
        store.append(ts=f"2026-06-15T00:02:{i:03d}", kind="turn", compact=f"w{i}", detailed=f"W{i}")
        for _ in range(3):
            store._compact_layer(0)
rs = [threading.Thread(target=reader) for _ in range(3)]
w = threading.Thread(target=writer)
for r in rs: r.start()
w.start(); w.join(20); stop.set()
for r in rs: r.join(2)
check("no torn/null reads observed under read/compact contention", torn["n"] == 0, f"{torn['n']} torn")
check("raw layer file is still valid JSONL after the storm",
      all(_valid(l) for l in (d / "rolling-l1.jsonl").read_text().splitlines() if l.strip()))
shutil.rmtree(d, ignore_errors=True)


# ─────────────────────── C. cascade l1→l2→l3→archive ───────────────────────
section("C. cascade promotes through tiers and the top layer drops (archive)")
d = fresh()
store = ContextStore(mem_dir=d, idle_secs=10**9,
                     compact_fn=lambda text, layer: f"SUM<{len(text)}>")
# Hammer enough events that l1 compacts to l2, l2 fills and cascades to l3.
for i in range(400):
    store.append(ts=f"2026-06-15T00:00:{i:04d}"[:25], kind="turn",
                 compact=f"c{i}", detailed="X" * 200)
    if i % 25 == 0:
        store._compact_layer(0)
for _ in range(5):
    store._compact_layer(0)
l2 = (d / "rolling-l2.jsonl")
check("l2 received compacted summaries", l2.exists() and l2.stat().st_size > 0)
# Force l2 over budget so it cascades to l3.
store.l2_budget = 200
store._compact_layer(0)
l3 = (d / "rolling-l3.jsonl")
check("l3 received cascaded summaries", l3.exists() and l3.stat().st_size > 0,
      "l3 empty — cascade did not reach the archive tier")
shutil.rmtree(d, ignore_errors=True)


# ─────────────────────── D. schema resilience to corrupt lines ───────────────────────
section("D. a corrupt layer line is skipped, never crashes read/compaction")
d = fresh()
store = ContextStore(mem_dir=d, idle_secs=10**9, compact_fn=lambda t, l: "S")
for i in range(10):
    store.append(ts=f"2026-06-15T00:00:{i:02d}", kind="turn", compact=f"c{i}", detailed=f"D{i}")
# Inject garbage directly into the raw file.
p = d / "rolling-l1.jsonl"
p.write_text(p.read_text() + "{ this is not json \n" + "\x00\x00 binary noise\n" + '{"ts":"x"}\n')
ok_read = True
try:
    t = store.tail_for_model()
    check("tail_for_model survives corrupt lines", "D0" in t)
except Exception as e:
    ok_read = False
    check("tail_for_model survives corrupt lines", False, repr(e))
try:
    store._compact_layer(0)
    check("compaction survives corrupt lines", True)
except Exception as e:
    check("compaction survives corrupt lines", False, repr(e))
shutil.rmtree(d, ignore_errors=True)


section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL MEMORY STRESS CHECKS PASSED")
