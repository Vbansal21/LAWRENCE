"""§10 — retrieval dedup, per-URL caps, and recency.

Deterministic + offline: a FakeDB feeds candidate chunks and `search_and_fetch`
is stubbed to return nothing, so ranking/dedup/recency are exercised without a
network or a real SQLite file.
"""
import sys, copy, time
sys.path.insert(0, "services")

FAILS = []
def check(name, cond, extra=""):
    print(f"  [{'ok' if cond else 'XX'}] {name}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)

from lk.retrieval import pipeline as P
from lk.retrieval.pipeline import RetrievalPipeline, _norm_chunk, _recency_factor, _is_local, _is_web
from lk.retrieval.db import StoredChunk
from lk.retrieval.web import WebChunk

# No network: any web fetch returns nothing.
P.search_and_fetch = lambda queries, max_per_query=3: []

class FakeDB:
    def __init__(self, chunks):
        self._chunks = chunks
    def search(self, query, top_k=10):
        return list(self._chunks)[:top_k]
    def upsert(self, url, title, texts):
        return 0

def pipe(chunks):
    return RetrievalPipeline(db=FakeDB(chunks))

# ── 10a: near-duplicate chunks collapse (case/whitespace/punctuation) ─────────
print("\n§10a near-duplicate collapse")
chunks = [
    StoredChunk(url="u1", title="A", text="Alpha report findings."),
    StoredChunk(url="u2", title="B", text="alpha   report  findings"),   # near-dup of A
    StoredChunk(url="u3", title="C", text="Beta alpha summary conclusions"),
]
res = pipe(chunks).retrieve(["alpha report"])
urls = [r.url for r in res]
check("normalize collapses case/whitespace/punct variants",
      _norm_chunk("Alpha report findings.") == _norm_chunk("alpha   report  findings"))
check("near-duplicate chunk dropped (one survives across URLs)", len(res) == 2, f"urls={urls}")
check("the distinct chunk survives", "u3" in urls and "u2" not in urls, f"urls={urls}")
norms = [_norm_chunk(r.text) for r in res]
check("no duplicate text in results", len(norms) == len(set(norms)), f"{norms}")

# ── 10b: per-URL cap (unit on the chokepoint helper) ──────────────────────────
print("\n§10b per-URL cap before ranking")
p = pipe([])
p.max_chunks_per_url = 2
cands = [(WebChunk(url="u1", title="t", text=f"unique body number {i}"), 0.0, False) for i in range(5)]
cands.append((WebChunk(url="u2", title="t", text="other page body"), 0.0, False))
capped = p._dedup_and_cap(cands)
n_u1 = sum(1 for c, _, _ in capped if c.url == "u1")
n_u2 = sum(1 for c, _, _ in capped if c.url == "u2")
check("one URL capped to max_chunks_per_url", n_u1 == 2, f"n_u1={n_u1}")
check("a second URL is not crowded out", n_u2 == 1, f"n_u2={n_u2}")

# ── 10c: recency factor — file:// never stale, mild web boost, never penalised ─
print("\n§10c recency factor")
now = time.time()
old = now - 100 * 86400
check("local file:// is never stale (old → neutral 1.0)", _recency_factor(True, old, now) == 1.0)
check("_is_local detects file:// ingested rows", _is_local("file:///home/u/doc.md") and not _is_local("https://x/y"))
check("_is_web accepts only HTTP(S), not note:// rows",
      _is_web("https://x/y") and not _is_web("note://n1") and not _is_web("file:///x"))
fresh_f = _recency_factor(False, now, now)
old_f   = _recency_factor(False, old, now)
unk_f   = _recency_factor(False, 0.0, now)
check("fresh web row gets a mild boost (>1.0)", fresh_f > 1.0, f"{fresh_f}")
check("recency boost is mild (<=1.2)", fresh_f <= 1.2, f"{fresh_f}")
check("old web row decays to neutral, never penalised", abs(old_f - 1.0) < 1e-9, f"{old_f}")
check("unknown-timestamp web row is neutral", unk_f == 1.0, f"{unk_f}")

# ── 10c integration: newer web row wins a BM25 tie ────────────────────────────
print("\n§10c recency breaks a ranking tie")
# Same bag-of-words + length (BM25 ties) but different word order → distinct
# normalized keys, so both survive dedup; the newer one should rank first.
tie = [
    StoredChunk(url="u-old", title="old", text="alpha beta gamma", ts_fetched=old),
    StoredChunk(url="u-new", title="new", text="gamma beta alpha", ts_fetched=now),
]
res2 = pipe(tie).retrieve(["alpha beta gamma"])
check("both tied rows survive dedup (distinct order)", len(res2) == 2, f"{[r.url for r in res2]}")
check("newer web row ranks first on a tie", res2 and res2[0].url == "u-new", f"{[r.url for r in res2]}")

# ── 10d: deep search widens breadth without mutating instance defaults ────────
print("\n§10d deep-search shallow copy")
base = pipe([])
base_topk, base_cap = base.top_k, base.max_chunks_per_url
deep = copy.copy(base)            # mirrors ui_bridge._retrieval_for_turn(deep=True)
deep.top_k, deep.fresh_per_q, deep.db_min_hits = 12, 8, 6
check("deep copy inherits the per-URL cap", deep.max_chunks_per_url == base_cap)
check("base defaults are not mutated by deep search", base.top_k == base_topk)
deep.max_chunks_per_url = 2
many = [(WebChunk(url="u1", title="t", text=f"body {i}"), 0.0, False) for i in range(6)]
check("deep search still obeys the per-URL cap",
      sum(1 for c, _, _ in deep._dedup_and_cap(many) if c.url == "u1") == 2)

# ── stable source numbers ─────────────────────────────────────────────────────
print("\n§10 stable citation numbering")
nums = [r.citation_num for r in res]
check("citation numbers are 1..k in rank order", nums == list(range(1, len(res) + 1)), f"{nums}")

if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\nALL RETRIEVAL RANK CHECKS PASSED")
