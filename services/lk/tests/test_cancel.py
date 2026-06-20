"""Job cancellation + hard timeouts (NEXT_WORK_CHECKLIST §3).

Three layers, no real model/server:
  A) model transport — a stub llama-server proves cooperative streaming cancel,
     the streaming wall-clock deadline, and the NEW non-streaming wall-clock
     deadline (a stalled gen errors at ~the deadline, not 3x via retries).
  B) run_turn semantics — a cancelled turn raises TurnCancelled and writes
     NOTHING to rolling memory; a later turn still succeeds.
  C) bridge job lifecycle — queued/running cancellation, terminal idempotency,
     and that _job_view is JSON-safe (drops the private cancel Event).
"""
import sys, threading, time, json, http.server
sys.path.insert(0, "services")
from pathlib import Path
import tempfile, shutil
from datetime import datetime, timezone

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

import lk.server as SRV
import lk.model as M

# ───────────────────────── stub local llama-server ─────────────────────────
STALL = [0.0]   # non-streaming server delay before it answers (seconds)

class _Stub(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    def log_message(self, *a): pass
    def do_GET(self):                                  # /health
        self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for i in range(200):                       # ~10s of slow tokens
                try:
                    self.wfile.write(b"data: " + json.dumps(
                        {"choices": [{"delta": {"content": f"tok{i} "}}]}).encode() + b"\n\n")
                    self.wfile.flush()
                except Exception:
                    return                              # client hung up (cancel/deadline)
                time.sleep(0.05)
            try: self.wfile.write(b"data: [DONE]\n\n")
            except Exception: pass
        else:
            time.sleep(STALL[0])                        # idle while "generating"
            payload = {"choices": [{"message": {"content": "ok"}}]}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

_srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
SRV.PORT = _srv.server_address[1]
threading.Thread(target=_srv.serve_forever, daemon=True).start()
MSGS = [{"role": "user", "content": "hi"}]

# ───────────────────────── A. model transport ─────────────────────────
section("model: streaming cooperative cancel")
collected = []
def ss_after3(): return len(collected) >= 3
cancelled = False
try:
    M.call_model(MSGS, stream_fn=collected.append, should_stop=ss_after3, timeout=30)
except M.TurnCancelled:
    cancelled = True
check("streaming cancel raises TurnCancelled", cancelled)
check("streaming cancel stops early (not full gen)", 3 <= len(collected) < 50, f"got {len(collected)}")
check("gate released after cancel", M._gate.try_acquire(), "gate still held")
M._gate.release()

section("model: cancel before first token")
got = []
pre = False
try:
    M.call_model(MSGS, stream_fn=got.append, should_stop=lambda: True, timeout=30)
except M.TurnCancelled:
    pre = True
check("pre-token cancel raises TurnCancelled", pre)
check("pre-token cancel emits zero tokens", len(got) == 0, f"got {len(got)}")

section("model: streaming wall-clock deadline")
err = ""
try:
    M.call_model(MSGS, stream_fn=lambda p: None, should_stop=None, timeout=1)
except M.TurnCancelled:
    err = "cancelled"
except RuntimeError as e:
    err = str(e)
check("streaming gen hits wall-clock timeout", "wall-clock" in err, err)

section("model: NON-streaming wall-clock deadline (the new bit)")
STALL[0] = 4.0
t0 = time.monotonic()
nerr = ""
try:
    M.call_model(MSGS, timeout=1)        # non-streaming, no schema → _post_with_retry
except RuntimeError as e:
    nerr = str(e)
elapsed = time.monotonic() - t0
check("non-streaming stall raises timeout error", "timeout after" in nerr, nerr)
check("errors at ~deadline, not 3x via retry", elapsed < 2.5, f"elapsed={elapsed:.2f}s")

section("model: healthy after a timeout (later call succeeds)")
STALL[0] = 0.0
ok = M.call_model(MSGS, timeout=5)
check("later non-streaming call succeeds", ok.get("text") == "ok", ok)
check("gate free after timeout+success", M._gate.try_acquire()); M._gate.release()

# ───────────────────────── B. run_turn semantics ─────────────────────────
section("run_turn: cancel writes nothing, later turn succeeds")
from lk.ctx import ContextStore
from lk.retrieval import SemanticDB, RetrievalPipeline
from lk.kernel import run_turn, TurnConfig
from lk.ui import UIConnector

tmp = Path(tempfile.mkdtemp())
ctx = ContextStore(mem_dir=tmp / "m")
ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="turn", compact="seed", detailed="seed ctx")
db = SemanticDB(tmp / "r.db"); pipe = RetrievalPipeline(db); ui = UIConnector()
cfg = TurnConfig(no_retrieval=True, skip_analysis=True, timeout=30)
size_before = ctx._l1_size

