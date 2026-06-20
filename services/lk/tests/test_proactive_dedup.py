"""§9 — proactive dedup + stale guard.

The proactive loop must surface a useful finding *once* and must not surface a
conclusion computed against a context the user has already moved past. These are
deterministic, model-free tests: `lk.model._post` is stubbed so each
`run_proactive` consumes a scripted PROACTIVE pass + PROACTIVE_BRIEF pass.
"""
import sys, tempfile, shutil
sys.path.insert(0, "services")
from pathlib import Path
from datetime import datetime, timezone

FAILS = []
def check(name, cond, extra=""):
    print(f"  [{'ok' if cond else 'XX'}] {name}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)

import lk.model as M
from lk.ctx.store import ContextStore
from lk.kernel import invoke as INV
from lk.kernel.invoke import run_proactive
from lk.retrieval.pipeline import CitedResult

M.configure_backend(kind="local")

class _FakeRetrieval:
    def retrieve(self, queries, top_k=None):
        return [CitedResult(citation_num=1, url="https://x.test/a", title="A", text="chunk text")]

_PROACTIVE = '{"needs_retrieval": true, "queries": ["adjacent info"]}'

def script(brief_json, *, pre_brief=None):
    """Install a _post stub that returns the PROACTIVE pass then `brief_json` for
    the PROACTIVE_BRIEF pass. `pre_brief()` runs just before the brief is returned
    — used to simulate concurrent context advances arriving mid-run."""
    seq = [_PROACTIVE, brief_json]
    def _post(payload, timeout):
        nxt = seq.pop(0)
        if nxt is brief_json and pre_brief is not None:
            pre_brief()
        return {"choices": [{"message": {"content": nxt}}]}
    M._post = _post

def fresh_ctx():
    tmp = Path(tempfile.mkdtemp())
    ctx = ContextStore(mem_dir=tmp)
    ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="vision",
               compact="[VISION] editing", detailed="[VISION] user editing report.md")
    return ctx, tmp

# ── ContextStore freshness + finding reader (9a) ──────────────────────────────
print("\n§9a ContextStore.version() / recent_findings()")
_c, _t = fresh_ctx()
v0 = _c.version()
_c.append(ts=datetime.now(timezone.utc).isoformat(), kind="vision",
          compact="[VISION] more", detailed="[VISION] more")
check("append bumps version", _c.version() == v0 + 1, f"{v0}->{_c.version()}")
_c.append(ts=datetime.now(timezone.utc).isoformat(), kind="finding",
          compact="[FOUND] Cache miss", detailed="[PROACTIVE FINDING] Cache miss\nYour build skips the cache [1]")
rf = _c.recent_findings()
check("recent_findings parses headline", any(f["headline"] == "Cache miss" for f in rf), f"{rf}")
check("recent_findings parses insight", any("skips the cache" in f["insight"] for f in rf), f"{rf}")
v1 = _c.version()
_c.clear_rolling()
check("clear_rolling bumps version", _c.version() == v1 + 1)
shutil.rmtree(_t, ignore_errors=True)

# ── first finding surfaces ────────────────────────────────────────────────────
print("\n§9b surface once, then dedup the repeat")
ctx, tmp = fresh_ctx()
BRIEF = '{"surface": true, "headline": "Heads-up", "insight": "Useful fact [1]"}'
script(BRIEF)
found1 = []
run_proactive(ctx, _FakeRetrieval(), present_fn=found1.append)
check("first finding surfaces", len(found1) == 1 and found1[0]["headline"] == "Heads-up", f"{found1}")
check("finding recorded to context", "[PROACTIVE FINDING]" in ctx.tail_for_model())

# identical finding again → deduped (one card total)
script(BRIEF)
found2 = []
run_proactive(ctx, _FakeRetrieval(), present_fn=found2.append)
check("equivalent finding deduped (one card)", found2 == [], f"{found2}")

# near-identical wording (minor edits) → still deduped by ratio
script('{"surface": true, "headline": "Heads up", "insight": "A useful fact [1]"}')
found2b = []
run_proactive(ctx, _FakeRetrieval(), present_fn=found2b.append)
check("near-duplicate deduped by ratio", found2b == [], f"{found2b}")

