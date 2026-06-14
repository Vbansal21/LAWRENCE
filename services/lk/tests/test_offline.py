"""Offline stress/regression harness for LAWRENCE — no model/server needed.
Exercises every pure-Python component + edge cases. Records all failures."""
import sys, tempfile, shutil, json, time, threading, os
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone, timedelta

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)

def section(t): print(f"\n=== {t} ===")

# ───────────────────────── gate ─────────────────────────
section("gate")
from lk.ctx import gate as G
from lk.ctx.gate import gate_config, vision_gate, audio_gate
check("vision skip below pixel-min", vision_gate(0.05, "", "abc def") is False)
check("vision pass on high (no text)", vision_gate(0.99, "same text", "same text") is True)
check("vision pass on novelty", vision_gate(0.3, "alpha beta gamma", "delta epsilon zeta") is True)
check("vision skip when not novel", vision_gate(0.3, "alpha beta gamma delta", "alpha beta gamma delta") is False)
check("audio skip short", audio_gate("hi there", []) is False)
check("audio pass long novel", audio_gate("the quick brown fox jumps over", []) is True)
check("audio dedup skip", audio_gate("the quick brown fox jumps", ["the quick brown fox jumps over lazy"]) is False)
# live mutation
gate_config.vision_high = 0.9
check("live vision-high mutation respected", vision_gate(0.6, "a b c", "a b c") is False)
gate_config.vision_high = 0.5  # restore

# ───────────────────────── distill ─────────────────────────
section("distill")
from lk.ctx import distill as D
c, d = D.vision("2026-06-07T12:00:00+00:00", 0.7, "some screen text here", "diff")
check("vision distill returns 2 strs", isinstance(c, str) and isinstance(d, str) and c and d)
check("vision compact tagged sig", "sig" in c)
c2, d2 = D.audio("2026-06-07T12:00:00+00:00", "hello world", -20.0)
check("audio distill ok", "hello world" in d2)
c3, d3 = D.turn("2026-06-07T12:00:00+00:00", "q?", "ans", "note")
check("turn distill has user+assist", "USER" in d3 and "ASSIST" in d3)

# ───────────────────────── store: budget + compaction cascade ─────────────────────────
section("store: dynamic budget + L1→L2→L3 cascade")
from lk.ctx.store import ContextStore, _BUDGET_BASE, _BUDGET_GROW, _BUDGET_MAX, _BUDGET_MIN

tmp = Path(tempfile.mkdtemp())
# stub compactor that always returns a summary
calls = {"l1": 0, "l2": 0}
def stub_compact(text, level):
    calls[level] += 1
    return f"SUMMARY[{level}] of {len(text)} chars"
ctx = ContextStore(mem_dir=tmp/"m", compact_fn=stub_compact)
ctx._min_compact_secs = 0  # disable cooldown for the test
b0 = ctx.working_budget()
ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="turn", compact="c", detailed="x"*100)
check("budget grows on append", ctx.working_budget() >= b0)
# Force L1 over 70% of budget to trigger compaction
big = "y" * 2000
for i in range(60):
    ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="vision", compact="c", detailed=big)
# compaction runs in a background thread; wait
for _ in range(50):
    if calls["l1"] > 0 and ctx._l2_size > 0: break
    time.sleep(0.1)
time.sleep(0.5)  # let the in-flight compaction settle
check("L1 compaction fired", calls["l1"] > 0, f"calls={calls}")
check("L2 entry written", ctx._l2_size > 0, f"l2_size={ctx._l2_size}")
# real invariant: compaction trims L1 well below the total appended (120K)
check("L1 trimmed after compact", ctx._l1_size < 60*2000, f"l1_size={ctx._l1_size}")
# Now force L2 over budget to cascade to L3
ctx.l2_budget = 200
for i in range(40):
    ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="vision", compact="c", detailed=big)
for _ in range(80):
    if ctx._l3_size > 0: break
    time.sleep(0.1)
check("L3 entry written (cascade)", ctx._l3_size > 0, f"l3_size={ctx._l3_size} calls={calls}")
# let the background compaction settle — reading mid-rewrite makes this flaky
for _ in range(50):
    if not ctx._compacting:
        break
    time.sleep(0.1)
