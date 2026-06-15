"""Extraction-layer tests (WS-P/B1) — perception → clean memory.

Proves the keystone contract with the model stubbed (offline, no server):
  • high info-gain slice → exactly one extract call + a CLEAN stored entry;
  • low info-gain (near-duplicate) → no call (the droppable model is not spent);
  • model "down" (returns None) → the RAW slice is still logged (degraded path);
  • the store distils only sensor kinds (vision/audio), never turns;
  • LK_EXTRACT=0 disables it (config parity);
  • results buffer for the tick and drain() empties it.
"""
import sys, tempfile, shutil, os
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk.ctx import ContextStore, Extractor, NoteStore
from lk.ctx import gate as G

def _ts(): return datetime.now(timezone.utc).isoformat()

# A stub kernel call: counts invocations, returns a clean distillation.
def make_fn():
    n = {"calls": 0}
    def fn(slice_text, kind):
        n["calls"] += 1
        return {"clean": f"clean::{slice_text[:20]}", "significance": 0.8, "tags": ["t1", "t2"]}
    return fn, n

# ───────────────────────── gate: info-gain ─────────────────────────
section("extract_gate (info-gain)")
check("novel slice passes", G.extract_gate("", "the quarterly revenue chart shows a dip") is True)
check("near-duplicate skipped",
      G.extract_gate("alpha beta gamma delta epsilon", "alpha beta gamma delta epsilon") is False)
check("too-few-words skipped", G.extract_gate("", "hi ok") is False)

# ───────────────────────── extractor: high-gain → one call + clean ─────────────────────────
section("extractor distils a high-gain slice")
os.environ.pop("LK_EXTRACT", None)  # default-on
fn, n = make_fn()
ex = Extractor(fn)
res = ex.extract("the build failed on step 3 with a linker error in libfoo", "vision")
check("returned a result", bool(res) and res.get("clean", "").startswith("clean::"))
check("exactly one model call", n["calls"] == 1, f"calls={n['calls']}")
check("significance + tags surfaced", res["significance"] == 0.8 and res["tags"] == ["t1", "t2"])
check("buffered for the tick", len(ex.recent) == 1)
drained = ex.drain()
check("drain empties the buffer", len(drained) == 1 and len(ex.recent) == 0)

# ───────────────────────── extractor: low-gain → no call ─────────────────────────
section("near-duplicate slice makes no model call")
fn, n = make_fn()
ex = Extractor(fn)
slice_a = "the dashboard shows CPU at 80 percent and memory at 60 percent"
r1 = ex.extract(slice_a, "vision")
r2 = ex.extract(slice_a + " percent", "vision")   # ~identical → gated out
check("first slice extracted", bool(r1) and n["calls"] == 1)
check("near-duplicate skipped (no 2nd call)", r2 is None and n["calls"] == 1, f"calls={n['calls']}")

# ───────────────────────── degraded path: model down → raw kept ─────────────────────────
section("degraded path — model returns None")
def fn_down(slice_text, kind):
    return None
ex = Extractor(fn_down)
check("model-down yields None (caller keeps raw)", ex.extract("a brand new distinct observation here", "vision") is None)

# ───────────────────────── store integration: clean replaces raw, turns untouched ─────────────────────────
section("store append distils sensor kinds, never turns")
tmp = Path(tempfile.mkdtemp())
fn, n = make_fn()
ctx = ContextStore(mem_dir=tmp / "m", extractor=Extractor(fn))
ctx.append(ts=_ts(), kind="vision", compact="c", detailed="raw OCR garble about a flight booking to tokyo")
shown = ctx.show_layer("l1")
check("sensor slice stored as the CLEAN entry", "clean::" in shown, f"shown={shown[:80]!r}")
check("store made one extract call", n["calls"] == 1)
# a turn must NOT be extracted (kind='turn' is the response path, already clean)
calls_before = n["calls"]
ctx.append(ts=_ts(), kind="turn", compact="c", detailed="USER asked X / ASSISTANT answered Y verbatim")
shown2 = ctx.show_layer("l1")
check("turn stored verbatim (not extracted)", "ASSISTANT answered Y verbatim" in shown2)
check("no extract call for a turn", n["calls"] == calls_before, f"calls={n['calls']}")
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── B1→M3 bridge: significance mints a note ─────────────────────────
section("significance gates atomic-note creation (B1→M3)")
tmp = Path(tempfile.mkdtemp())
ns = NoteStore(mem_dir=tmp)
def fn_hi(s, k): return {"clean": "a notable build failure", "significance": 0.9, "tags": ["ci"]}
def fn_lo(s, k): return {"clean": "ambient ui chrome", "significance": 0.1, "tags": []}
ex_hi = Extractor(fn_hi, note_store=ns)
r_hi = ex_hi.extract("the linker exploded on libfoo at step three", "vision")
check("high significance mints a note", r_hi.get("note_id") and ex_hi.notes_written == 1)
check("the note is in the store", ns.stats()["notes"] == 1)
ex_lo = Extractor(fn_lo, note_store=ns)
r_lo = ex_lo.extract("a totally different ambient frame of pixels", "vision")
check("low significance mints NO note", "note_id" not in r_lo and ex_lo.notes_written == 0)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── disabled via LK_EXTRACT=0 ─────────────────────────
section("LK_EXTRACT=0 disables extraction (config parity)")
tmp = Path(tempfile.mkdtemp())
os.environ["LK_EXTRACT"] = "0"
fn, n = make_fn()
ctx = ContextStore(mem_dir=tmp / "m", extractor=Extractor(fn))
ctx.append(ts=_ts(), kind="vision", compact="c", detailed="some raw distinct ocr text not distilled")
shown = ctx.show_layer("l1")
check("raw kept when disabled", "some raw distinct ocr text" in shown)
check("no model call when disabled", n["calls"] == 0, f"calls={n['calls']}")
os.environ.pop("LK_EXTRACT", None)
shutil.rmtree(tmp, ignore_errors=True)

# ───────────────────────── summary ─────────────────────────
section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL EXTRACTION CHECKS PASSED")
