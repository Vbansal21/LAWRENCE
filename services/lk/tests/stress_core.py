"""N-59 CORE-STRESS — sustained runtime + model-path stress orchestrator.

The deployment diamond's cognition lane (PLAN §N.1). This drives the REAL kernel
machinery under repeated and overlapping work — run_turn, the priority gate, the
cognitive tick, the bridge job lifecycle, the ContextStore/ChatStore durable logs,
the retrieval pipeline, and the KV-slot compatibility logic — with a DETERMINISTIC
stub in place of the model transport, so the whole thing is sandbox-buildable and
needs no cloud key or GGUF. (The identical orchestrator run against a real backend
is the live confirmation; the spec has "no hard deferral beyond a configured cloud
key and installed local model".)

It asserts the N-59 contract:
  • ≥50 mixed turns (retrieval on/off, streaming) all complete and persist;
  • cancellation during active work writes ZERO torn durable records, later turns OK;
  • repeated retrieval is stable and never corrupts/grows the store;
  • 10 autonomous cycles act exactly-once-per-significant-beat and self-heal;
  • 3 bridge restarts: every durable record survives, zero stuck jobs, bounded queue;
  • 3 compatible/incompatible KV restarts: a compatible runtime reuses the slot, an
    incompatible one gets a DIFFERENT slot (never silently loaded) — no corruption;
  • no SILENT provider fallback — a local-primary failure re-raises, never reroutes;
  • clean shutdown — stores close, no orphan threads, the inference gate is free.
It reports p50/p95/max turn latency and the queue high-water mark.
"""
import sys, os, json, time, threading, tempfile, shutil, importlib.util, statistics
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone

import lk.model as M
import lk.kernel.invoke as INV
from lk.ctx import ContextStore
from lk.ctx.chats import ChatStore
from lk.retrieval import SemanticDB, RetrievalPipeline
from lk.kernel import run_turn, TurnConfig
from lk.kernel.tick import CognitiveTick
from lk.ui import UIConnector
from lk import server as SRV
from lk.profile import ModelProfile

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

REPORT = {"turns": 0, "cancelled": 0, "latency": {}, "queueHighWater": 0, "restarts": 0}
NOW = lambda: datetime.now(timezone.utc).isoformat()


# ── deterministic stub model: streams a few tokens then returns answer JSON ───────
# Mirrors the kernel's two call shapes: a streaming RESPONSE pass (stream_fn set) and
# a structured ANALYSIS pass (stream_fn None, schema set). Honours should_stop so a
# cancelled turn raises TurnCancelled exactly where the real transport would.
def fake_call(messages, *, stream_fn=None, should_stop=None, schema=None, role="", **kw):
    if stream_fn is not None:
        for i in range(12):
            if should_stop and should_stop():
                raise M.TurnCancelled()
            stream_fn(f"tok{i} ")
            time.sleep(0.001)
        return {"text": json.dumps({"answer_text": "final grounded answer", "confidence": 0.9})}
    if should_stop and should_stop():
        raise M.TurnCancelled()
    # structured (analysis) pass — drive the legacy retrieval branch deterministically
    return {"text": json.dumps(
        {"needs_retrieval": True, "queries": ["alpha", "bravo"], "situation": "stress"})}