# tail_for_model includes all layers
tail = ctx.tail_for_model()
check("tail has section headers", "[CURRENT CONTEXT]" in tail)
check("tail within budget", len(tail) <= ctx.working_budget() + 200)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── store: budget decay ─────────────────────────
section("store: budget decay when stale")
from lk.ctx import store as STORE
tmp = Path(tempfile.mkdtemp())
ctx = ContextStore(mem_dir=tmp/"m")
ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="turn", compact="c", detailed="z"*500)
fresh = ctx.working_budget()
# simulate staleness by rewinding last activity
ctx._last_act = time.monotonic() - (STORE._STALE_SECS + STORE._DECAY_SECS + 10)
stale = ctx.working_budget()
check("budget decays to floor when stale", stale <= STORE._BUDGET_MIN + 10, f"stale={stale}")
check("budget recovers on activity", (ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="turn", compact="c", detailed="z"*100) or ctx.working_budget() > stale))
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── store: layer ops + archive ─────────────────────────
section("store: layer ops, archive, clear")
tmp = Path(tempfile.mkdtemp())
ctx = ContextStore(mem_dir=tmp/"m")
ctx.append(ts="2026-06-07T12:00:00+00:00", kind="vision", compact="c", detailed="event one")
ctx.append(ts="2026-06-07T12:00:01+00:00", kind="audio", compact="c", detailed="event two")
check("show_layer l1 has content", "event one" in ctx.show_layer("l1"))
check("show_layer bad layer", "must be" in ctx.show_layer("zz"))
exp = ctx.export(tmp/"exp")
check("export wrote l1", any(p.name=="rolling-l1.jsonl" for p in exp))
check("clear_layer l1", ctx.clear_layer("l1") and ctx._l1_size == 0)
check("clear_layer bad returns False", ctx.clear_layer("zz") is False)
# archive copy-then-truncate
ctx.append(ts="2026-06-07T12:00:02+00:00", kind="turn", compact="c", detailed="to archive")
ctx._archive_l1()
archives = list((tmp/"m").glob("rolling-2026*.jsonl"))
check("archive file created", len(archives) >= 1, f"archives={archives}")
check("L1 truncated after archive", ctx._l1_size == 0)
ctx.clear_rolling()
check("clear_rolling zeroes all", ctx._l1_size==0 and ctx._l2_size==0 and ctx._l3_size==0)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── admin: journal parse/render + mgmt ─────────────────────────
section("admin: journal + logs")
from lk import admin
tmp = Path(tempfile.mkdtemp())
admin._MEM_DIR=tmp; admin._JOURNAL_DIR=tmp/"journal"; admin._LOGS_DIR=tmp/"logs"
# structured parse
p = admin.parse_journal_output("TITLE: T One\nSUMMARY: A summary line.\nHIGHLIGHTS:\n- one\n- two\nTOPICS: a, b, c\nOPEN: keep going")
check("parse title", p["title"]=="T One")
check("parse highlights 2", len(p["highlights"])==2)
check("parse topics 3", p["topics"]==["a","b","c"])
check("parse open", p["open"]=="keep going")
# prose fallback
pf = admin.parse_journal_output("Just prose. More prose.")
check("prose fallback summary", bool(pf["summary"]))
check("prose fallback title derived", pf["title"]=="Just prose")
# OPEN none → empty
pn = admin.parse_journal_output("TITLE: X\nSUMMARY: s\nOPEN: none")
check("open none stripped", pn["open"]=="")
# render + stack two entries, frontmatter merge
w1 = datetime(2026,6,7,8,0,tzinfo=timezone.utc)
w2 = datetime(2026,6,7,9,0,tzinfo=timezone.utc)
admin.append_journal_entry(p, tags=["x"], when=w1)
path = admin.append_journal_entry(pf, tags=["y"], when=w2)
txt = path.read_text()
check("mdx has frontmatter", txt.startswith("---"))
check("mdx entries=2", "entries: 2" in txt)
check("mdx has callout", "> [!SUMMARY]" in txt)
check("mdx has details", "<details>" in txt)
check("mdx two sections", txt.count("## ")==2)
check("journal list 1 file", len(admin.list_journals())==1)
check("journal show works", "T One" in admin.show_journal("2026-06-07"))
check("journal show missing", "no journal" in admin.show_journal("2020-01-01"))
expj = admin.export_journal(tmp/"je", "2026-06-07")
check("journal export", len(expj)==1)
check("journal delete", admin.delete_journal("2026-06-07") and len(admin.list_journals())==0)
# logs
(tmp/"context-2026-06-07.log").write_text("\n".join(f"l{i}" for i in range(20))+"\n")
(tmp/"logs").mkdir(exist_ok=True); (tmp/"logs"/"2026-06-07.jsonl").write_text('{"tags":["py","async"]}\n')
check("list_logs", len(admin.list_logs())==1)
check("show_log tail 5", admin.show_log("2026-06-07",5).count("\n")==4)
check("day_tags from turnlog", set(admin.day_tags("2026-06-07"))=={"py","async"})
check("trim_log keeps 3", admin.trim_log("2026-06-07",3)==3)
check("export_log both files", len(admin.export_log(tmp/"le","2026-06-07"))==2)
check("delete_log both", len(admin.delete_log("2026-06-07"))==2)
# norm_date
check("norm today", admin.norm_date("today")==datetime.now(timezone.utc).strftime("%Y-%m-%d"))
check("norm bad", admin.norm_date("notadate") is None)
check("norm explicit", admin.norm_date("2026-06-07")=="2026-06-07")
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── spool ─────────────────────────
section("spool: writer/reader + corrupt handling")
from lk.obs.spool import SpoolWriter, SpoolReader
tmp = Path(tempfile.mkdtemp())
w = SpoolWriter(tmp/"sp")
for i in range(5):
    w.append(ts=f"2026-06-07T12:00:0{i}+00:00", kind="vision", compact=f"c{i}", detailed=f"d{i}")
