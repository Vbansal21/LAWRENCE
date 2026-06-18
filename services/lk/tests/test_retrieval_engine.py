"""N-05 — unified RetrievalEngine: DISCERN → per-category parallel chains → iterative
→ final collective rank.

Deterministic + offline. The model is an injected stub (`call_fn`) that returns canned
RETRIEVAL_PLAN / RETRIEVAL_ASSESS envelopes keyed by the schema it is handed; the notes
arm uses a real in-memory MemoryIndex (bag-of-words embed), the doc/web arms a real
SemanticDB pre-seeded with file:// and http:// rows, and web fetch is stubbed out — so
each arm, the iteration loop, the collective rank, and every degrade path are exercised
without a model server or the network.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "services")

FAILS = []
def check(name, cond, extra=""):
    print(f"  [{'ok' if cond else 'XX'}] {name}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


from lk.kernel import schemas
from lk.retrieval import evidence_assets
from lk.retrieval.db import SemanticDB
from lk.retrieval.engine import RetrievalEngine, GatherResult
from lk.retrieval.memory import MemoryIndex
import lk.retrieval.web as webmod


def make_embed():
    import re as _re
    def embed(texts):
        out = []
        for t in texts:
            v = [0.0] * 64
            for w in _re.findall(r"[a-z0-9]+", t.lower()):
                v[sum(ord(c) for c in w) % 64] += 1.0
            out.append(v)
        return out
    return embed


# ── stub model: canned envelopes keyed by schema ─────────────────────────────────
RESP = {"plan": {}, "assess": {}}
calls = {"plan": 0, "assess": 0}

def stub_call(messages, **kw):
    sch = kw.get("schema")
    if sch is schemas.RETRIEVAL_PLAN:
        calls["plan"] += 1
        return {"text": json.dumps(RESP["plan"])}
    if sch is schemas.RETRIEVAL_ASSESS:
        calls["assess"] += 1
        return {"text": json.dumps(RESP["assess"])}
    return {"text": "{}"}


def reset_calls():
    calls["plan"] = 0
    calls["assess"] = 0


_ENV_KEYS = ["LK_RETRIEVAL", "LK_RETRIEVAL_ENFORCE", "LK_RETRIEVAL_ITERS",
             "LK_RETRIEVAL_ASSESS", "LK_RETRIEVAL_TOP_K", "LK_RETRIEVAL_MIN_RESULTS",
             "LK_RETRIEVAL_DEPTH", "LK_RETRIEVAL_CATEGORIES"]


tmp = Path(tempfile.mkdtemp(prefix="lk-engine-"))
_saved_env = {k: os.environ.get(k) for k in _ENV_KEYS}
_saved_fetch = webmod.search_and_fetch
try:
    # never touch the network — the web arm's fresh fetch is neutralised
    webmod.search_and_fetch = lambda queries, max_per_query=3: []

    # notes (own memory)
    mem = MemoryIndex(tmp / "mem.db", embed_fn=make_embed())
    mem.upsert("nphys", "note", "quark gluon plasma physics experiment at the collider", title="physics")
    mem.upsert("ncook", "note", "a sourdough bread baking recipe", title="cooking")
    mem.upsert("nrefine", "note", "obscure tax deduction rule for freelancers", title="tax")

    # doc (file://) + web (http://) rows in one SemanticDB
    sem = SemanticDB(tmp / "sem.db")
    sem.upsert("https://w1.test/a", "Web A", ["quark gluon plasma collider results from CERN today"])
    sem.upsert("https://w2.test/b", "Web B", ["unrelated celebrity gossip news of the week"])
    sem.upsert("file:///docs/d1.md", "Doc One", ["internal design doc about plasma containment fields"])
    sem.upsert("file:///docs/d2.md", "Doc Two", ["meeting notes about the quarterly budget review"])

    engine = RetrievalEngine(db=sem, memory=mem, call_fn=stub_call)

    # ── basic gather: discern → all three arms → unified cited bundle ─────────────
    print("\nRetrievalEngine — basic gather (all categories)")
    os.environ["LK_RETRIEVAL_MIN_RESULTS"] = "1"   # arms satisfied in one round → no assess
    os.environ["LK_RETRIEVAL_ASSESS"] = "1"
    os.environ.pop("LK_RETRIEVAL_ENFORCE", None)
    RESP["plan"] = {
        "context_understanding": "the user is researching quark gluon plasma",
        "needs_retrieval": True,
        "notes_queries": ["quark plasma physics"],
        "doc_queries": ["plasma containment"],
        "web_queries": ["quark gluon plasma collider"],
        "capture_hires": False,
    }
    reset_calls()
    res = engine.gather("tell me about quark gluon plasma", short_ctx="(rolling ctx)", priority=0)
    check("returns a GatherResult", isinstance(res, GatherResult))
    check("context_understanding captured (the Raw/draft)", "quark gluon plasma" in res.context_understanding)
    check("per-category queries planned", set(res.queries) == {"notes", "doc", "web"}, f"{res.queries}")
    check("evidence is non-empty", bool(res.evidence), f"{len(res.evidence)}")
    cats = {r.category for r in res.evidence}
    check("bundle spans all three categories (collective fusion, no arm starved)",
          cats == {"notes", "doc", "web"}, f"{cats}")
    nums = [r.citation_num for r in res.evidence]
    check("citations are one consistent 1..N space", nums == list(range(1, len(res.evidence) + 1)), f"{nums}")
    check("no assess call when arms already sufficient", calls["assess"] == 0, f"{calls}")
    check("evidence maps to typed asset cards (FR-008)", len(evidence_assets(res.evidence)) == len(res.evidence))

    # ── per-arm isolation: a failing arm must not sink the others ─────────────────
    print("\nRetrievalEngine — a failing arm is isolated")
    class BrokenMem:
        def recall(self, *a, **k):
            raise RuntimeError("notes arm down")
    eng_broken = RetrievalEngine(db=sem, memory=BrokenMem(), call_fn=stub_call)
    reset_calls()
    rb = eng_broken.gather("quark gluon plasma", short_ctx="(ctx)", priority=0)
    bcats = {r.category for r in rb.evidence}
    check("doc + web still returned when the notes arm raises", {"doc", "web"} <= bcats, f"{bcats}")
    check("the broken notes arm contributes nothing", "notes" not in bcats, f"{bcats}")

    # ── iterative refine: an under-filled arm triggers an ASSESS + refine round ───
    print("\nRetrievalEngine — dynamic iteration (assess → refine → retry)")
    os.environ["LK_RETRIEVAL_MIN_RESULTS"] = "99"   # force "insufficient" every round
    os.environ["LK_RETRIEVAL_ITERS"] = "2"
    RESP["plan"] = {
        "context_understanding": "freelance tax question",
        "needs_retrieval": True,
        "notes_queries": ["quark plasma physics"],   # round 1 finds nphys, NOT nrefine
        "doc_queries": [], "web_queries": [], "capture_hires": False,
    }
    RESP["assess"] = {"sufficient": False, "refined_notes": ["freelancer tax deduction rule"],
                      "refined_doc": [], "refined_web": []}
    reset_calls()
    ri = engine.gather("how do freelancer tax deductions work", short_ctx="(ctx)", priority=0)
    keys = {r.url for r in ri.evidence}
    check("refined query surfaced a node unreachable in round 1",
          "memory://nrefine" in keys, f"{keys}")
    check("two rounds ran", ri.iterations == 2, f"iters={ri.iterations}")
    check("assessor was consulted between rounds", calls["assess"] >= 1, f"{calls}")

    print("\nRetrievalEngine — dynamic stop on 'sufficient'")
    RESP["assess"] = {"sufficient": True}
    reset_calls()
    rs = engine.gather("quark plasma", short_ctx="(ctx)", priority=0)
    check("stops after one round when assessor says sufficient", rs.iterations == 1, f"iters={rs.iterations}")
    check("assessor consulted exactly once", calls["assess"] == 1, f"{calls}")

    # ── degrade: model down → heuristic queries still retrieve ───────────────────
    print("\nRetrievalEngine — degrades when the model is down (enforced heuristic queries)")
    os.environ["LK_RETRIEVAL_MIN_RESULTS"] = "1"
    os.environ.pop("LK_RETRIEVAL_ENFORCE", None)     # default enforce = on
    def boom(*a, **k):
        raise RuntimeError("model down")
    eng_down = RetrievalEngine(db=sem, memory=mem, call_fn=boom)
    rd = eng_down.gather("quark gluon plasma", short_ctx="(ctx)", priority=0)
    check("retrieval still happens with no model (enforced)", bool(rd.evidence), f"{len(rd.evidence)}")
    check("no discerned context when the model is down", rd.context_understanding == "")

    # ── degrade: no backends at all → empty, never raises ────────────────────────
    print("\nRetrievalEngine — degrades when no backends are available")
    eng_bare = RetrievalEngine(db=None, memory=None, call_fn=stub_call)
    RESP["plan"] = {"context_understanding": "x", "needs_retrieval": True,
                    "web_queries": ["anything"], "notes_queries": ["x"], "doc_queries": ["x"]}
    rbare = eng_bare.gather("anything", short_ctx="(ctx)", priority=0)
    check("no db/memory + stubbed web → empty bundle, no crash", rbare.evidence == [], f"{rbare.evidence}")

    # ── enforce off + needs_retrieval false → short-circuit ──────────────────────
    print("\nRetrievalEngine — enforce off honours a 'no retrieval' verdict")
    os.environ["LK_RETRIEVAL_ENFORCE"] = "0"
    RESP["plan"] = {"context_understanding": "just chit-chat", "needs_retrieval": False}
    rc = engine.gather("hello there", short_ctx="(ctx)", priority=0)
    check("no retrieval when not enforced and model says no", rc.evidence == [], f"{rc.evidence}")
    check("but the situation is still discerned", rc.context_understanding == "just chit-chat")
    os.environ.pop("LK_RETRIEVAL_ENFORCE", None)

    # ── master switch off ────────────────────────────────────────────────────────
    print("\nRetrievalEngine — master switch (LK_RETRIEVAL=0) disables the engine")
    os.environ["LK_RETRIEVAL"] = "0"
    roff = engine.gather("quark gluon plasma", short_ctx="(ctx)", priority=0)
    check("disabled engine returns an empty result", roff.evidence == [] and roff.context_understanding == "")

finally:
    webmod.search_and_fetch = _saved_fetch
    for k, v in _saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    shutil.rmtree(tmp, ignore_errors=True)

if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\nALL RETRIEVAL-ENGINE CHECKS PASSED")