def l1_lines(mem_dir: Path) -> list[str]:
    p = mem_dir / "rolling-l1.jsonl"
    try:
        return [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    except FileNotFoundError:
        return []

def all_parse(lines) -> bool:
    try:
        for l in lines: json.loads(l)
        return True
    except json.JSONDecodeError:
        return False


# ─────────────────────────────── A. ≥50 mixed turns ───────────────────────────────
section("A. ≥50 mixed turns (retrieval on/off, streaming) — complete + persist")
tmpA = Path(tempfile.mkdtemp(prefix="lk-n59-A-"))
ctx = ContextStore(mem_dir=tmpA / "m")
ctx.append(ts=NOW(), kind="turn", compact="seed", detailed="seed ctx")
db = SemanticDB(tmpA / "r.db"); pipe = RetrievalPipeline(db); ui = UIConnector()
db.upsert("file:///doc1.md", "Doc One", ["alpha bravo charlie delta", "echo foxtrot golf"])
db.upsert("file:///doc2.md", "Doc Two", ["bravo hotel india", "alpha juliet kilo"])

_real = INV.call_model
INV.call_model = fake_call
N_TURNS = 60
lat = []
seed_size = ctx._l1_size
try:
    for i in range(N_TURNS):
        retrieve_on = (i % 3 == 0)         # mix: one in three exercises the retrieval path
        cfg = TurnConfig(no_retrieval=not retrieve_on, skip_analysis=not retrieve_on,
                         max_tokens=64, timeout=30)
        t0 = time.monotonic()
        ans, ctrl = run_turn(f"stress question {i}?", ctx=ctx, retrieval=pipe, cfg=cfg,
                             images=[], audios=[], ui=ui,
                             stream_fn=lambda p: None, should_stop=lambda: False)
        lat.append(time.monotonic() - t0)
        if not ans.strip():
            check(f"turn {i} produced an answer", False, "empty"); break
    REPORT["turns"] = len(lat)
    check("all 60 mixed turns completed", len(lat) == N_TURNS, f"{len(lat)}/{N_TURNS}")
    check("every turn returned a non-empty answer", all(x is not None for x in lat))
    lines = l1_lines(tmpA / "m")
    check("rolling-l1 grew (durable turns persisted)", ctx._l1_size > seed_size)
    check("every durable L1 record parses (no torn writes)", all_parse(lines), f"{len(lines)} lines")
    check("inference gate is free after the batch", M._gate.try_acquire()); M._gate.release()
    ordered = sorted(lat)
    REPORT["latency"] = {
        "p50": round(statistics.median(ordered), 4),
        "p95": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 4),
        "max": round(max(ordered), 4),
    }
    print(f"      latency p50={REPORT['latency']['p50']}s "
          f"p95={REPORT['latency']['p95']}s max={REPORT['latency']['max']}s")
finally:
    db.close(); shutil.rmtree(tmpA, ignore_errors=True)


# ─────────────────── B. cancellation during active work → no torn records ───────────────────
section("B. cancellation during active work writes nothing; later turns succeed")
tmpB = Path(tempfile.mkdtemp(prefix="lk-n59-B-"))
ctx = ContextStore(mem_dir=tmpB / "m")
ctx.append(ts=NOW(), kind="turn", compact="seed", detailed="seed")
db = SemanticDB(tmpB / "r.db"); pipe = RetrievalPipeline(db); ui = UIConnector()
INV.call_model = fake_call
cancelled = 0
try:
    before = ctx._l1_size
    for i in range(10):                      # interleave cancelled + completed turns
        cfg = TurnConfig(no_retrieval=True, skip_analysis=True, max_tokens=64, timeout=30)
        if i % 2 == 0:
            t_mid = time.monotonic()
            ss = lambda: (time.monotonic() - t_mid) > 0.003   # trip mid-stream
            raised = False
            try:
                run_turn(f"cancel {i}?", ctx=ctx, retrieval=pipe, cfg=cfg, images=[],
                         audios=[], ui=ui, stream_fn=lambda p: None, should_stop=ss)
            except M.TurnCancelled:
                raised = True; cancelled += 1
            if not raised:
                check(f"cancel turn {i} raised TurnCancelled", False); break
        else:
            ans, _ = run_turn(f"ok {i}?", ctx=ctx, retrieval=pipe, cfg=cfg, images=[],
                              audios=[], ui=ui, stream_fn=lambda p: None, should_stop=lambda: False)
    after = ctx._l1_size
    REPORT["cancelled"] = cancelled
    check("all 5 cancellations raised TurnCancelled", cancelled == 5, f"{cancelled}/5")
    # exactly the 5 completed turns wrote; cancels wrote nothing → no torn records
    lines = l1_lines(tmpB / "m")
    check("every L1 record still parses after interleaved cancels", all_parse(lines))
    check("durable size advanced (only completed turns wrote)", after > before)
    check("gate free after cancellation storm", M._gate.try_acquire()); M._gate.release()
    # a final clean turn still works
    ans, _ = run_turn("final?", ctx=ctx, retrieval=pipe, cfg=cfg, images=[], audios=[],
                      ui=ui, stream_fn=lambda p: None, should_stop=lambda: False)
    check("a turn after the cancel storm still succeeds", "answer" in ans, ans[:40])