# ── below-threshold (genuinely different) → new card allowed ──────────────────
print("\n§9b distinct finding still surfaces")
script('{"surface": true, "headline": "Migration risk", "insight": "Schema change may drop the users table without a backup [1]"}')
found3 = []
run_proactive(ctx, _FakeRetrieval(), present_fn=found3.append)
check("distinct finding surfaces", len(found3) == 1 and found3[0]["headline"] == "Migration risk", f"{found3}")
shutil.rmtree(tmp, ignore_errors=True)

# ── stale guard: context advanced too far mid-run → drop ──────────────────────
print("\n§9b stale guard")
import os
os.environ["LK_PROACTIVE_STALE_DELTA"] = "3"
ctx, tmp = fresh_ctx()
def advance(n):
    def _a():
        for i in range(n):
            ctx.append(ts=datetime.now(timezone.utc).isoformat(), kind="vision",
                       compact=f"[VISION] turn {i}", detailed=f"[VISION] user moved on {i}")
    return _a

# 4 concurrent appends (> delta 3) arrive while we work → drop
script('{"surface": true, "headline": "Stale insight", "insight": "About an old screen [1]"}', pre_brief=advance(4))
found4 = []
run_proactive(ctx, _FakeRetrieval(), present_fn=found4.append)
check("stale finding dropped (version moved too far)", found4 == [], f"{found4}")
check("stale finding not recorded to context", "Stale insight" not in ctx.tail_for_model())

# small advance (1 < delta) → still allowed
script('{"surface": true, "headline": "Fresh insight", "insight": "Still relevant [1]"}', pre_brief=advance(1))
found5 = []
run_proactive(ctx, _FakeRetrieval(), present_fn=found5.append)
check("small advance still surfaces", len(found5) == 1 and found5[0]["headline"] == "Fresh insight", f"{found5}")
shutil.rmtree(tmp, ignore_errors=True)

# ── busy inference gate → skip cleanly, nothing surfaced ──────────────────────
print("\n§9 droppable under busy gate")
ctx, tmp = fresh_ctx()
script('{"surface": true, "headline": "Whatever", "insight": "x [1]"}')
M._gate.acquire(M.PRI_TURN)
found6 = []
try:
    run_proactive(ctx, _FakeRetrieval(), present_fn=found6.append)
finally:
    M._gate.release()
check("proactive skipped while slot busy", found6 == [], f"{found6}")
shutil.rmtree(tmp, ignore_errors=True)

# ── pure-helper unit: _is_duplicate_finding / stale tunables ──────────────────
print("\n§9 helper units")
recent = [{"headline": "Build cache miss", "insight": "Your CI rebuilds from scratch every run [1]"}]
check("exact-ish duplicate detected",
      INV._is_duplicate_finding("Build cache miss", "Your CI rebuilds from scratch every run [1]", recent))
check("unrelated finding not duplicate",
      not INV._is_duplicate_finding("Disk almost full", "Root volume at 96% [2]", recent))
check("empty recent → never duplicate", not INV._is_duplicate_finding("anything", "x", []))
os.environ["LK_PROACTIVE_STALE_DELTA"] = "not-an-int"
check("bad stale-delta env falls back to default 3", INV._proactive_stale_delta() == 3)
os.environ.pop("LK_PROACTIVE_STALE_DELTA", None)

# ── N-07 observability: proactive_stats() reflects every outcome above ─────────
# 7 run_proactive() calls ran above: 3 surfaced, 2 deduped, 1 stale-dropped, 1
# busy-skipped. The counters make "is the autonomous loop firing?" answerable.
print("\nN-07 proactive observability counters")
from lk.kernel.invoke import proactive_stats
st = proactive_stats()
check("stats: calls counted (every invocation)",   st["calls"]    >= 7, str(st))
check("stats: surfaced counted (cards shown)",      st["surfaced"] >= 3, str(st))
check("stats: dup counted (deduped repeats)",       st["dup"]      >= 2, str(st))
check("stats: stale counted (dropped late)",        st["stale"]    >= 1, str(st))
check("stats: skipped counted (busy slot)",         st["skipped"]  >= 1, str(st))

if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\nALL PROACTIVE DEDUP CHECKS PASSED")
