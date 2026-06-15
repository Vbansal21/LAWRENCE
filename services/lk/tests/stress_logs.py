"""Logs stress harness — by LOGIC, not by model.

The turn log (logger.write_turn) is the audit trail: one JSON line per turn under
memory/logs/DATE.jsonl, read back by admin.py (journal tags, /log show/export).
A log is only useful if every line is parseable and nothing is lost or torn. We
probe the writer + reader contract:

  A. ATOMICITY     — many concurrent writers, zero torn/interleaved lines, none lost;
  B. SCHEMA SAFETY — non-serializable values (datetime/set/objects) never crash the
     write (default=str), and newline/quote/unicode in values stay ONE physical
     JSONL line that round-trips;
  C. READER DEFENCE— the reader (admin.day_tags) skips garbage lines, never crashes;
  D. PATH SAFETY   — log management (delete/trim) cannot escape the logs dir via a
     crafted date (norm_date strptime guard).
"""
import sys, os, json, threading, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone

import lk.logger as logger
import lk.admin as admin

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

tmp = Path(tempfile.mkdtemp(prefix="lk-logs-"))
logs_dir = tmp / "logs"
logger._LOG_DIR = logs_dir                 # redirect the writer at a temp dir
admin._MEM_DIR = tmp                        # redirect the reader/manager too
admin._LOGS_DIR = logs_dir
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
log_path = logs_dir / f"{today}.jsonl"


# ─────────────────────── A. concurrent write atomicity ───────────────────────
section("A. concurrent writers: every line valid JSON, none lost or interleaved")
N_THREADS, PER = 40, 25
def writer(tid):
    for i in range(PER):
        logger.write_turn({
            "ts": datetime.now(timezone.utc).isoformat(),
            "turn_id": f"t-{tid:03d}-{i:03d}",
            "user_text": "q" * 500,            # ~1KB line — within one write() in O_APPEND
            "answer": "a" * 400,
            "tags": ["x", "y"], "confidence": 0.5,
        })
ts = [threading.Thread(target=writer, args=(k,)) for k in range(N_THREADS)]
for t in ts: t.start()
for t in ts: t.join(timeout=30)
raw = log_path.read_text(encoding="utf-8").splitlines()
parsed, bad = [], 0
ids = set()
for l in raw:
    if not l.strip(): continue
    try:
        o = json.loads(l); parsed.append(o); ids.add(o.get("turn_id"))
    except Exception:
        bad += 1
check("line count == writes issued", len([l for l in raw if l.strip()]) == N_THREADS * PER,
      f"{len(raw)} lines for {N_THREADS*PER} writes")
check("every line is valid JSON (no torn/interleaved writes)", bad == 0, f"{bad} unparseable")
check("every distinct turn_id present (no lost writes)", len(ids) == N_THREADS * PER, f"{len(ids)} ids")


# ─────────────────────── B. schema safety ───────────────────────
section("B. non-serializable values + injection chars never break the JSONL")
class Weird:                                  # not JSON-serializable
    def __str__(self): return "weird-obj"
log_path.write_text("", encoding="utf-8")     # reset
logger.write_turn({
    "ts": datetime.now(timezone.utc),          # raw datetime (not JSON-native)
    "obj": Weird(),                            # arbitrary object
    "set": {1, 2, 3},                         # set (not JSON-native)
    "answer": 'line1\nline2 "quoted" \t tab\\slash\nline3',  # newlines/quotes/tabs
    "unicode": "héllo … 日本語 🚀",
})
after = log_path.read_text(encoding="utf-8").splitlines()
check("non-serializable entry produced exactly ONE physical line", len(after) == 1, f"{len(after)} lines")
ok_parse = True
try:
    obj = json.loads(after[0])
except Exception as e:
    ok_parse = False
    obj = {}
    check("the line round-trips as JSON", False, repr(e))
if ok_parse:
    check("embedded newlines stayed inside the string (not new lines)",
          obj.get("answer", "").count("\n") == 2, repr(obj.get("answer")))
    check("unicode preserved (ensure_ascii=False)", obj.get("unicode") == "héllo … 日本語 🚀")
    check("datetime/object/set coerced via default=str", isinstance(obj.get("obj"), str))


# ─────────────────────── C. reader defensiveness ───────────────────────
section("C. admin.day_tags survives a corrupt log (skips garbage, no crash)")
log_path.write_text(
    json.dumps({"tags": ["alpha", "beta"]}) + "\n"
    + "{ not json at all\n"
    + "\x00\x00 binary\n"
    + json.dumps({"tags": ["beta", "gamma"]}) + "\n",
    encoding="utf-8",
)
try:
    tags = admin.day_tags(today)
    check("day_tags returns the good tags, skips garbage", set(tags) == {"alpha", "beta", "gamma"}, str(tags))
except Exception as e:
    check("day_tags did not crash on corrupt log", False, repr(e))


# ─────────────────────── D. path-traversal safety of log management ───────────────────────
section("D. crafted date cannot escape the logs dir (norm_date guard)")
sentinel = tmp.parent / "lk-SHOULD-NOT-DELETE.txt"
sentinel.write_text("important", encoding="utf-8")
for evil in ["../../lk-SHOULD-NOT-DELETE", "../lk-SHOULD-NOT-DELETE.txt", "/etc/passwd", "2026-06-15/../../x"]:
    check(f"norm_date rejects {evil!r}", admin.norm_date(evil) is None)
removed = admin.delete_log("../../lk-SHOULD-NOT-DELETE")
check("delete_log with traversal removes nothing", removed == [], str(removed))
check("sentinel file outside the tree is untouched", sentinel.exists())

shutil.rmtree(tmp, ignore_errors=True)
sentinel.unlink(missing_ok=True)

section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL LOG STRESS CHECKS PASSED")