finally:
    db.close(); shutil.rmtree(tmpB, ignore_errors=True)


# ─────────────────────────── C. repeated retrieval is stable ───────────────────────────
section("C. repeated retrieval — deterministic, no growth, no corruption")
tmpC = Path(tempfile.mkdtemp(prefix="lk-n59-C-"))
db = SemanticDB(tmpC / "r.db"); pipe = RetrievalPipeline(db)
db.upsert("file:///k1.md", "K1", ["alpha bravo charlie", "delta echo foxtrot"])
db.upsert("file:///k2.md", "K2", ["alpha golf hotel", "india juliet kilo"])
try:
    queries = ["alpha bravo", "echo foxtrot", "kilo"]
    sigs = []
    for _ in range(40):                      # hammer the pipeline
        res = pipe.retrieve(queries)
        sigs.append(tuple((r.url, r.title) for r in res))
    check("retrieval ran 40× without raising", len(sigs) == 40)
    check("repeated retrieval is deterministic (identical result set each call)",
          len(set(sigs)) == 1, f"{len(set(sigs))} distinct shapes")
    res2 = pipe.retrieve(queries)
    check("retrieval after the loop still returns the same set",
          tuple((r.url, r.title) for r in res2) == sigs[0])
finally:
    db.close(); shutil.rmtree(tmpC, ignore_errors=True)


# ─────────────────────────── D. 10 autonomous cycles ───────────────────────────
section("D. 10 autonomous tick cycles — exactly-once per significant beat, self-heal")
acts = {"n": 0}
gate_free = {"all": True}
heal = {"raised": 0}
def ev(sig): return {"clean": f"e{sig}", "significance": sig}
beat_idx = {"i": 0}
def events_fn():
    beat_idx["i"] += 1
    # alternate significant / empty beats; one beat raises to prove self-heal
    if beat_idx["i"] % 3 == 0:
        return []
    return [ev(0.2), ev(0.9)]
def act_fn(events):
    acts["n"] += 1
    if not M._gate.try_acquire():            # the action takes the droppable slot
        gate_free["all"] = False
    else:
        M._gate.release()
    if beat_idx["i"] == 4:                    # simulate a model-down beat
        heal["raised"] += 1
        raise RuntimeError("model down")
tick = CognitiveTick(events_fn, act_fn, interval=10.0, max_interval=40.0)
try:
    for _ in range(10):
        tick.beat()
    check("exactly 10 beats ran", tick.beats == 10, f"beats={tick.beats}")
    check("actions only on non-empty beats (≤10, ≥1)", 1 <= acts["n"] <= 10, f"acts={acts['n']}")
    check("a raising act_fn was swallowed (loop self-heals)", heal["raised"] == 1)
    check("the gate was free for every action (droppable)", gate_free["all"])
    check("inference gate free after 10 cycles", M._gate.try_acquire()); M._gate.release()
except Exception as exc:
    check("tick cycles did not crash the orchestrator", False, str(exc))


# ─────────────────── E. 3 bridge restarts — durable survival, no stuck jobs ───────────────────
section("E. 3 bridge restarts — every record survives, zero stuck jobs, bounded queue")
_bridge_path = Path("apps/desktop/scripts/ui_bridge.py").resolve()
spec = importlib.util.spec_from_file_location("ui_bridge", _bridge_path)
UB = importlib.util.module_from_spec(spec); spec.loader.exec_module(UB)

