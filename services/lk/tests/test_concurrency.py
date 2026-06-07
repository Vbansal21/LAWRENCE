"""Hammer ContextStore under concurrent writers + compaction + readers."""
import sys, tempfile, shutil, threading, time, random, json
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone
from lk.ctx.store import ContextStore

tmp = Path(tempfile.mkdtemp())
ccalls = {"l1":0,"l2":0}
def slow_compact(text, level):
    ccalls[level]+=1
    time.sleep(random.uniform(0.005, 0.03))  # simulate model latency
    return f"S[{level}] {len(text)}c"
ctx = ContextStore(mem_dir=tmp/"m", compact_fn=slow_compact)
ctx._min_compact_secs = 0
ctx.l2_budget = 1200

errors = []
empty_tail_with_data = [0]
stop = threading.Event()

def writer(wid):
    try:
        for i in range(150):
            ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="vision",
                       compact=f"w{wid}-{i}", detailed=f"writer{wid} event {i} " + "p"*random.randint(200,1500))
            time.sleep(random.uniform(0, 0.003))
    except Exception as e:
        errors.append(("writer", repr(e)))

def reader():
    try:
        while not stop.is_set():
            t = ctx.tail_for_model()
            # if store has data, tail must never be the empty sentinel
            if ctx._l1_size > 0 and t == "(no context yet)":
                empty_tail_with_data[0] += 1
            # every line must be parseable structure (no half-written json garbage)
            time.sleep(0.001)
    except Exception as e:
        errors.append(("reader", repr(e)))

def statuser():
    try:
        while not stop.is_set():
            _ = ctx.working_budget(); _ = ctx.show_layer("l1"); _ = ctx.show_layer("l2")
            time.sleep(0.005)
    except Exception as e:
        errors.append(("status", repr(e)))

writers = [threading.Thread(target=writer, args=(w,)) for w in range(6)]
readers = [threading.Thread(target=reader) for _ in range(3)]
st = threading.Thread(target=statuser)
for t in writers: t.start()
for t in readers: t.start()
st.start()
for t in writers: t.join()
time.sleep(1.0)  # let compaction drain
stop.set()
for t in readers: t.join()
st.join()
time.sleep(0.5)

# final integrity: every L1/L2/L3 line is valid JSON
def all_valid(p):
    if not p.exists():
        return True   # layer not created yet (e.g. no cascade) — vacuously valid
    try:
        for l in p.read_text().splitlines():
            if l.strip(): json.loads(l)
        return True
    except Exception as e:
        errors.append(("integrity", f"{p.name}: {e}")); return False
ok_l1 = all_valid(ctx._l1); ok_l2 = all_valid(ctx._l2); ok_l3 = all_valid(ctx._l3)

print(f"compactions: {ccalls}")
print(f"errors: {errors}")
print(f"empty-tail-while-data races: {empty_tail_with_data[0]}")
print(f"final sizes L1={ctx._l1_size} L2={ctx._l2_size} L3={ctx._l3_size}")
print(f"JSON integrity L1={ok_l1} L2={ok_l2} L3={ok_l3}")
shutil.rmtree(tmp, ignore_errors=True)
ok = (not errors) and empty_tail_with_data[0]==0 and ok_l1 and ok_l2 and ok_l3 and ccalls["l1"]>0
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