# Stub call_model inside the kernel so the turn streams without a real model.
import lk.kernel.invoke as INV
def fake_call(messages, *, stream_fn=None, should_stop=None, **kw):
    if stream_fn:
        for i in range(200):
            if should_stop and should_stop():
                raise M.TurnCancelled()
            stream_fn(f"x{i}")
            time.sleep(0.005)
    return {"text": json.dumps({"answer_text": "final answer", "confidence": 0.9})}
_real_call = INV.call_model
INV.call_model = fake_call
try:
    raised = False
    try:
        run_turn("question?", ctx=ctx, retrieval=pipe, cfg=cfg, images=[], audios=[],
                 ui=ui, stream_fn=lambda p: None, should_stop=lambda: True)   # pre-token cancel
    except M.TurnCancelled:
        raised = True
    check("run_turn cancel raises TurnCancelled", raised)
    check("cancelled turn writes nothing to rolling memory", ctx._l1_size == size_before,
          f"{size_before}->{ctx._l1_size}")

    # cancel mid-stream (after generation has been running a moment) — still no
    # memory write. Time-based probe: run_turn wraps stream_fn in AnswerTextStreamer,
    # so the cancel signal must be independent of the answer collector.
    t_mid = time.monotonic()
    def ss_mid(): return (time.monotonic() - t_mid) > 0.05
    raised2 = False
    try:
        run_turn("q2?", ctx=ctx, retrieval=pipe, cfg=cfg, images=[], audios=[],
                 ui=ui, stream_fn=lambda p: None, should_stop=ss_mid)
    except M.TurnCancelled:
        raised2 = True
    check("mid-stream cancel raises TurnCancelled", raised2)
    check("mid-stream cancel writes nothing", ctx._l1_size == size_before)

    # a later, uncancelled turn completes and DOES write
    ans, ctrl = run_turn("q3?", ctx=ctx, retrieval=pipe, cfg=cfg, images=[], audios=[],
                         ui=ui, stream_fn=lambda p: None, should_stop=lambda: False)
    check("later turn returns the answer", "final answer" in ans, ans)
    check("later turn writes to rolling memory", ctx._l1_size > size_before)

    # N-22: a turn-wide deadline aborts the whole pipeline via TurnCancelled even
    # when the caller's should_stop never fires. The deadline (already past) trips
    # at the first stage boundary; nothing is written for the aborted turn.
    size_pre_dl = ctx._l1_size
    cfg_dl = TurnConfig(no_retrieval=True, skip_analysis=True, timeout=30,
                        turn_deadline_s=0.0001)
    time.sleep(0.001)
    dl_raised = False
    try:
        run_turn("q4-deadline?", ctx=ctx, retrieval=pipe, cfg=cfg_dl, images=[],
                 audios=[], ui=ui, stream_fn=lambda p: None, should_stop=lambda: False)
    except M.TurnCancelled:
        dl_raised = True
    check("N-22 turn-wide deadline aborts via TurnCancelled", dl_raised)
    check("N-22 deadline-aborted turn writes nothing", ctx._l1_size == size_pre_dl)

    # default (turn_deadline_s=None) is unchanged: a turn still completes
    ans5, _ = run_turn("q5?", ctx=ctx, retrieval=pipe, cfg=cfg, images=[], audios=[],
                       ui=ui, stream_fn=lambda p: None, should_stop=lambda: False)
    check("N-22 default (no deadline) still completes", "final answer" in ans5)