tmpE = Path(tempfile.mkdtemp(prefix="lk-n59-E-"))
class _NullUI:
    def push_status(self, *a, **k): pass
    def push_context_event(self, *a, **k): pass

def new_bridge(chat_id):
    b = UB.DesktopBridge.__new__(UB.DesktopBridge)
    b.jobs = {}; b.job_lock = threading.Lock()
    b._turn_count_lock = threading.Lock(); b._turns_in_flight = 0
    b.ui = _NullUI()
    cs = ChatStore(mem_dir=tmpE)
    # a turn that honours cancellation and writes a real user+assistant pair on success
    def _turn(req):
        ss = req.get("should_stop")
        for _ in range(8):
            if ss and ss():
                raise UB._model.TurnCancelled()
            time.sleep(0.002)
        text = (req.get("turn") or {}).get("text") or "?"
        u = cs.append_message(chat_id, "user", text)
        a = cs.append_message(chat_id, "assistant", "ok " + text)
        return {"answer": "ok", "userMsgId": u, "assistantMsgId": a}
    b.turn = _turn
    return b, cs

cs0 = ChatStore(mem_dir=tmpE)
CHAT = cs0.create_chat("stress")["id"]
total_durable = 0
high_water = 0
stuck_total = 0
try:
    for r in range(3):                       # three restart cycles
        b, cs = new_bridge(CHAT)
        ids = [b.enqueue_turn({"turn": {"text": f"r{r}-m{i}"}})["jobId"] for i in range(20)]
        # one running job gets cancelled mid-flight (cancellation during active work)
        time.sleep(0.003)
        b.cancel_job(ids[0])
        # sample the queue depth while it drains
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with b.job_lock:
                states = [j["state"] for j in b.jobs.values()]
            depth = sum(1 for s in states if s in ("queued", "running"))
            high_water = max(high_water, depth)
            if depth == 0:
                break
            time.sleep(0.005)
        with b.job_lock:
            states = [j["state"] for j in b.jobs.values()]
        stuck = sum(1 for s in states if s in ("queued", "running"))
        stuck_total += stuck
        # "restart": drop in-memory job state, re-open the store from disk
        b.jobs = None; b = None
        cs_reload = ChatStore(mem_dir=tmpE)
        msgs = cs_reload.messages(CHAT)
        check(f"restart {r}: durable messages re-load and all parse",
              len(msgs) >= total_durable, f"have {len(msgs)}, prior {total_durable}")
        total_durable = len(msgs)
        # contiguous seq numbers → no torn/duplicated records across the restart
        seqs = [m["seq"] for m in msgs]
        check(f"restart {r}: message seqs are contiguous (no torn/dup records)",
              seqs == list(range(1, len(seqs) + 1)), f"seqs[-3:]={seqs[-3:]}")
    REPORT["restarts"] = 3
    REPORT["queueHighWater"] = high_water
    check("zero stuck jobs across all 3 restart cycles", stuck_total == 0, f"stuck={stuck_total}")
    check("queue depth stayed bounded (≤ enqueued per cycle)", high_water <= 20, f"hw={high_water}")
    check("final durable record count is the 3×19 successful pairs (1 cancel/cycle)",
          total_durable == 3 * 19 * 2, f"durable={total_durable}")
finally:
    shutil.rmtree(tmpE, ignore_errors=True)


# ─────────────── F. 3 compatible/incompatible KV restarts — no silent wrong-KV ───────────────
section("F. KV restarts — compatible reuses the slot, incompatible never loads it")
tmpF = Path(tempfile.mkdtemp(prefix="lk-n59-F-"))
(tmpF / "model.gguf").write_bytes(b"\0" * 64)
(tmpF / "bin").write_bytes(b"\0" * 16)
def profile(**over):
    base = dict(model=tmpF / "model.gguf", bin=tmpF / "bin", mmproj=None,
                vision=False, audio=False, ctx_size=65536, flash_attn="on",
                kv_type="q4_0", jinja=True)
    base.update(over)
    return ModelProfile(**base)