check("spool writer 5 files", len(list((tmp/"sp").glob("*.json")))==5)
check("no tmp leftovers", len(list((tmp/"sp").glob("*.tmp")))==0)
# corrupt file
(tmp/"sp"/"zzz-bad.json").write_text("{not json")
got=[]
ctx2 = ContextStore(mem_dir=tmp/"m2")
r = SpoolReader(tmp/"sp", ctx2, on_event=lambda k,c: got.append((k,c)), poll=0.1)
r.start()
for _ in range(40):
    if not list((tmp/"sp").glob("*.json")): break
    time.sleep(0.1)
r.stop(); time.sleep(0.2)
check("spool drained all (incl corrupt removed)", len(list((tmp/"sp").glob("*.json")))==0)
check("on_event fired 5 (corrupt skipped)", len(got)==5, f"got={len(got)}")
check("events ingested to store", ctx2._l1_size>0)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── profile ─────────────────────────
section("profile: detection + env overrides + safety")
from lk.profile import ModelProfile
tmp = Path(tempfile.mkdtemp())
(tmp/"model.gguf").write_bytes(b"x")
(tmp/"mmproj-model.gguf").write_bytes(b"x")
binp = tmp/"llama-server"; binp.write_bytes(b"x")
for k in ("LK_VISION","LK_AUDIO","LK_KV_TYPE","LK_FLASH_ATTN","LK_JINJA","LK_CTX_SIZE"):
    os.environ.pop(k, None)
pr = ModelProfile.detect(model=tmp/"model.gguf", bin_path=binp)
check("mmproj auto-detected", pr.mmproj is not None)
check("vision+audio from mmproj", pr.vision and pr.audio)
check("default ctx 64k", pr.ctx_size==65536, f"ctx={pr.ctx_size}")
check("default kv q4_0", pr.kv_type=="q4_0")
# text-only model (no mmproj) — own dir so no stray mmproj is globbed
solodir = tmp/"solo"; solodir.mkdir()
(solodir/"solo.gguf").write_bytes(b"x")
pr2 = ModelProfile.detect(model=solodir/"solo.gguf", bin_path=binp)
check("text-only no mmproj", pr2.mmproj is None and not pr2.vision and not pr2.audio)
# env override: force vision off, kv f16
os.environ["LK_VISION"]="0"; os.environ["LK_KV_TYPE"]="f16"
pr3 = ModelProfile.detect(model=tmp/"model.gguf", bin_path=binp)
check("env LK_VISION=0 forces off", pr3.vision is False)
check("env f16 → kv_type None", pr3.kv_type is None)
# safety: FA off + quantized kv → kv dropped
os.environ.pop("LK_VISION"); os.environ["LK_KV_TYPE"]="q4_0"; os.environ["LK_FLASH_ATTN"]="off"
pr4 = ModelProfile.detect(model=tmp/"model.gguf", bin_path=binp)
check("safety: FA off drops quant KV", pr4.kv_type is None and pr4.flash_attn=="off")
for k in ("LK_VISION","LK_AUDIO","LK_KV_TYPE","LK_FLASH_ATTN","LK_JINJA","LK_CTX_SIZE"):
    os.environ.pop(k, None)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── model JSON + fallback ─────────────────────────
