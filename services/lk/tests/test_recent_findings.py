"""ContextStore.recent_findings correctness (T2).

The §9 proactive dedup guard reads recent_findings() to avoid re-surfacing a
finding it just produced. This locks the parser contract: finding-only filtering,
the "[PROACTIVE FINDING] {headline}\\n{insight}" split, oldest→newest order,
last-N windowing, and a headline-only finding yielding an empty insight. Reads the
raw layer directly — no model call, no lock.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "services")
from lk.ctx import ContextStore

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

tmp = Path(tempfile.mkdtemp())
ctx = ContextStore(mem_dir=tmp / "m", compact_fn=None)

def add_finding(headline, insight):
    ctx.append("2026-06-17T00:00:00", "finding", headline,
               f"[PROACTIVE FINDING] {headline}\n{insight}")


section("A. finding-only filtering + headline/insight split")
ctx.append("t", "spool", "c", "a plain user-turn detail")     # non-finding noise
add_finding("Headline A", "insight a")
ctx.append("t", "spool", "c", "another non-finding event")
add_finding("Headline B", "insight b")

found = ctx.recent_findings()
check("only findings returned (noise ignored)", len(found) == 2, [d["headline"] for d in found])
check("headline + insight parsed", found[0] == {"headline": "Headline A", "insight": "insight a"}, found[0])
check("order is oldest→newest", found[1]["headline"] == "Headline B", found)


section("B. last-N windowing")
for n in range(5):
    add_finding(f"H{n}", f"i{n}")
# total findings now: A, B, H0..H4  → 7
heads3 = [d["headline"] for d in ctx.recent_findings(limit=3)]
check("limit windows to the last N", heads3 == ["H2", "H3", "H4"], heads3)
check("default limit returns up to 8 most-recent", len(ctx.recent_findings()) == 7,
      len(ctx.recent_findings()))


section("C. headline-only finding → empty insight")
ctx2 = ContextStore(mem_dir=tmp / "m2", compact_fn=None)
ctx2.append("t", "finding", "c", "[PROACTIVE FINDING] lonely headline")
g = ctx2.recent_findings()
check("no newline ⇒ insight is empty", g == [{"headline": "lonely headline", "insight": ""}], g)


print()
if FAILS:
    print(f"  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("  ALL RECENT-FINDINGS CHECKS PASSED")