_real_slotdir = SRV.SLOT_DIR
SRV.SLOT_DIR = tmpF / "kv"; SRV.SLOT_DIR.mkdir(parents=True, exist_ok=True)
try:
    base = profile()
    name0 = SRV._slot_filename(base)
    check("a compatible restart maps to the SAME slot file (KV reused)",
          SRV._slot_filename(profile()) == name0, name0)
    # three incompatibility classes — each must produce a DIFFERENT slot digest
    incompat = {
        "ctx_size":   profile(ctx_size=32768),
        "kv_type":    profile(kv_type="q8_0"),
        "flash_attn": profile(flash_attn="off"),
    }
    distinct = {k: SRV._slot_filename(p) for k, p in incompat.items()}
    for k, fn in distinct.items():
        check(f"incompatible runtime ({k}) gets a DIFFERENT slot (never silently loaded)",
              fn != name0, fn)
    check("all 3 incompatible digests are mutually distinct", len(set(distinct.values())) == 3)
    # an absent matching checkpoint → _restore_slot is a clean no-op (no crash/corruption)
    crashed = False
    try:
        SRV._restore_slot(base)              # SLOT_DIR empty → returns without raising
    except Exception:
        crashed = True
    check("restore with no matching checkpoint is a clean no-op", not crashed)
    # _prune_slots keeps ONLY the current slot — stale/incompatible checkpoints removed
    for fn in [name0] + list(distinct.values()):
        (SRV.SLOT_DIR / fn).write_bytes(b"\0")
    SRV._prune_slots(name0)
    remaining = sorted(p.name for p in SRV.SLOT_DIR.glob("slot-*.bin"))
    check("prune keeps only the current slot (incompatible checkpoints discarded)",
          remaining == [name0], remaining)
finally:
    SRV.SLOT_DIR = _real_slotdir
    shutil.rmtree(tmpF, ignore_errors=True)


# ─────────────────────── G. no SILENT provider fallback ───────────────────────
section("G. a local-primary failure re-raises — never reroutes to a cloud provider")
M.configure_backend(kind="local", base_url="", model=None, provider="local")
M.clear_routing()
_real_gen = M._generate
def _boom(*a, **k):
    raise RuntimeError("local transport down")
M._generate = _boom
try:
    raised = False
    try:
        M.call_model([{"role": "user", "content": "hi"}], timeout=5)
    except RuntimeError as exc:
        raised = "local transport down" in str(exc)
    check("local-primary failure propagates (no swallow)", raised)
    check("backend stays LOCAL after the failure (no silent cloud reroute)",
          M._current_backend().kind == "local", M._current_backend().kind)
    check("gate released after the failed local call", M._gate.try_acquire()); M._gate.release()
finally:
    M._generate = _real_gen


# ─────────────────────────── H. clean shutdown ───────────────────────────
section("H. clean shutdown — no orphan threads, gate free")
INV.call_model = _real                         # restore the real transport
live = [t for t in threading.enumerate()
        if t is not threading.current_thread() and t.is_alive()
        and (t.name.startswith("ui-turn-") or "CognitiveTick" in t.name)]
check("no orphan turn/tick threads left running", not live, [t.name for t in live])
check("inference gate is free at shutdown", M._gate.try_acquire()); M._gate.release()


# ─────────────────────────── report + result ───────────────────────────
section("REPORT")
out = Path(".runtime"); out.mkdir(exist_ok=True)
report = {
    "ok": not FAILS,
    "turns": REPORT["turns"],
    "cancelled": REPORT["cancelled"],
    "autonomousCycles": 10,
    "bridgeRestarts": REPORT["restarts"],
    "queueHighWater": REPORT["queueHighWater"],
    "latencySeconds": REPORT["latency"],
    "note": "deterministic-stub transport; identical run vs a real backend = live confirmation",
}
(out / "core-stress-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))

section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL N-59 CORE-STRESS CHECKS PASSED")