section("model: JSON extraction, thinking strip, fallback salvage")
from lk.kernel.invoke import _extract_json, _fallback_response
from lk.model import _strip_thinking
check("extract last valid object", _extract_json('noise {"a":1} more {"b":2}')=={"b":2})
check("extract nested", _extract_json('{"x":{"y":2}}')=={"x":{"y":2}})
check("extract none on garbage", _extract_json("no json here") is None)
# regression: RESPONSE with nested controls must return the WHOLE object, not controls
_resp = '<|channel>thought hmm<|channel>answer {"answer_text":"hi","confidence":0.9,"controls":{"vision":"hi"}}'
_r = _extract_json(_resp)
check("extract full response w/ nested controls", _r is not None and _r.get("answer_text")=="hi" and _r.get("controls")=={"vision":"hi"}, f"got={_r}")
check("strip thinking channel", _strip_thinking("<|channel>thought stuff<|channel>answer hello")=="hello")
check("strip unclosed thought", _strip_thinking("<|channel>thought only thinking")=="")
check("strip <think>", _strip_thinking("<think>x</think>real")=="real")
fb = _fallback_response('{"answer_text":"partial ans')
check("fallback salvages answer_text", fb["answer_text"]=="partial ans", f"got={fb['answer_text']!r}")
fb2 = _fallback_response("plain text not json")
check("fallback plain text", fb2["answer_text"]=="plain text not json")

# ───────────────────────── retrieval formatting + ranker ─────────────────────────
section("retrieval: formatting + ranker")
from lk.retrieval.pipeline import CitedResult, format_snippets, format_for_model, format_citations
from lk.retrieval.ranker import rank
rs = [CitedResult(1,"http://a","Title A","x"*400), CitedResult(2,"http://b","Title B","y"*400)]
check("format_snippets previews", "previews" in format_snippets(rs) and "…" in format_snippets(rs))
check("format_for_model full", "Title A" in format_for_model(rs) and "URL" in format_for_model(rs))
check("format_citations list", "[1]" in format_citations(rs))
check("empty formatting safe", format_snippets([])=="" and format_citations([])=="")
ranked = rank(["python asyncio"], ["python asyncio event loop tutorial", "totally unrelated cooking recipe"])
check("ranker returns ordered indices", ranked[0][0]==0, f"ranked={ranked}")

# ───────────────────────── invoke message builder ─────────────────────────
section("invoke: message builder")
from lk.kernel.invoke import _build_messages
m = _build_messages("SYS", "body", [], [])
check("text-only msg shape", m[0]["role"]=="system" and isinstance(m[1]["content"], str))
tmp = Path(tempfile.mkdtemp()); img=tmp/"i.png"; img.write_bytes(b"\x89PNG")
m2 = _build_messages("SYS", "body", [img], [])
check("media msg is block list", isinstance(m2[1]["content"], list))
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── region tracker ─────────────────────────
section("regions: tracker IoU/EMA/TTL/dedup")
from lk.obs.regions import RegionTracker, WinRect, _iou, _dedup_overlapping, screen_windows
check("iou identical", _iou((0,0,10,10),(0,0,10,10))==1.0)
check("iou disjoint", _iou((0,0,10,10),(20,20,30,30))==0.0)
tk = RegionTracker(ema=0.5, iou_match=0.3, ttl=2)
a = tk.update([WinRect("Ed",0,0,100,100), WinRect("Tm",200,0,300,100)])
check("two regions tracked", len(a)==2)
ed_id = [r.rid for r in a if r.title=="Ed"][0]
b = tk.update([WinRect("Ed",10,0,110,100), WinRect("Tm",200,0,300,100)])
ed = [r for r in b if r.title=="Ed"][0]
check("stable id across nudge", ed.rid==ed_id)
check("ema smooths box (0<l<10)", 0 < ed.box[0] < 10, f"l={ed.box[0]}")
tk.update([WinRect("Ed",10,0,110,100)]); tk.update([WinRect("Ed",10,0,110,100)])
tk.update([WinRect("Ed",10,0,110,100)])
check("ttl evicts gone region", "Tm" not in {r.title for r in tk.active()})
# dedup: occluded duplicate maximized windows collapse to the topmost
dd = _dedup_overlapping([WinRect("Top",0,0,1000,1000), WinRect("Behind",0,0,1000,1000),
                         WinRect("Side",1000,0,1200,400)])