finally:
    INV.call_model = _real_call
    db.close(); shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── C. bridge job lifecycle ─────────────────────────
section("bridge: job cancellation lifecycle")
import importlib.util
_bridge_path = Path("apps/desktop/scripts/ui_bridge.py").resolve()
spec = importlib.util.spec_from_file_location("ui_bridge", _bridge_path)
UB = importlib.util.module_from_spec(spec); spec.loader.exec_module(UB)

# Bare instance — skip __init__ (writer lock / SSE server / observers).
b = UB.DesktopBridge.__new__(UB.DesktopBridge)
b.jobs = {}
b.job_lock = threading.Lock()
b._turn_count_lock = threading.Lock()
b._turns_in_flight = 0
class _NullUI:
    def push_status(self, *a, **k): pass
    def push_context_event(self, *a, **k): pass
b.ui = _NullUI()

def _seed_job(state="queued"):
    jid = f"turn-{state}-{time.time_ns()}"
    with b.job_lock:
        b.jobs[jid] = {"id": jid, "state": state, "createdAt": datetime.now(timezone.utc).isoformat(),
                       "_cancel": threading.Event()}
    return jid

# (1) queued job cancelled before it runs → runner never calls turn
jid = _seed_job("queued")
view = b.cancel_job(jid)
check("cancel queued → state cancelled", view["state"] == "cancelled")
check("_job_view drops private _cancel key", "_cancel" not in view)
check("_job_view is JSON-serializable", isinstance(json.dumps(view), str))
turn_called = [0]
b.turn = lambda req: turn_called.__setitem__(0, turn_called[0] + 1) or {"answer": "x"}
b._run_turn_job(jid, {"turn": {"text": "hi"}})
check("queued-cancelled runner never starts turn", turn_called[0] == 0)
check("queued-cancelled stays cancelled", b.jobs[jid]["state"] == "cancelled")

# (2) running job cancelled while streaming → ends cancelled, no fake answer
jid = _seed_job("queued")
def turn_stream(req):
    ss = req.get("should_stop")
    for _ in range(400):
        if ss and ss():
            raise UB._model.TurnCancelled()
        time.sleep(0.005)
    return {"answer": "done"}
b.turn = turn_stream
th = threading.Thread(target=b._run_turn_job, args=(jid, {"turn": {"text": "hi"}}))
th.start()
time.sleep(0.1)
check("running job is in 'running' state", b.jobs[jid]["state"] == "running")
b.cancel_job(jid)
th.join(timeout=5)
check("running cancel → state cancelled", b.jobs[jid]["state"] == "cancelled")
check("cancelled job has no result answer", "result" not in b.jobs[jid])
check("in-flight counter balanced after cancel", b._turns_in_flight == 0)

# (3) a later turn still succeeds after a cancellation
jid2 = _seed_job("queued")
b.turn = lambda req: {"answer": "later ok"}
b._run_turn_job(jid2, {"turn": {"text": "again"}})
check("later job completes (state done)", b.jobs[jid2]["state"] == "done")
check("later job carries its result", b.jobs[jid2]["result"]["answer"] == "later ok")

# (4) cancelling a terminal job is an idempotent no-op
view = b.cancel_job(jid2)
check("cancel terminal job is no-op", view["state"] == "done")

# (5) unknown job → 404 BridgeError
try:
    b.cancel_job("nope")
    check("cancel unknown job raises 404", False)
except UB.BridgeError as e:
    check("cancel unknown job raises 404", e.status == 404)

# ───────────────────────── summary ─────────────────────────
print()
if FAILS:
    print(f"FAIL ({len(FAILS)}): " + ", ".join(FAILS)); sys.exit(1)
print("test_cancel: ALL PASS")
