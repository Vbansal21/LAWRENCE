"""Edge & failure-mode tests. Simulates server-down by pointing the model client
at a closed port, plus empty/huge/malformed inputs and fallback paths."""
import sys, tempfile, shutil, time, json
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone, timedelta

FAILS=[]
def check(n,c,extra=""):
    print(f"  {'PASS' if c else 'FAIL'}  {n}"+(f"  :: {extra}" if extra and not c else "")); 
    if not c: FAILS.append(n)
def section(t): print(f"\n=== {t} ===")

# ---- server-down (degraded) ----
section("server down → degraded handling")
from lk import server as SRV
SRV.PORT = 59999  # nothing listening
check("health_check false when down", SRV.health_check(timeout=1.0) is False)
from lk.model import call_model
try:
    call_model([{"role":"user","content":"hi"}], max_tokens=4, timeout=2)
    check("call_model raises when down", False)
except Exception:
    check("call_model raises when down", True)

from lk.ctx import ContextStore
from lk.retrieval import SemanticDB, RetrievalPipeline
from lk.kernel import run_turn, run_proactive, write_journal_entry, run_compaction, TurnConfig
from lk.ui import UIConnector
tmp = Path(tempfile.mkdtemp())
ctx = ContextStore(mem_dir=tmp/"m")
ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="turn", compact="c", detailed="some context")
db = SemanticDB(tmp/"r.db"); pipe = RetrievalPipeline(db); ui = UIConnector()
cfg = TurnConfig(no_retrieval=True, timeout=2)
try:
    ans, ctrl = run_turn("hello?", ctx=ctx, retrieval=pipe, cfg=cfg, images=[], audios=[], ui=ui)
    check("run_turn degraded returns (str,dict)", isinstance(ans,str) and isinstance(ctrl,dict))
except Exception as e:
    check("run_turn degraded returns (str,dict)", False, repr(e))
# proactive + journal must not raise when down
try:
    run_proactive(ctx, pipe, present_fn=lambda f: None); check("run_proactive silent when down", True)
except Exception as e:
    check("run_proactive silent when down", False, repr(e))
check("journal returns '' when down", write_journal_entry(ctx)=="")
check("compaction returns '' when down", run_compaction("some text","l1")=="")
db.close(); shutil.rmtree(tmp, ignore_errors=True)

# ---- empty context ----
section("empty context")
tmp = Path(tempfile.mkdtemp())
ctx = ContextStore(mem_dir=tmp/"m")
check("empty tail sentinel", ctx.tail_for_model()=="(no context yet)")
check("journal empty ctx ''", write_journal_entry(ctx)=="")
check("show_layer empty", "empty" in ctx.show_layer("l1").lower())
shutil.rmtree(tmp, ignore_errors=True)

# ---- compact_fn=None → naive trim, never unbounded ----
section("no compactor → naive trim fallback")
tmp = Path(tempfile.mkdtemp())
ctx = ContextStore(mem_dir=tmp/"m")  # no compact_fn
for i in range(200):
    ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="vision", compact="c", detailed="q"*1500)
time.sleep(0.3)
from lk.ctx import store as STORE
check("naive-trimmed L1 bounded", ctx._l1_size <= STORE._BUDGET_MAX, f"l1={ctx._l1_size}")
check("tail still valid after naive trim", "[CURRENT CONTEXT]" in ctx.tail_for_model())
shutil.rmtree(tmp, ignore_errors=True)

# ---- idle archive on startup ----
section("startup archives stale L1")
tmp = Path(tempfile.mkdtemp()); mem = tmp/"m"; mem.mkdir(parents=True)
old_ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
(mem/"rolling-l1.jsonl").write_text(json.dumps({"ts":old_ts,"kind":"turn","detailed":"old session"})+"\n")
ctx = ContextStore(mem_dir=mem, idle_secs=2*3600)
check("stale L1 archived on startup", ctx._l1_size==0)
check("archive file exists", len(list(mem.glob("rolling-2*.jsonl")))>=1)
shutil.rmtree(tmp, ignore_errors=True)

# ---- admin malformed/edge ----
section("admin edge cases")
from lk import admin
tmp = Path(tempfile.mkdtemp())
admin._MEM_DIR=tmp; admin._JOURNAL_DIR=tmp/"j"; admin._LOGS_DIR=tmp/"l"
check("trim missing log → -1", admin.trim_log("2020-01-01", 5)==-1)
check("delete missing journal → False", admin.delete_journal("2020-01-01") is False)
check("export missing journal → []", admin.export_journal(tmp/"x","2020-01-01")==[])
check("show_log missing", "no event log" in admin.show_log("2020-01-01"))
check("list empty journals", admin.list_journals()==[])
check("day_tags missing → []", admin.day_tags("2020-01-01")==[])
# empty model output → parse still yields a title
pe = admin.parse_journal_output("")
check("parse empty → has title", pe["title"]=="Session" or pe["title"])
shutil.rmtree(tmp, ignore_errors=True)

# ---- spool edge ----
section("spool edge cases")
from lk.obs.spool import SpoolReader, SpoolWriter
tmp = Path(tempfile.mkdtemp())
ctxs = ContextStore(mem_dir=tmp/"m")
r = SpoolReader(tmp/"nonexistent_spool", ctxs, poll=0.1)  # dir created lazily
r.start(); time.sleep(0.3); r.stop()
check("spool reader on empty/new dir no crash", True)
shutil.rmtree(tmp, ignore_errors=True)

# ---- fallback salvage variants ----
section("fallback salvage")
from lk.kernel.invoke import _fallback_response
check("escaped quotes", _fallback_response(r'{"answer_text":"say \"hi\" now')["answer_text"]=='say "hi" now')
check("newline escape", "line1\nline2" in _fallback_response(r'{"answer_text":"line1\nline2')["answer_text"])
check("no answer_text key", isinstance(_fallback_response('{"other":1}')["answer_text"], str))

section("RESULT")
print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}" if FAILS else "\n  ALL EDGE CHECKS PASSED")
sys.exit(1 if FAILS else 0)