check("dedup drops occluded", len(dd)==2 and dd[0].title=="Top", f"dd={[w.title for w in dd]}")

# ───────────────────────── proactive surfacing ─────────────────────────
section("proactive surfacing (run_proactive)")
import lk.model as MPro
from lk.ctx.store import ContextStore as _PCtx
from lk.kernel.invoke import run_proactive, AnswerTextStreamer
from lk.retrieval.pipeline import CitedResult

_pseq = [
    '{"needs_retrieval": true, "queries": ["adjacent info"]}',
    '{"surface": true, "headline": "Heads-up", "insight": "Useful fact [1]"}',
]
def _proactive_post(payload, timeout):
    return {"choices": [{"message": {"content": _pseq.pop(0)}}]}
MPro._post = _proactive_post
MPro.configure_backend(kind="local")

class _FakeRetrieval:
    def retrieve(self, queries, top_k=None):
        return [CitedResult(citation_num=1, url="https://x.test/a", title="A", text="chunk text")]

_ptmp = Path(tempfile.mkdtemp())
_pctx = _PCtx(mem_dir=_ptmp)
_pctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="vision",
             compact="[VISION] editing", detailed="[VISION] user editing report.md")
_found = []
run_proactive(_pctx, _FakeRetrieval(), present_fn=_found.append)
check("finding presented", len(_found) == 1 and _found[0]["headline"] == "Heads-up",
      f"found={_found}")
check("finding has citations", bool(_found) and _found[0]["citations"][0]["url"] == "https://x.test/a")
check("finding recorded to context", "[PROACTIVE FINDING]" in _pctx.tail_for_model())
# droppable: gate held → proactive skips silently, nothing surfaced
_pseq2 = ['{"needs_retrieval": true, "queries": ["x"]}']
MPro._post = lambda payload, timeout: {"choices": [{"message": {"content": _pseq2.pop(0)}}]}
MPro._gate.acquire(MPro.PRI_TURN)
_found2 = []
run_proactive(_pctx, _FakeRetrieval(), present_fn=_found2.append)
MPro._gate.release()
check("proactive skipped while slot busy", _found2 == [])
shutil.rmtree(_ptmp, ignore_errors=True)

# ───────────────────────── answer streamer ─────────────────────────
section("AnswerTextStreamer (live answer extraction from JSON deltas)")
_out = []
_st = AnswerTextStreamer(_out.append)
_env = '{"answer_text": "Hi \\"there\\"\\nline2 \\u00e9!", "note_compact": "x"}'
for _i in range(0, len(_env), 3):
    _st.feed(_env[_i:_i + 3])
check("streams unescaped answer", "".join(_out) == 'Hi "there"\nline2 é!', repr("".join(_out)))
check("stops at closing quote", _st.emitted and '"note_compact"' not in "".join(_out))
_out2, _st2 = [], AnswerTextStreamer(lambda t: _out2.append(t))
for _c in "plain text, not json":
    _st2.feed(_c)
check("non-JSON emits nothing", _out2 == [] and not _st2.emitted)

# ───────────────────────── document ingestion ─────────────────────────
section("document ingestion (knowledge base)")
from lk.retrieval.db import SemanticDB as _IngestDB
from lk.retrieval.ingest import ingest as _ingest

