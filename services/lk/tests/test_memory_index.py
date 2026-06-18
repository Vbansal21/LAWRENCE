"""N-02 — hybrid memory recall: MemoryIndex + reindex backfill.

Deterministic + offline. The vector arm is driven by an injected stub embed_fn
(a stable bag-of-words hash, plus exact-text overrides) so the lexical / vector /
graph / recency / link / delete behaviours are each isolated and asserted without
a model server or the network. The graph arm uses a real NoteStore over a temp
memory dir.
"""
import re
import sys
import shutil
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "services")

FAILS = []
def check(name, cond, extra=""):
    print(f"  [{'ok' if cond else 'XX'}] {name}" + (f"  ({extra})" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


from lk.retrieval.memory import MemoryIndex, RecallResult, format_recall, _rrf, _recency_boost
from lk.retrieval.reindex import backfill
from lk.ctx.notes import NoteStore


def make_embed(overrides=None):
    """Stable, offline embedder: exact-text overrides win; else a 64-dim
    bag-of-words count (deterministic — no builtin hash()). The wide dim keeps
    unrelated texts near-orthogonal so the vector arm's cosine floor cleanly
    separates real semantic matches from noise."""
    overrides = overrides or {}
    def embed(texts):
        out = []
        for t in texts:
            if t in overrides:
                out.append(list(overrides[t]))
                continue
            v = [0.0] * 64
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                v[sum(ord(c) for c in w) % 64] += 1.0
            out.append(v)
        return out
    return embed


tmp = Path(tempfile.mkdtemp(prefix="lk-mem-"))
try:
    # ── RRF + recency unit checks ────────────────────────────────────────────────
    print("\nMemoryIndex — fusion + recency primitives")
    fused = _rrf({"a": ["x", "y"], "b": ["y", "z"]})
    check("RRF rewards agreement (y in both arms ranks top)",
          max(fused, key=fused.get) == "y", f"{fused}")
    now = time.time()
    check("recency boost: newer > older",
          _recency_boost(now, now) > _recency_boost(now - 60 * 86400, now))
    check("recency boost: unknown ts is neutral", _recency_boost(0.0, now) == 1.0)

    # ── lexical recall + idempotency ─────────────────────────────────────────────
    print("\nMemoryIndex — lexical recall + idempotent upsert")
    mi = MemoryIndex(tmp / "idx.db", embed_fn=make_embed())
    changed = mi.upsert("n1", "note", "the quark hadron plasma experiment", title="physics")
    mi.upsert("n2", "note", "a recipe for sourdough bread", title="cooking")
    check("upsert reports change on first write", changed is True)
    check("upsert idempotent on identical text", mi.upsert("n1", "note", "the quark hadron plasma experiment") is False)
    check("upsert reports change on edited text", mi.upsert("n1", "note", "the quark gluon plasma experiment") is True)

    res = mi.recall("quark plasma", k=5)
    check("lexical recall finds the matching node first", res and res[0].node_id == "n1", f"{[r.node_id for r in res]}")
    check("recall result is provenance-tagged", bool(res) and res[0].source_kind == "note" and "lexical" in res[0].arms, f"{res[0].arms if res else None}")
    # An unrelated node may surface as a weak tail candidate, but recall must keep
    # it far below the real match (precision-at-top is the property that matters).
    n2score = next((r.score for r in res if r.node_id == "n2"), 0.0)
    check("unrelated node is strongly outranked by the real match",
          res[0].node_id == "n1" and n2score < res[0].score * 0.6, f"n1={res[0].score:.4f} n2={n2score:.4f}")
    check("empty query -> []", mi.recall("") == [])

    # ── vector arm isolated from lexical ─────────────────────────────────────────
    print("\nMemoryIndex — vector arm (no lexical overlap)")
    ov = {"zzz topic": [1.0] + [0.0] * 15, "alpha cats document": [1.0] + [0.0] * 15}
    miv = MemoryIndex(tmp / "vec.db", embed_fn=make_embed(ov))
    miv.upsert("v1", "note", "alpha cats document")
    rv = miv.recall("zzz topic", k=5)
    check("vector arm recalls a node with zero lexical overlap",
          any(r.node_id == "v1" for r in rv), f"{[(r.node_id, r.arms) for r in rv]}")
    check("that hit is tagged as a vector arm hit",
          any(r.node_id == "v1" and "vector" in r.arms and "lexical" not in r.arms for r in rv))
    check("stats report embedded vectors", miv.stats()["embedded"] == 1 and miv.stats()["vectors"] == 1, f"{miv.stats()}")

    # ── graph arm + link boost (G) via NoteStore ─────────────────────────────────
    print("\nMemoryIndex — graph expansion + link boost")
    nmem = tmp / "graphmem"
    notes = NoteStore(mem_dir=nmem)
    aid = notes.write_note("obs", "deadline for the tax filing project")
    bid = notes.write_note("obs", "remember to call the accountant on friday")
    notes.add_edge(aid, bid, kind="link")          # user links A → B
    mg = MemoryIndex(tmp / "graph.db", notes=notes, embed_fn=make_embed())
    mg.upsert(aid, "note", "deadline for the tax filing project")
    mg.upsert(bid, "note", "remember to call the accountant on friday")
    rg = mg.recall("tax filing deadline", k=5)
    ids = [r.node_id for r in rg]
    check("seed node (A) recalled lexically", aid in ids, f"{ids}")
    check("linked node (B) surfaced via graph despite no lexical/vector match",
          bid in ids and "graph" in next(r.arms for r in rg if r.node_id == bid), f"{[(r.node_id, r.arms) for r in rg]}")

    # link boost actually raises score: same node, with vs without an incoming link
    base_idx = MemoryIndex(tmp / "noboost.db", embed_fn=make_embed())
    base_idx.upsert("k1", "note", "deadline for the tax filing project")
    plain = base_idx.recall("tax filing deadline")[0].score
    boosted = next(r.score for r in mg.recall("tax filing deadline") if r.node_id == aid)
    check("explicit link boosts the linked node's score (G term)", boosted > plain, f"{boosted} vs {plain}")

    # ── delete penalty (P) — reversible suppression ──────────────────────────────
    print("\nMemoryIndex — delete penalty (reversible)")
    mg.mark_deleted(aid)
    check("deleted node is excluded from recall", all(r.node_id != aid for r in mg.recall("tax filing deadline")))
    mg.clear_deleted(aid)
    check("cleared delete restores the node", any(r.node_id == aid for r in mg.recall("tax filing deadline")))

    # ── recency ordering ─────────────────────────────────────────────────────────
    print("\nMemoryIndex — recency ordering")
    mr = MemoryIndex(tmp / "rec.db", embed_fn=make_embed())
    now = time.time()
    mr.upsert("old", "log", "meeting about the budget review", ts=now - 120 * 86400)
    mr.upsert("new", "log", "meeting about the budget review again", ts=now - 1 * 86400)
    rr = mr.recall("budget review meeting", k=5)
    check("more recent node outranks the stale one", rr and rr[0].node_id == "new", f"{[(r.node_id, round(r.score, 4)) for r in rr]}")

    # ── local-first degrade: embedding backend unavailable ───────────────────────
    print("\nMemoryIndex — degrades when no embedding backend")
    def boom(_texts):
        raise RuntimeError("no embedding backend")
    md = MemoryIndex(tmp / "degrade.db", embed_fn=boom)
    md.upsert("d1", "note", "the photosynthesis lecture notes")
    check("upsert still stores when embedding fails", md.stats()["nodes"] == 1 and md.stats()["embedded"] == 0, f"{md.stats()}")
    check("recall still works lexically with no vector arm", any(r.node_id == "d1" for r in md.recall("photosynthesis lecture")))

    # ── persistence: vectors rebuilt from SQLite on reopen ───────────────────────
    print("\nMemoryIndex — persistence (vectors rebuilt from store)")
    miv.close()
    reopened = MemoryIndex(tmp / "vec.db", embed_fn=make_embed(ov))
    check("vectors reloaded from SQLite on reopen", len(reopened._vec) == 1, f"{len(reopened._vec)}")
    check("recall works after reopen", any(r.node_id == "v1" for r in reopened.recall("zzz topic")))

    # ── reindex backfill over a synthetic memory tree ────────────────────────────
    print("\nreindex.backfill — every source")
    md_dir = tmp / "memtree"
    (md_dir / "notes").mkdir(parents=True)
    (md_dir / "chats" / "c-0001").mkdir(parents=True)
    (md_dir / "journal").mkdir(parents=True)
    # a note (+ its index row)
    (md_dir / "notes" / "20260101-000000-x.md").write_text(
        "---\nid: 20260101-000000\n---\nthe migratory patterns of arctic terns\n", encoding="utf-8")
    (md_dir / "notes" / "index.jsonl").write_text(
        '{"id": "20260101-000000", "ts": "2026-01-01T00:00:00+00:00", "kind": "obs", "tags": ["birds"], "file": "20260101-000000-x.md"}\n',
        encoding="utf-8")
    # a chat transcript
    (md_dir / "chats" / "index.jsonl").write_text('{"id": "c-0001", "title": "rocketry chat"}\n', encoding="utf-8")
    (md_dir / "chats" / "c-0001" / "messages.jsonl").write_text(
        '{"seq": 1, "id": "c-0001:1", "role": "user", "text": "how do ion thrusters work", "ts": "2026-02-01T00:00:00+00:00"}\n',
        encoding="utf-8")
    # rolling working-memory + daily log + journal
    (md_dir / "rolling-l1.jsonl").write_text(
        '{"ts": "2026-03-01T00:00:00+00:00", "kind": "vision", "detailed": "the user is editing a terraform configuration"}\n',
        encoding="utf-8")
    (md_dir / "context-2026-03-01.log").write_text("[VISION 10:00:00] terraform kubernetes cluster\n", encoding="utf-8")
    (md_dir / "journal" / "2026-03-02.mdx").write_text(
        '---\ntitle: "Journal"\n---\ntoday I debugged the payment webhook retry logic\n', encoding="utf-8")

    bi = MemoryIndex(tmp / "backfill.db", embed_fn=make_embed())
    counts = backfill(bi, mem_dir=md_dir)
    check("backfill indexed all five sources",
          all(counts.get(s) == 1 for s in ("notes", "chats", "rolling", "log", "journal")), f"{counts}")
    check("backfill is idempotent (re-run changes nothing)", backfill(bi, mem_dir=md_dir)["total"] == 0)
    check("recall finds note content", any("tern" in r.text for r in bi.recall("arctic terns migration")))
    check("recall finds chat content", any(r.source_kind == "chat" for r in bi.recall("ion thruster")))
    check("recall finds journal content", any(r.source_kind == "journal" for r in bi.recall("payment webhook retry")))
    check("recall finds rolling context", any(r.source_kind == "rolling" for r in bi.recall("terraform configuration")))

    # ── format_recall — the N-06 turn-context block ──────────────────────────────
    print("\nformat_recall — turn-context rendering")
    check("empty recall renders to empty string", format_recall([]) == "")
    block = format_recall([
        RecallResult("a", "note", 0.0, "t", "remember the project deadline is friday"),
        RecallResult("b", "chat", 0.0, "t", "we discussed the budget earlier"),
    ])
    check("block is provenance-tagged for the model",
          "RECALLED MEMORY" in block and "(note)" in block and "(chat)" in block, block)
    long = format_recall([RecallResult("x", "note", 0.0, "", "word " * 400)], max_chars=200)
    check("block is budget-bounded", len(long) <= 260, f"len={len(long)}")

finally:
    shutil.rmtree(tmp, ignore_errors=True)

if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\nALL MEMORY-INDEX CHECKS PASSED")
