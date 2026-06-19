"""Unified retrieval engine (N-05) — Perplexity-style, context-grounded.

This is the "researches until it has enough" half of the watcher. It replaces the
old single-shot `analysis → one retrieve → answer` path with a loop that matches the
locked 2026-06-18 design (see docs/PLAN.md §J):

  Phase A — DISCERN.  ONE model call drafts the agent's understanding of the CURRENT
            situation (the "Raw/draft") from the short rolling context + the long
            summary/recall digest, and ONLY from that produces per-category queries.
            Correct retrieval is only possible from correct context.
  Phase B — PER-CATEGORY PARALLEL CHAINS.  Each category — notes (own memory), doc
            (ingested files), web (public search) — runs its OWN retrieve→rank chain,
            in parallel. When an arm is thin and rounds remain, a single shared ASSESS
            call judges sufficiency and emits refined per-arm queries; the arms loop.
            The model's `sufficient` verdict is the dynamic stop; `max_iter` +
            `should_stop`/deadline are the hard caps (configurable + dynamic).
  Phase C — FINAL COLLECTIVE RANK.  Reciprocal-Rank-Fusion across the per-arm rankings
            (scale-free) blended with a global BM25 score (cross-arm agreement AND
            lexical strength) → ONE consistently-cited bundle spanning all categories.

Design guarantees (mirror the rest of the kernel):
  • Local-first ([[lawrence-local-first]]): the discern/assess calls run under the
    `retrieve` role, which defaults to the LOCAL backend (planning over personal context
    never ships to a cloud by default; API opt-in via routing.retrieve).
  • Degraded / never raises: model down → heuristic queries from the need; an arm that
    errors is isolated; no embedding/web backend ⇒ that arm is skipped, not fatal.
  • Provider-agnostic (I3): every model touch is behind the `retrieve` role seam.
  • stdlib core, heavy deps lazy (I4): reuses SemanticDB (web/doc) + MemoryIndex (notes);
    adds no new on-disk store. Knobs are read from the env each call so `lk set` /
    `/set` take effect without a restart.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from .memory   import _rrf
from .pipeline import CitedResult, _is_local, _is_web, _norm_chunk
from .ranker   import _tokenize
from .ranker   import rank as _bm25_rank
from ..policy import sanitize_web_query

CATEGORIES = ("notes", "doc", "web")

# ── knob defaults (env-overridable; live-patchable) ──────────────────────────
DEF_ITERS       = 2     # max iterative rounds per arm (base profile)
DEF_TOP_K       = 8     # final fused bundle size
DEF_MIN_RESULTS = 3     # per-arm sufficiency floor (below ⇒ candidate for a refine round)
DEF_DEPTH       = 8     # candidates pulled per arm per query
DEF_FRESH       = 3     # fresh web results fetched per under-served query
# deepSearch per-turn profile (FR deep-web flag; raised breadth, no global mutation)
DEEP_ITERS      = 3
DEEP_TOP_K      = 18
DEEP_FRESH      = 8
MAX_PER_URL     = 3     # candidate-pool cap so one page can't crowd a category


# ── env readers ──────────────────────────────────────────────────────────────

def _env_flag(name: str, default: bool = True) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() not in ("0", "false", "no", "off")


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


def _env_csv(name: str, default: tuple[str, ...]) -> list[str]:
    v = os.environ.get(name)
    if not v:
        return list(default)
    items = [x.strip().lower() for x in v.split(",") if x.strip()]
    return [x for x in items if x in CATEGORIES] or list(default)


def _clean_queries(qs: Any, *, limit: int = 4) -> list[str]:
    """Normalise a model-emitted query array: strings, stripped, de-duped, bounded."""
    if not isinstance(qs, list):
        return []
    out: list[str] = []
    for q in qs:
        s = str(q).strip()
        if s and s not in out:
            out.append(s)
    return out[:limit]


def _fallback_queries(text: str) -> list[str]:
    """Heuristic query when the model gave none (degraded / enforcement): use the need
    verbatim (natural-language search works), backed by its salient content tokens."""
    text = (text or "").strip()
    if not text:
        return []
    qs = [text[:120]]
    toks = _tokenize(text)            # ranker tokens: len≥3, stopwords dropped
    if toks:
        kw = " ".join(toks[:8])
        if kw and kw not in qs:
            qs.append(kw)
    return qs


# ── results ──────────────────────────────────────────────────────────────────

@dataclass
class GatherResult:
    """The unified evidence bundle + the discerned situation, for one gather()."""
    context_understanding: str = ""
    evidence:    list[CitedResult]        = field(default_factory=list)
    capture_hires: bool                   = False
    queries:     dict[str, list[str]]     = field(default_factory=dict)
    iterations:  int                      = 0


@dataclass
class _Candidate:
    key:      str    # identity / dedup key — url or memory://<node_id>
    category: str    # notes | doc | web
    title:    str
    text:     str
    url:      str


def _merge_candidates(existing: list[_Candidate], new: list[_Candidate]) -> list[_Candidate]:
    """Append round-N candidates not already present, preserving per-arm rank order."""
    seen = {c.key for c in existing}
    out = list(existing)
    for c in new:
        if c.key not in seen:
            seen.add(c.key)
            out.append(c)
    return out


# ── engine ─────────────────────────────────────────────────────────────────────

class RetrievalEngine:
    """Orchestrates DISCERN → per-category parallel chains → collective rank.

    ``db`` (optional :class:`SemanticDB`) backs the web + doc arms; ``memory``
    (optional :class:`MemoryIndex`) backs the notes arm. ``call_fn`` injects the model
    call for tests; in production it lazily uses ``lk.model.call_model`` (role
    ``retrieve``). Any missing collaborator simply drops the affected arm.
    """

    def __init__(self, *, db: Any = None, memory: Any = None,
                 call_fn: Callable[..., dict] | None = None) -> None:
        self._db      = db
        self._memory  = memory
        self._call_fn = call_fn

    # ── public API ──────────────────────────────────────────────────────────────

    def gather(
        self, need: str, *,
        short_ctx: str = "", long_ctx: str = "",
        proactive: bool = False, deep: bool = False,
        priority: int | None = None, timeout: int = 300,
        should_stop: Callable[[], bool] | None = None,
        live_fn: Callable[[str], None] | None = None,
    ) -> GatherResult:
        if not _env_flag("LK_RETRIEVAL", True):
            return GatherResult()
        need = (need or "").strip()
        cats = self._active_categories()
        if not cats:
            return GatherResult()
        if priority is None:
            priority = self._default_priority(proactive)

        max_iter = self._iters(deep)
        depth    = self._depth()
        top_k    = self._top_k(deep)
        fresh    = self._fresh(deep)

        # long context for the discern pass = a recall digest over the need (the "long"
        # half of "context (short & long) based"); computed once if the caller didn't.
        if not long_ctx and self._memory is not None and need:
            try:
                from .memory import format_recall
                long_ctx = format_recall(self._memory.recall(need, k=4))
            except Exception:
                long_ctx = ""

        # ── Phase A — DISCERN ─────────────────────────────────────────────────────
        plan = self._discern(need, short_ctx, long_ctx, proactive,
                             priority, timeout, should_stop) or {}
        understanding = str(plan.get("context_understanding", "")).strip()
        capture_hires = bool(plan.get("capture_hires"))
        queries = {
            "notes": _clean_queries(plan.get("notes_queries")),
            "doc":   _clean_queries(plan.get("doc_queries")),
            "web":   _clean_queries(plan.get("web_queries")),
        }
        needs = bool(plan.get("needs_retrieval", True))

        # Enforcement (FR-003): an ENABLED category runs every turn regardless of the
        # classifier — fill any empty enabled arm with heuristic queries. When NOT
        # enforcing, a model "no retrieval" verdict short-circuits.
        seed = need or understanding or short_ctx
        if self._enforce():
            for c in cats:
                if not queries.get(c):
                    queries[c] = _fallback_queries(seed)
        elif not needs:
            return GatherResult(context_understanding=understanding,
                                capture_hires=capture_hires, queries=queries)

        queries = {c: queries.get(c, []) for c in cats}    # restrict to active arms

        # ── Phase B — per-category PARALLEL chains, shared-assess iteration ────────
        arm_results: dict[str, list[_Candidate]] = {c: [] for c in cats}
        cur_queries = {c: list(queries.get(c, [])) for c in cats}
        iterations = 0
        for round_i in range(max_iter):
            active = {c: qs for c, qs in cur_queries.items() if qs}
            if not active:
                break
            iterations += 1
            with ThreadPoolExecutor(max_workers=max(1, len(active))) as pool:
                futs = {c: pool.submit(self._run_arm, c, qs, depth, fresh)
                        for c, qs in active.items()}
                for c, fut in futs.items():
                    try:
                        hits = fut.result()
                    except Exception:
                        hits = []
                    arm_results[c] = _merge_candidates(arm_results[c], hits)
                    if live_fn and hits:
                        live_fn(f"[retrieve] {c}: {len(arm_results[c])} source(s)"
                                + (" (deep)" if deep else ""))
            if should_stop and should_stop():
                break
            if round_i + 1 >= max_iter:
                break
            # dynamic stop: every arm satisfied → done; else ask the assessor to refine.
            under = [c for c in cats if len(arm_results[c]) < self._min_results()]
            if not under or not self._assess_enabled():
                break
            assess = self._assess(need, understanding, arm_results,
                                  priority, timeout, should_stop)
            if assess is None or bool(assess.get("sufficient", True)):
                break
            cur_queries = {
                "notes": _clean_queries(assess.get("refined_notes")),
                "doc":   _clean_queries(assess.get("refined_doc")),
                "web":   _clean_queries(assess.get("refined_web")),
            }
            cur_queries = {c: cur_queries.get(c, []) for c in cats}
            if not any(cur_queries.values()):
                break

        # ── Phase C — FINAL COLLECTIVE RANK ───────────────────────────────────────
        evidence = self._collective_rank(arm_results, queries, top_k)
        if live_fn and evidence:
            live_fn(f"[retrieve] {len(evidence)} cited across "
                    + ", ".join(sorted({r.category for r in evidence})))
        return GatherResult(
            context_understanding=understanding, evidence=evidence,
            capture_hires=capture_hires, queries=queries, iterations=iterations,
        )

    # ── knobs ─────────────────────────────────────────────────────────────────────

    def _iters(self, deep: bool) -> int:
        return _env_int("LK_RETRIEVAL_DEEP_ITERS", DEEP_ITERS) if deep \
            else _env_int("LK_RETRIEVAL_ITERS", DEF_ITERS)

    def _top_k(self, deep: bool) -> int:
        return _env_int("LK_RETRIEVAL_DEEP_TOPK", DEEP_TOP_K) if deep \
            else _env_int("LK_RETRIEVAL_TOP_K", DEF_TOP_K)

    def _fresh(self, deep: bool) -> int:
        return _env_int("LK_RETRIEVAL_DEEP_FRESH", DEEP_FRESH) if deep \
            else _env_int("LK_RETRIEVAL_FRESH", DEF_FRESH)

    def _depth(self) -> int:       return _env_int("LK_RETRIEVAL_DEPTH", DEF_DEPTH)
    def _min_results(self) -> int: return _env_int("LK_RETRIEVAL_MIN_RESULTS", DEF_MIN_RESULTS)
    def _assess_enabled(self) -> bool: return _env_flag("LK_RETRIEVAL_ASSESS", True)
    def _enforce(self) -> bool:    return _env_flag("LK_RETRIEVAL_ENFORCE", True)

    def _active_categories(self) -> list[str]:
        out: list[str] = []
        for c in _env_csv("LK_RETRIEVAL_CATEGORIES", CATEGORIES):
            if c == "notes" and self._memory is None:
                continue
            if c == "doc" and self._db is None:
                continue
            out.append(c)               # web is allowed even without a DB (fetch-only)
        return out

    @staticmethod
    def _default_priority(proactive: bool) -> int:
        try:
            from ..model import PRI_PROACTIVE, PRI_TURN
            return PRI_PROACTIVE if proactive else PRI_TURN
        except Exception:
            return 0

    # ── arms ────────────────────────────────────────────────────────────────────

    def _run_arm(self, category: str, queries: list[str], depth: int, fresh: int) -> list[_Candidate]:
        if category == "notes":
            return self._notes_round(queries, depth)
        if category == "doc":
            return self._doc_round(queries, depth)
        if category == "web":
            return self._web_round(queries, depth, fresh)
        return []

    def _notes_round(self, queries: list[str], depth: int) -> list[_Candidate]:
        """Notes arm = the agent's OWN memory. Each query goes through MemoryIndex.recall
        (itself a hybrid lexical+vector+graph+recency+link/delete chain), merged across
        queries by best rank position — the per-category chain is satisfied internally."""
        mem = self._memory
        if mem is None or not queries:
            return []
        best: dict[str, tuple[int, Any]] = {}
        for q in queries:
            try:
                res = mem.recall(q, k=depth)
            except Exception:
                continue
            for pos, r in enumerate(res):
                if r.node_id not in best or pos < best[r.node_id][0]:
                    best[r.node_id] = (pos, r)
        ranked = sorted(best.values(), key=lambda pr: (pr[0], -pr[1].score))
        out: list[_Candidate] = []
        for _pos, r in ranked[:depth]:
            out.append(_Candidate(
                key=f"memory://{r.node_id}", category="notes",
                title=r.title or r.source_kind, text=r.text, url=f"memory://{r.node_id}",
            ))
        return out

    def _doc_round(self, queries: list[str], depth: int) -> list[_Candidate]:
        """Doc arm = ingested local documents (file:// rows in the SemanticDB)."""
        db = self._db
        if db is None or not queries:
            return []
        raw: list[tuple[str, str, str]] = []
        for q in queries:
            try:
                hits = db.search(q, top_k=depth)
            except Exception:
                hits = []
            raw += [(h.url, h.title, h.text) for h in hits if _is_local(h.url)]
        return self._dedup_rank(raw, queries, category="doc", depth=depth)

    def _web_round(self, queries: list[str], depth: int, fresh: int) -> list[_Candidate]:
        """Web arm = cached web rows ∪ fresh search→read→extract for under-served
        queries (cached back into the SemanticDB). Reuses the D-19 provider chain."""
        queries = [q for q in (sanitize_web_query(q) for q in queries) if q]
        db = self._db
        raw: list[tuple[str, str, str]] = []
        hits_by_q: dict[str, int] = {}
        if db is not None:
            for q in queries:
                try:
                    hits = db.search(q, top_k=depth)
                except Exception:
                    hits = []
                web_hits = [h for h in hits if _is_web(h.url)]
                hits_by_q[q] = len(web_hits)
                raw += [(h.url, h.title, h.text) for h in web_hits]
        needs = [q for q in queries if hits_by_q.get(q, 0) < self._min_results()]
        if needs:
            try:
                from .web import search_and_fetch
                chunks = search_and_fetch(needs, max_per_query=fresh)
            except Exception:
                chunks = []
            if chunks and db is not None:
                by_url: dict[str, list[Any]] = {}
                for c in chunks:
                    by_url.setdefault(c.url, []).append(c)
                for url, cs in by_url.items():
                    try:
                        db.upsert(url, cs[0].title, [c.text for c in cs])
                    except Exception:
                        pass
            raw += [(c.url, c.title, c.text) for c in chunks]
        return self._dedup_rank(raw, queries, category="web", depth=depth)

    def _dedup_rank(self, raw: list[tuple[str, str, str]], queries: list[str], *,
                    category: str, depth: int) -> list[_Candidate]:
        """Collapse near-duplicate text, cap per URL, then BM25-rank within the arm."""
        seen_norm: set[str] = set()
        per_url: dict[str, int] = {}
        items: list[tuple[str, str, str]] = []
        for url, title, text in raw:
            norm = _norm_chunk(text)
            if not norm or norm in seen_norm:
                continue
            if per_url.get(url, 0) >= MAX_PER_URL:
                continue
            seen_norm.add(norm)
            per_url[url] = per_url.get(url, 0) + 1
            items.append((url, title, text))
        if not items:
            return []
        ranked = _bm25_rank(queries, [t for _, _, t in items])    # [(idx, score), …]
        out: list[_Candidate] = []
        for idx, _score in ranked[:depth]:
            url, title, text = items[idx]
            out.append(_Candidate(key=url, category=category, title=title, text=text, url=url))
        return out

    # ── final collective ranking ─────────────────────────────────────────────────

    def _collective_rank(self, arm_results: dict[str, list[_Candidate]],
                         queries: dict[str, list[str]], top_k: int) -> list[CitedResult]:
        """Fuse the per-arm rankings: RRF (scale-free cross-arm agreement) blended with
        a global BM25 score (lexical strength vs. the union of all queries)."""
        rankings = {c: [cand.key for cand in cands]
                    for c, cands in arm_results.items() if cands}
        if not rankings:
            return []
        fused = _rrf(rankings)

        by_key: dict[str, _Candidate] = {}
        for cands in arm_results.values():
            for cand in cands:
                by_key.setdefault(cand.key, cand)
        keys = list(by_key)

        all_q = [q for qs in queries.values() for q in qs]
        bm = {k: 0.0 for k in keys}
        if all_q:
            for idx, score in _bm25_rank(all_q, [by_key[k].text for k in keys]):
                bm[keys[idx]] = score
        mx = max(bm.values()) if bm else 0.0

        scored = sorted(
            keys,
            key=lambda k: fused.get(k, 0.0) * (1.0 + (bm[k] / mx if mx > 0 else 0.0)),
            reverse=True,
        )
        out: list[CitedResult] = []
        for num, k in enumerate(scored[:top_k], start=1):
            c = by_key[k]
            out.append(CitedResult(citation_num=num, url=c.url, title=c.title,
                                   text=c.text, category=c.category))
        return out

    # ── model passes (behind the `retrieve` role seam, I3) ───────────────────────

    def _call(self, system: str, body: str, schema: dict, *,
              priority: int, max_tokens: int, timeout: int,
              should_stop: Callable[[], bool] | None) -> dict | None:
        fn = self._call_fn
        if fn is None:
            try:
                from ..model import call_model
                fn = call_model
            except Exception:
                return None
        try:
            from ..kernel.invoke import _build_messages, _extract_json
            raw = fn(
                _build_messages(system, body, [], []),
                max_tokens=max_tokens, temperature=0.1, timeout=timeout,
                schema=schema, role="retrieve", priority=priority, should_stop=should_stop,
            )
            text = raw.get("text", "") if isinstance(raw, dict) else ""
            return _extract_json(text)
        except Exception:
            return None

    def _discern(self, need: str, short_ctx: str, long_ctx: str, proactive: bool,
                 priority: int, timeout: int,
                 should_stop: Callable[[], bool] | None) -> dict | None:
        parts: list[str] = []
        if short_ctx:
            parts.append("CURRENT CONTEXT (recent stream + summaries):\n" + short_ctx)
        if long_ctx:
            parts.append("RECALLED FROM MEMORY:\n" + long_ctx)
        if proactive:
            parts.append("NEED: (no explicit question — you are watching in the "
                         "background; decide what is worth looking into for the user "
                         "right now, if anything.)")
        else:
            parts.append(f"NEED: {need}")
        try:
            from ..kernel import prompts, schemas
        except Exception:
            return None
        return self._call(prompts.RETRIEVAL_PLAN, "\n\n".join(parts),
                          schemas.RETRIEVAL_PLAN, priority=priority,
                          max_tokens=512, timeout=timeout, should_stop=should_stop)

    def _assess(self, need: str, understanding: str,
                arm_results: dict[str, list[_Candidate]],
                priority: int, timeout: int,
                should_stop: Callable[[], bool] | None) -> dict | None:
        digest: list[str] = []
        for c, cands in arm_results.items():
            if not cands:
                digest.append(f"[{c}] (nothing found yet)")
                continue
            lines = [f"[{c}] {len(cands)} found:"]
            for cand in cands[:5]:
                snippet = " ".join((cand.text or "").split())[:160]
                lines.append(f"  - {cand.title}: {snippet}")
            digest.append("\n".join(lines))
        body = (f"NEED: {need}\nSITUATION: {understanding}\n\n"
                "EVIDENCE SO FAR:\n" + "\n".join(digest))
        try:
            from ..kernel import prompts, schemas
        except Exception:
            return None
        return self._call(prompts.RETRIEVAL_ASSESS, body, schemas.RETRIEVAL_ASSESS,
                          priority=priority, max_tokens=384, timeout=timeout,
                          should_stop=should_stop)