_itmp = Path(tempfile.mkdtemp())
_doc = _itmp / "notes.md"
_doc.write_text(
    "# Project Phoenix\n\n"
    "The launch window for Project Phoenix opens on March 3rd. "
    "The propulsion subsystem uses a methalox engine with regenerative cooling. "
    "Telemetry downlink runs at 2.4 GHz with a 6 dB link margin requirement.\n",
    encoding="utf-8",
)
_idb = _IngestDB(path=_itmp / "test.db")
_n, _title = _ingest(str(_doc), db=_idb)
check("ingest inserts chunks", _n >= 1, f"n={_n}")
check("ingest title is filename", _title == "notes.md")
_hits = _idb.search("methalox propulsion")
check("ingested text is searchable", any("methalox" in h.text for h in _hits))
check("ingested url is file://", bool(_hits) and _hits[0].url.startswith("file://"))
try:
    _ingest(str(_itmp / "missing.pdf"), db=_idb)
    check("missing file raises", False)
except FileNotFoundError:
    check("missing file raises", True)
shutil.rmtree(_itmp, ignore_errors=True)

# ───────────────────────── web search provider chain ─────────────────────────
section("web search provider chain (bot-block fallthrough)")
import lk.retrieval.web as W

_saved_providers = W._PROVIDERS
_saved_cooldowns = dict(W._cooldown_until)
def _blocked(query, n):  raise W._BotBlocked("HTTP 202 bot-block page")
def _erroring(query, n): raise RuntimeError("connection refused")
def _working(query, n):  return [{"url": "https://ok.test/a", "title": "A"}]
W._PROVIDERS = [("p_blocked", _blocked), ("p_error", _erroring), ("p_ok", _working)]
W._cooldown_until.clear()
W._stats.clear()

res = W.ddg_search("anything", 3)
check("chain falls through to working provider", res and res[0]["url"] == "https://ok.test/a")
st = W.search_stats()
check("blocked provider counted", st["providers"].get("p_blocked", {}).get("blocked") == 1, st)
check("erroring provider counted", st["providers"].get("p_error", {}).get("fail") == 1)
check("blocked provider cooling down", "p_blocked" in st["cooling_down"])
res2 = W.ddg_search("again", 3)   # blocked provider must be skipped instantly now
check("cooldown skips blocked provider", res2 and W._stats["p_blocked"]["blocked"] == 1)
# all providers down → empty result but last_error recorded, no exception
W._PROVIDERS = [("p_error", _erroring)]
W._stats.clear()
check("all-down returns [] with error noted",
      W.ddg_search("x", 3) == [] and "p_error" in W.search_stats()["last_error"])
W._PROVIDERS = _saved_providers
W._cooldown_until.clear()
W._cooldown_until.update(_saved_cooldowns)

# ───────────────────────── model backend ─────────────────────────
section("model backend: local vs api request construction")
import lk.model as MB
_cap = {}
def _fake_post(payload, timeout):
    _cap.update(payload=payload, timeout=timeout, endpoint=MB._endpoint()); return {"choices":[{"message":{"content":"x"}}]}
MB._post = _fake_post
MB.configure_backend(kind="local")
MB.call_model([{"role":"user","content":"hi"}], max_tokens=5, timeout=300)
check("local endpoint", _cap["endpoint"].endswith(":8190/v1/chat/completions"))
check("local cache_prompt on", _cap["payload"].get("cache_prompt") is True)
check("local no model field", "model" not in _cap["payload"])
check("local blocks (timeout None)", _cap["timeout"] is None)
MB.configure_backend(kind="api", base_url="https://x.test/v1/", api_key="k", model="m1")
MB.call_model([{"role":"user","content":"hi"}], max_tokens=5, timeout=99)
check("api endpoint", _cap["endpoint"]=="https://x.test/v1/chat/completions")
check("api model field", _cap["payload"].get("model")=="m1")
check("api no cache_prompt", "cache_prompt" not in _cap["payload"])
check("api timeout set", _cap["timeout"]==99)
check("describe api", "x.test" in MB.describe_backend())
MB.configure_backend(kind="local")  # restore

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL OFFLINE CHECKS PASSED")
