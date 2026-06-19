# LAWRENCE — PLAN (possibility space)

> **SOUL** — canonical source **`docs/papers/LAWRENCE_v0_1_ieee.{tex,pdf}`**: local-first
> **watcher-assistant** (not a chatbot) — perceives continuously, turns activity into
> context, durable linked-Markdown memory, **recalls the right context on its own**
> (hybrid bundle: lexical+vector+graph+recency+thread+journal+web), parallel-facet
> kernel that answers now and keeps thinking; one replaceable LLM behind a gateway;
> litmus = *useful with the user unplugged an hour*; never a chat UI that staples a
> screenshot + keyword-searches the web.
>
> Companion: [DONE.md](DONE.md) (constraint surface). Produced under the Planning &
> TODO Consolidation Protocol. **The cross-partition edges are the primary
> deliverable.** Edge weights: `load-bearing` / `significant` / `incidental`.
> Status: `[ ]` open · `🔁` total rework (subsumes a DONE node). Supersedes
> `WORK_REMAINING.md` (deleted). Code is implementation truth.
>
> **CURRENT AUTHORITY (2026-06-18): §K.** The user confirmed the SOUL and directed
> a running end-to-end MVP. §K is the BUILD→AUDIT→REVISE overlay for that phase and
> supersedes the older executable-frontier recommendation in §G. Earlier nodes remain
> as implementation history and source constraints.
>
> **COMPLETED-WORK CONSOLIDATION (2026-06-19).** Every done node (`[x]` / SHIPPED:
> N-01,N-02,N-05,N-09,N-28 + §J + §K's N-34…N-44) is consolidated, compacted, and
> verification-graded in **[DONE.md](DONE.md) §0** (✅ gate+code verified this session ·
> ⚠ live-behavior documented but not re-run). PLAN.md keeps the as-built contracts
> **§J/§K** as authoritative reference (per the anti-drift rule — conception docs are
> not dismissed), and remains the home of the **open frontier**: the partial/open nodes
> (N-03,N-04,N-06,N-07,N-10,N-11,N-16,N-17,N-18,N-32,N-33,…) and the **§L next-horizon
> concepts** (N-45…N-50). Net done state + honest caveats: see the DONE.md §0 roll-up.

---

## §A — Triage (depth-scaling decision, auditable)

`centrality` = how much else hangs off it. `ambiguity` = how underspecified.
Depth: H-centrality(any) → **Full (§4 treatment)** · M/M → medium+deferral · M/L →
medium · L/* → one line + edges.

```
[N-01 EMB]    centrality:H ambiguity:M  → FULL    (gates all semantic work)
[N-02 RET]    centrality:H ambiguity:H  → FULL    (the core rework)
[N-03 WEB]    centrality:M ambiguity:M  → medium+deferral
[N-04 DOC]    centrality:M ambiguity:L  → medium
[N-05 LOOP]   centrality:H ambiguity:M  → FULL
[N-06 CTX]    centrality:H ambiguity:M  → FULL
[N-07 PRO]    centrality:H ambiguity:H  → FULL    (litmus; root cause unknown)
[N-08 SESS]   centrality:H ambiguity:M  → FULL
[N-09 U0]     centrality:H ambiguity:L  → FULL    (unblocks all UI)
[N-10 UA]     centrality:M ambiguity:L  → medium
[N-11 UB]     centrality:M ambiguity:M  → medium+deferral
[N-12 U6]     centrality:L ambiguity:L  → one line
[N-13 U7]     centrality:L ambiguity:M  → one line + note
[N-14 U8]     centrality:L ambiguity:L  → one line
[N-15 U4m]    centrality:L ambiguity:L  → one line
[N-16 ART]    centrality:M ambiguity:M  → medium+deferral
[N-17 WSK]    centrality:M ambiguity:L  → medium
[N-18 R1]     centrality:L ambiguity:M  → one line + conflict edge
[N-19 A1]     centrality:L ambiguity:M  → one line
[N-20 A2]     centrality:L ambiguity:L  → one line (may be done-by-existing)
[N-21 A3]     centrality:M ambiguity:M  → medium+deferral (enables N-07)
[N-22 A4]     centrality:L ambiguity:L  → one line
[N-23 R3]     centrality:L ambiguity:L  → one line
[N-24 HARNESS]centrality:M ambiguity:L  → medium (many incoming edges)
[N-25 WSX]    centrality:L ambiguity:H  → one line + note (strategic, deferred)
[N-26 WSH]    centrality:L ambiguity:M  → one line
[N-27 L1]     centrality:L ambiguity:L  → one line
[N-28 L2]     centrality:M ambiguity:M  → medium+deferral (user-requested)
[N-29 DOCS]   centrality:L ambiguity:L  → one line
[N-30 CARDS]  centrality:L ambiguity:L  → one line
```

---

## §B — §0 Conception-recovery reworks (highest priority)

### N-01 (EMB) — Embedding seam `[x]` — FULL — **DONE → DONE.md D-20**
**Pathway (DAG).** Hard-dep on D-17 (provider seam). Convergence point: feeds N-02
(vector arm), N-06/N-07/N-08 (semantic recall). Parallel-safe with all of §1.
**Triple-anchor.** *Task-local:* `embed(texts)->vectors` via the role seam. *Impl-
scope:* attachment point exists (`model.py` + llama-server `/embedding` or API
`/embeddings`); no embedding model wired today. *Soul:* precondition for "recall the
right context" — without meaning-vectors, recall stays keyword. **Coherent.**
**Deferral.** Hard-defer nothing. Re-entry: ready now; it is the unblocker for §0.
**Impl specifics.** Transport stdlib (`urllib`/existing client). Vectors → lazy
**numpy**; exact cosine over a packed normalized float32 matrix, **O(n·d)/query** (n
≤ ~10⁵ personal-scale → sub-ms to low-ms); **no ANN dep** (faiss/hnswlib) until n
forces it (I4). Trades: memory for the in-RAM matrix (n·d·4 bytes ≈ tens of MB) vs
query speed — fine at scale.
**Ambiguity register.** local embedding GGUF + dim `crystallizes-during` (record dim
in index schema). API embed routing `resolve-before-start` (route like background
roles, default local). Re-embed-on-model-swap `crystallizes-during`.

### N-02 (RET) — Hybrid retrieval engine 🔁 `[x]` — FULL — supersedes D-14 — DONE 2026-06-18 → D-24
> **DONE (own-memory hybrid recall).** `retrieval/memory.py` `MemoryIndex` + `reindex.py`:
> unified `source_kind` store, RRF fusion of lexical(FTS5)+vector(D-20)+graph(NoteStore),
> recency×link(G)×delete(P) shaping, local-first embed (degrades), `lk reindex`. The web
> arm stays in `SemanticDB` (fused later by N-03/N-05); the own-vs-web mix is N-05's call.
**Pathway (DAG).** Hard-deps: N-01 (vector arm), D-01 (L3/L2 sources), D-05 (journal),
D-08 (NoteStore graph arm + past chats). Soft-dep (informs): N-03 (web arm), N-04
(doc arm). **Diamond:** N-02 → {N-06, N-08} which must converge on the ambient-vs-
per-chat context split. Wrapped by N-05.
**Triple-anchor.** *Task-local:* one `retrieve(query)` returning a fused, provenance-
tagged bundle over own-memory + web. *Impl-scope:* `retrieval/pipeline.py` is BM25-
web-only; `db.py` is FTS5; NoteStore edges + journal/notes/L3 exist but are
**unindexed for retrieval**. The attachment points exist; the substance must be
rebuilt. *Soul:* this IS "recall the right context on its own" — the single highest-
soul-alignment task. **Coherent; D-14's assumption is the tension it resolves.**
**Deferral.** Hard-defer the vector arm until N-01; the lexical+graph+own-memory-
indexing arms can start immediately and already beat today's behavior. Re-entry:
N-01 done → full hybrid. This is the recommended first real build after N-01.
**Impl specifics.** Unified chunk+vector store (`source_kind`+provenance+blob).
Fusion = **Reciprocal Rank Fusion** across lexical(BM25)/vector(cosine)/graph(
neighborhood) rankings — parameterless, O(k log k); recency multiplier post-fusion
(reuse `_recency_factor`). Keep FTS5 for lexical, numpy for vector (N-01),
NoteStore for graph. `lk reindex` one-shot backfill + incremental on append. Trades:
index storage + embedding cost (background, droppable) vs recall quality.
**Ambiguity register.** Fusion algo `resolve-before-start` → RRF. Unified-vs-per-
store index `crystallizes-during` → single table w/ `source_kind`. Own-vs-web mix
per query `intentionally-open` → N-05 decides per step. Backfill scope
`crystallizes-during`.

### N-03 (WEB) — Web search & read rework `[~]` — medium + deferral — **folded as a category in D-26**
> **2026-06-18:** the web arm is now a category in the unified engine (D-26): cached web rows
> ∪ fresh search→read→extract (D-19 chain), BM25-ranked, cited consistently. Remaining: the
> single/deep/off *policy* surface (FR-003) is partly wired (`deep_search`); per-FR-003 web
> enforcement is on by default.
**Pathway.** Independent start; feeds N-02 web arm + N-05. Reuses D-19 chain/pacing/
cooldown.
**Achieves + alignment.** Real search→read→extract→**embed into N-02** (reusable,
cited), policy-gated (single/deep/off per FR-003); query formulation owned by N-05.
*Soul:* web becomes relevant evidence, not a keyword dump.
**Deferral.** Soft-defer the formulation half to N-05; the read/extract/embed half
ships independently and is valuable pre-loop. Re-entry: N-02 index schema exists.

### N-04 (DOC) — Document retrieval & conversion rework `[~]` — medium — subsumes §6 ingest — **doc arm shipped in D-26**
> **2026-06-18:** the doc *retrieval* arm is now a category in the unified engine (D-26):
> ingested `file://` chunks in `SemanticDB`, BM25-ranked, cited. Remaining: the conversion/
> ingest *write* path with path/page provenance (reuse D-16 converters) + the N-12 ingest
> button — i.e. getting more docs INTO the index; reading them back out is done.
**Pathway.** Hard-dep N-01 + N-02 index schema; reuses D-16 converters. Feeds N-02
doc arm. UI button = N-12 (separate).
**Achieves + alignment.** Converters → structural chunk → embed → index with
path/page provenance + citation (FR-005: typed/cited, not opaque blobs). *Soul:*
"doc search useless" was orphaned output; this re-homes it into recall.
**Deferral.** MUST-defer-until N-01+N-02 schema; one more source into the same index.

### N-05 (LOOP) — Agentic retriever loop 🔁 `[x]` — FULL — supersedes single-shot retrieve (FR-009) — **DONE 2026-06-18 → D-26**
> **DONE 2026-06-18 → D-26.** Shipped as the unified `RetrievalEngine` (per-category parallel
> chains + context-discernment-first + final collective RRF rank; perplexity default,
> configurable+dynamic). Folds N-03/N-04 in as categories, completes N-06's recall half (recall
> is now a cited category), and makes N-07 ride notes+doc+web. Full contract + granular steps
> RE-1…RE-13 in **§J**; `make check` green (32 suites, incl. `test_retrieval_engine.py`).
**Pathway (DAG).** Hard-deps: N-02, N-03. Reuses D-09 deadline machinery. Wraps
retrieval inside N-06 (turn) and N-07 (proactive). Convergence: every answer/finding's
grounding.
**Triple-anchor.** *Task-local:* bounded plan→retrieve→assess→refine→retry. *Impl-
scope:* today `analysis` emits keywords once → one `retrieve` → answer (`invoke.py`
run_turn). Attachment point = between analysis and response. *Soul:* "researches
until it has enough" vs "most-keyword-matching call" — the user's retriever complaint.
**Coherent.**
**Deferral.** Hard-defer until N-02 (and N-03 for web arm). Soft note: N-02 single-
shot is already a big win; the loop is increment 2. Re-entry: N-02 returns a usable
bundle.
**Impl specifics.** Orchestration over N-02; **bounded** (default 2 rounds + total
deadline via D-09's `TurnCancelled`); assess via N-02 fusion-score sufficiency + one
cheap model judgment (avoid per-source LLM grading). O(rounds·retrieve). stdlib.
**Ambiguity register.** Round budget `resolve-before-start` (default 2, deadline-
capped). Assess-by-score-vs-judgment `crystallizes-during`. Deep-search profile
`intentionally-open` (raises budget).

### N-06 (CTX) — Turn context assembly rework 🔁 `[~]` — FULL — supersedes screenshot-attach turn — RECALL HALF DONE → D-25/D-26
> **RECALL HALF DONE (D-25 core → D-26 unified).** `run_turn` first injected a `[RECALLED
> MEMORY]` block (D-25); D-26 then promoted recall to a **first-class cited category** inside
> the unified engine (own memory ranked + cited alongside doc/web in one bundle). **REMAINING
> (the perception half, independent of recall):** demote vision to distilled-secondary +
> on-request hi-res; audio transcript primary; recall/recency budget split tuning.
**Pathway (DAG).** Hard-dep N-02 (recall). Soft-dep D-18 (observers). Downstream:
every turn, N-07. **Diamond (not a cycle) `[revised: F3]`:** N-02 is the apex; it
feeds *both* N-06 and N-08, which must **converge once** on the ambient-vs-per-chat
context-split decision. This is a shared design decision resolved a single time, not
a mutual build-order dependency — neither blocks the other's start; they co-design
the split. (Build N-06's recall composition and N-08's session model against one
agreed split contract.)
**Triple-anchor.** *Task-local:* compose recall + recent-thread + current-context
distillation (app/window/time) + audio transcript + screen(secondary). *Impl-scope:*
`run_turn` uses `tail_for_model()` recency + maybe a screenshot; the rich
`TurnContextSnapshot` (interfaces.md) was never assembled. *Soul:* "context spanning
the past + audio + transcription"; "audio/text primary, vision secondary"
(ARCHITECTURE). **Coherent; directly resolves the user's #2 complaint.**
**Deferral.** Hard-defer the recall composition until N-02; the vision-demotion +
transcript-inclusion half (V3.T7/V3.T4) can land first and is independently valuable.
Re-entry: N-02 recall available.
**Impl specifics.** Rework `run_turn` context assembly: reserve a recall slice of the
dynamic working budget, fill remainder with recency; sticky summaries (keep D-06
fix); demote vision to distilled-secondary + on-request hi-res. One N-02 call/turn.
O(budget) assembly.
**Ambiguity register.** Recall/recency budget split `crystallizes-during` (tune by
tests). Current-context providers `resolve-before-start` (start with observer-
captured window+ts; reminder/calendar later). Per-chat split conflict with N-08
`resolve-before-start` (co-design).

### N-07 (PRO) — Proactive loop actually fires 🔁 `[~]` — FULL — re-opens D-13
> **2026-06-18 (D-26):** the "realize→retrieve→surface" quality half is in — `run_proactive`
> now rides the unified engine (findings grounded in own memory + doc + web, not web-only) and
> live-indexes each finding so the next pass sees what was surfaced. **REMAINING (the firing
> audit):** confirm the tick actually fires it under load (slot starvation / cadence) and route
> background off the starved local slot (N-21); the engine's plan/assess calls are droppable
> `PRI_PROACTIVE`, so de-starvation is the open risk to *firing* (vs. *quality*, now done).
**Pathway (DAG).** Hard-deps: D-03 (tick fires it), N-02 (relevant findings), N-06
(real "realize context"). Soft-dep N-21 (de-starve). Diamond: depends on both the
retrieval rework AND the de-starvation fix converging.
**Triple-anchor.** *Task-local:* the realize→retrieve→surface loop genuinely emits
useful unprompted findings. *Impl-scope:* D-13 added guards to a loop that may never
run; `run_proactive` exists but is `PRI_PROACTIVE` (droppable → skipped when the
slot is busy) and tick may be off/quiet. *Soul:* P2/P3 litmus — "unplug the user,
does it act?" Today ≈ nothing. **Out of alignment between impl (guards done) and soul
(behavior absent) — the named tension.**
**Deferral.** The **audit** (why inert) hard-defers nothing — do it first. The
**quality fix** soft-defers until N-02/N-06. Re-entry: instrumentation reveals the
root cause (config vs starvation).
**Impl specifics.** Add proactive-path tracing (tick on? slot busy? event present?
brief said surface?) → fix firing (tick defaults / route background off the starved
local slot via D-17 / event feed) → ensure findings ride N-02/N-06 → keep D-13
guards. O(1) overhead.
**Ambiguity register.** Root cause `resolve-before-start` (diagnose — likely both
config + starvation). Default cadence `crystallizes-during`.

### N-08 (SESS) — Chat session lifecycle 🔁 `[ ]` — FULL — supersedes D-08 bloat
**Pathway (DAG).** Hard-dep D-08 (CRUD + promote primitives). Soft-dep N-02 (recall
quality), D-05 (reuse WS-J for session journal). **Diamond off N-02 with N-06**
`[revised: F3]` (shared context-split decision, resolved once — co-design, not a
build-order cycle). Downstream: N-11 chat UI.
**Invariant guard `[revised: F4]`:** N-08 **does not delete D-08's append-only
durable transcript**. "Clear on new cycle" clears only the per-session *working
memory* (L1/L2) and resets the recall surface; `messages.jsonl` + the session's WS-J
summary persist and stay recallable/loadable. No conflict with D-08's append-only
invariant — the bloat being fixed is the unbounded *model-facing working stream*, not
the archive.
**Triple-anchor.** *Task-local:* dynamic session-boundary determination + new-session
init + clear-working-set-on-new-cycle + rolling [model-conducted] chat journal +
recall/review/restore/load-old/link. *Impl-scope:* `ensure_default()` = one Scratch
chat appended forever; the boundary/cycling mechanism the user described "got
skipped". CRUD + `promote_fn`/`ingest_summary` exist to build on. *Soul:* episodic,
reviewable, recallable memory vs an unbounded dump. **Coherent; resolves complaint
#3.**
**Deferral.** Hard-defer nothing for the boundary+clear+roll half (primitives exist);
soft-defer the recall-UI half to N-02/N-11. Re-entry: the bloat is live — do the
boundary half soon.
**Impl specifics.** Session-boundary policy (idle-gap OR day-rollover OR explicit) →
on new cycle: close+summarize via WS-J (D-05), promote to shared long-term
(`ingest_summary`), reset session working set → recall over `ChatStore.list/messages`
→ link via NoteStore edges. O(1)/turn boundary check; one WS-J call at rollover.
**Ambiguity register.** Boundary trigger `resolve-before-start` (idle/day/explicit
default). "Clear by default" vs durable transcript `resolve-before-start` (working
memory clears; transcript+journal persist). Chat-journal vs WS-J `resolve-before-
start` (reuse WS-J, scoped).

---

## §C — §1 WS-U UI redesign

### N-09 (U0) — UI seam (Track 0) `[x]` — FULL — **DONE 2026-06-18 → D-23**
**Done note.** Shipped exactly as planned: `web/lib/bridge.js` (sole transport) +
`web/variants/classic/app.js` (git-moved, imports transport) + `web/bootstrap.js`
(variant switch, classic fallback) + `ui_variant`/`LK_UI_VARIANT` config + `/health.
uiVariant`. Zero visual change, no Rust change. stress_ui section I + node --check on all
three entrypoints; `make check` green (30 suites). Markdown vendoring + `localDraft`
removal deliberately deferred to N-10. **Unblocks N-10/N-11/N-12/N-13/N-14/N-15.**
**Pathway (DAG).** No upstream **in the tracked done-graph** `[revised: F1]`. **Fan-out
convergence:** unblocks N-10, N-11, N-12, N-13, N-14, N-15 (all UI). The keystone of
the UI partition.
**Triple-anchor.** *Task-local:* `lib/bridge.js` (sole transport) + `bootstrap.js`
(variant switch, fallback to classic) + `ui_variant`. *Impl-scope:* extracts the
existing **`apps/desktop/web/app.js`** data layer — real prior art that predates this
tracker and is **not itself a D-node** (so N-09 shows zero incoming D-edges, but it is
not greenfield: the seam is a refactor of working code). No Rust change. *Soul:* "base
robust to the UI" — UI becomes replaceable like the model. **Coherent.**
**Deferral.** Hard-defer nothing; MUST precede every other UI node. Re-entry: ready.
**Impl specifics.** Native ES modules + `fetch`/`EventSource`; vendored markdown; 3
stress_ui seam assertions. O(1) indirection; one SSE parse point.
**Ambiguity register.** Markdown lib `crystallizes-during` (smallest CommonMark-safe).
`uiVariant` precedence `resolve-before-start` (config canonical, `/health` mirrors,
`?uiVariant=` dev-only).

### N-10 (UA) — Track A `classic` refactor `[ ]` — medium ↩ folds §5(D-11)
Hard-dep N-09. Drop `localDraft`, truthful toggles (from `/health`+SSE), vendored md,
config off the bar. Closes the popup half of D-11. Self-align: `grep -c localDraft`→0;
bridge-down ⇒ honest error. Deferral: MUST-defer-until N-09.

### N-11 (UB) — Track B `palette` variant `[ ]` — medium + deferral
Hard-dep N-09; soft-dep N-08 (renders sessions/recall/links). Command-palette overlay
(U1 geometry, ⌘K, settings window, U4 by turn-id, U5). Hosts N-12/13/14/15. Deferral:
MUST-defer-until N-09; CAN-defer-until after N-16 (functional UI ships on classic).
Ambiguity: magnetic panels (FR-010) `crystallizes-during` (in-app snapping first).

### N-12 (U6) — Ingest UI button `[ ]` — one line
Hard-dep N-09; real value needs N-04. "Save to KB" → status (FR-005 UI half).

### N-13 (U7) — Push-to-talk voice `[ ]` — one line + note
Hard-dep N-09; `POST /voice` exists. PTT button + transcript + `LK_DEBUG` fixture.
Coordinate with N-06 audio routing (FR-003). Ambiguity: live-mic verify
`crystallizes-during` (fixture passes in tests first).

### N-14 (U8) — Reminders panel/badge `[ ]` — one line ↩ folds §8(D-12)
Hard-dep N-09; backend D-12 done. Badge from `/health.reminders`; due event in feed.

### N-15 (U4m) — Capability markers in popup `[ ]` — one line ↩ folds §4(D-10)
Hard-dep N-09; buckets D-10 done. Render green/red/gray per control (launcher does).

---

## §D — §2/§3 feature engines

### N-16 (ART) — Artifact / deep-study engine (WS-A, §11) `[ ]` — medium + deferral
Hard-dep N-02 (grounding = own-memory + web), D-09 (cancel). `make(spec)->path` md-
first under `memory/vault/`, real citations or unsourced marks, provenance footer,
provider-blind (I3). Replaces dead `/context-pack/async`. Feeds N-24. Deferral:
hard-defer real grounding until N-02; a thin md version could ship on today's
retrieval but inherits its weakness. Re-entry: N-02 usable. Ambiguity: propose-then-
confirm `resolve-before-start`; kinds beyond md `crystallizes-during`.

### N-17 (WSK) — Capability routing layers 4–7 `[ ]` — medium ↩ extends D-10
Hard-dep D-10 (resolver/registry carry the data). L4 schema routing · L5 prefill
enforcement · L6 tools/MCP/skills + validated-JSON fallback · L7 probe→cache. L6
*execution* → N-25. Self-align: provider-shape in `model.py` (I3); tool config ≠
sampling; probe cache O(1). Deferral: MUST-defer-until nothing (L4/L5/L7); parallel-
safe; CAN-defer indefinitely.

---

## §E — §4 refinement streams (low-risk, parallel-safe)

### N-18 (R1) — `recent_findings` tail-read + store hot-path `[ ]` — one line + conflict edge
Hard-dep D-13 (behavior to preserve). **Conflict edge `--conditional--> N-02`
`[revised: F6 — resolved from ?:unresolved]`:** N-02's unified index will index
`kind="finding"` entries, so N-07's dedup can query N-02 instead of `recent_findings`
— which would make this tail-read **obsolete**. Resolution: **sequence N-18 after
N-02's index design crystallizes**; if N-02 subsumes findings recall, close N-18 as
done-by-N-02; otherwise do the O(limit) reverse scan vs O(layer), behavior-preserving
(keep `test_proactive_dedup` green). ⚠ modifies tested `ctx/store.py` (D-01 constraint).

### N-19 (A1) — Schema-repair pass `[ ]` — one line
Bounded repair before erroring; pairs with N-17 L4 + N-16. Default 1 attempt.

### N-20 (A2) — Proactive cooldown `[ ]` — one line (may be done-by-existing)
Pairs with N-07. ⚠ may already be covered by `LK_ELEVATE_MAX_PER_MIN` (D-04) — audit
first; may close as done-by-existing.

### N-21 (A3) — Background degrade / offload `[ ]` — medium + deferral — enables N-07
Hard-dep none (D-06 documents the starvation; D-17 provides offload routing). Graceful
shed/offload of starved background roles under turn-load. **Soft-dep edge → N-07**
(starvation is a prime inertness suspect). Deferral: MUST-defer-until nothing; do
alongside the N-07 audit. Re-entry: ready. Ambiguity: offload policy `crystallizes-
during` (reuse per-role routing matrix).

### N-22 (A4) — Turn deadline / watchdog `[ ]` — one line
Extend D-09 deadline coverage to remaining long ops; reuse `TurnCancelled`.

### N-23 (R3) — Schedule in-memory fold `[ ]` — one line
Dict `{id:state}` O(1)/op vs re-fold; durability unchanged (D-12 log is truth). Cheap.

---

## §F — §5/§6/§7 harness, strategic, hygiene

### N-24 (HARNESS) — Interleave & acceptance harness (§12) `[ ]` — medium
**Incoming (load-bearing):** N-16 (ingest→cite), N-02/N-04/N-07 (the scenario
exercises real recall/doc/proactive — passes only once those are real, not hollow).
The §14 goalpost. Deterministic stub-model 13-step session; exact event-count asserts.
Deferral: MUST-defer-until N-16 + the §0 reworks it checks. **Terminal node
`[revised: F5]`:** its completion unblocks nothing downstream — it *is* project
acceptance, the sink of the DAG. The "defer" rule (name what it unblocks) is satisfied
vacuously by being the goalpost, not hollow.

### N-25 (WSX) — Effectors / true agency `[ ]` 🔭 — one line + note (strategic)
Hard-dep N-17 L6 propose-path + a design+threat-model pass. Every effect user-
confirmed/audited. Deferral: MUST-defer-until L6 + design pass; strategic.

### N-26 (WSH) — Host-native UI (FR-011) `[ ]` — one line
Hard-dep N-09 seam (variant architecture is the enabler). Scaffolding in
`apps/desktop/host/windows/`. Strategic.

### N-27 (L1) — Tauri shell rebuild for live cancel `[ ]` — one line ↩ resume D-09
Rust `bridge_delete` exists; rebuild so UI Stop/Esc fire. Mechanical; I6. Anytime.

### N-28 (L2) — Launcher Quit & Quit-all `[x]` — DONE → DONE.md D-21 *(user 2026-06-17)*
**Triage note `[revised: F7]`:** true *centrality is L* (leaf — fan-out 0, nothing
waits on it); the medium depth is driven by *ambiguity M* (sudo escalation, verify
pass, "all relevant" scope) + explicit user priority, not by centrality.
**Pathway.** Hard-dep D-15 (registry + admission gate), D-07 (`stop --all` reaping).
**Leaf node `[revised: F5]`** — no downstream; "CAN-defer indefinitely" is honest
(nothing waits on it), not a hollow deferral — but it is small + user-requested, so
the recommendation is *do it early* despite being a leaf.
**Achieves + alignment.** Two front-view actions: **Quit** closes the launcher
interface ONLY (services keep running; deliberately redundant so "close launcher" ≠
"stop system"); **Quit-all** (dropdown, confirm-gated) force-terminates ALL
LAWRENCE processes (bridge, llama-server, observers, tick, hotkey helper, `lk_sensor`,
children), **escalating to sudo only per-process if one resists**, then **re-scans
and reports survivors**. *Soul:* an unambiguous, verified full-stop — the operational
counterpart to the warm-server design; a stuck/elevated process can't silently linger.
**Self-align.** Quit never signals a service; Quit-all always confirms. Thorough
(enumerate→SIGTERM→SIGKILL→re-scan→report). sudo only when needed, never blanket.
Never touch `.code-workspace`(I6)/secrets/`memory/`. Don't kill adjacent non-LAWRENCE
services (Ollama warning in desktop docs). Both GUI + console via `actions.py`.
**Deferral.** MUST-defer-until nothing (D-15 done). CAN-defer-until indefinitely, but
small + user-requested → good early win.
**Impl specifics.** stdlib `signal`/`os.kill`/`subprocess`(`pgrep`/`kill`);
O(#processes). `quit` (tier-1, handler closes window/console) + `quit_all` (tier-2
child, `confirm=True`, terminate-all + verify/escalate reusing `cmd_stop --all`).
**Ambiguity register.** "All relevant" scope `resolve-before-start` (canonical list,
confirm vs `ctl` process knowledge). sudo-on-WSL mechanism `crystallizes-during`
(no-password kill first; else emit exact command + Windows admin-kill note).

### N-29 (DOCS) — Documentation reconciliation `[ ]` — one line [revised stance]
**Partly done 2026-06-17:** the 14 drifted planning/conception docs were annotated
(origin + what-survives-where) and moved to **`docs/_archive/`** (staged for removal,
see `_archive/_ARCHIVE_INDEX.md`); SOUL re-anchored to the paper. **Remaining before
those archives can be deleted:** relocate the **I1–I9 invariants** + **Appendix A
(Anthropic backend facts)** out of the archived `IMPLEMENTATION_PLAN.md` into a live
home (e.g. `docs/INVARIANTS.md` or DONE.md preamble); fix README `crates/system-hooks/`
(absent dir). Opportunistic.

### N-30 (CARDS) — Telemetry / asset / panel cards `[ ]` — one line (FR-004/008/010)
FR-008 pairs with N-16; FR-010 folds into N-11; FR-004 rich telemetry into N-10/11 +
honest `/metrics`. Fold each into its parent; no standalone build.

### N-32 (LOCAL-PERF) — Local turn latency `[ ]` — medium *(finding from D-21, user "optimise for local")*
**Pathway.** Independent start; informs N-05 (loop budget) + N-06 (turn assembly).
**Finding (D-21).** Raw llama-server completes a tiny local completion in **~0.7s**,
but a full `run_turn` takes **minutes** on CPU — the cost is in the *pipeline*
(multiple model calls per turn: query/analysis/response/background) and the **gemma
thinking-token burn** (see [[lawrence-thinking-token-budget]]), NOT the server. So
the local spine *works* but isn't yet *usable-fast*.
**Achieves + alignment.** Make a local turn responsive: audit per-turn model-call
count + token ceilings; expose/right-size `LK_THINKING` and per-role `max_tokens`;
consider a smaller/faster local default + GPU offload (`LLAMACPP_GPU_LAYERS`); keep
the degraded-path doctrine (never hang the turn). *Soul:* "the whole system had to
be optimised for local" — a watcher-assistant that takes minutes to answer fails the
responsiveness bar even when fully local.
**Ambiguity register.** thinking on/off vs budget `resolve-before-start` (measure
first — disabling may regress quality per the thinking-budget memory). Smaller local
model `intentionally-open` (user hardware call). Per-role ceilings `crystallizes-during`.

### N-33 (SENSOR-DECOUPLE) — Sensors as independent services; model probes `[~]` — FULL *(user 2026-06-17)*
**Principle (user directive).** **Decouple the sensor from the model.** Each sensor
(vision, audio) is a *separate, individual, always-on service* that keeps running and
*proceeds with the data on its own* — capture → OCR/transcription → logging → context
write → extraction → context tracking → dynamic/smart adaptation to environment change
— **independent of the model**. The model never drives sensor lifecycle; it only
**probes** the accumulated sensor data to retrieve what's relevant. **Only the USER
turns a sensor off** (UI toggle · `/vision on|off` · config). The model may relay an
"off" *only* when a proactive / voice-query / active user-query explicitly asks for it.
**Pathway (DAG).** Step 1 done (D-22: model→sensor control severed; auto-start at boot
= D-21). Remaining hard-deps: **N-02** (the "probe" = hybrid retrieval over sensor-
derived context), **N-06** (assemble probed context into the turn), **N-07** (proactive
off the stream). Reuses D-18 (observers), D-02 (extraction), D-03 (tick/significance).
**Triple-anchor.** *Task-local:* sensors run as services; model calls `retrieve()` to
pull relevant perceived data; no per-turn device control. *Impl-scope:* observers
(D-18) already capture→OCR/transcribe→write context continuously and now auto-start
(D-21); the missing half is making the model *consume by probing* (N-02/N-06) instead
of by toggling, and making proactive ride the stream (N-07). *Soul:* the watcher-
assistant perceives continuously and recalls/acts on it — "audio/text primary, vision
secondary"; useful with the user unplugged. **Coherent — this is the umbrella the
perception reworks serve.**
**Proactive extrapolation (explicit ask).** Apply the same decoupling to N-07: the
proactive loop must observe the *continuously-updated* context stream — significance/
change-detection on the latest OCR/transcript (D-03 + vision region-change gating) —
and on a meaningful change, **probe** (N-02) + surface a finding, all WITHOUT the
model toggling sensors. Sensors push; tick watches for change; model pulls on a
worthwhile delta. Firing is driven by environment change, not by the model asking a
sensor to turn on.
**Deferral.** Step 1 (decouple control) done now. The probe/assembly/proactive halves
defer to N-02 → N-06 → N-07. The "model relays an explicit user OFF" case needs an
intent-aware path (a real effector/command channel, not the per-turn envelope) —
deferred (relates to N-25 effectors).
**Ambiguity register.** "probe" granularity (latest-frame vs windowed transcript vs
retrieval) `resolve-during` N-02. Change-detection thresholds for proactive
`crystallizes-during` N-07. Explicit-user-off intent path `resolve-before-start` of
that sub-task (N-25-adjacent).

---

## §G — N→N edge set (the execution DAG, beyond the cross-partition edges in DONE.md)

```
N-01 --dependency--> N-02            load-bearing  vector arm; break: no semantic recall
N-02 --dependency--> N-06            load-bearing  recall composed into the turn
N-02 --dependency--> N-07            load-bearing  relevant findings
N-02 --dependency--> N-05            load-bearing  the loop retrieves via N-02
N-02 --dependency--> N-16            significant   artifact grounding
N-02 --dependency--> N-08            significant   session recall quality
N-03 --dependency--> N-05            significant   web arm of the loop
N-03 --dependency--> N-02            significant   web is one source in the bundle
N-04 --dependency--> N-02            significant   docs are one source in the bundle
N-05 --wraps-------> N-06            load-bearing  turn retrieval = the loop
N-05 --wraps-------> N-07            significant   proactive retrieval = the loop
N-06 --dependency--> N-07            load-bearing  "realize context" must be real
N-02 --diamond----> {N-06,N-08}      significant   apex; both consume recall, converge
                                                   ONCE on the context-split decision
                                                   (co-design, NOT a build cycle) [rev:F3]
N-21 --dependency--> N-07            significant   de-starvation enables firing
N-09 --dependency--> {N-10,N-11,N-12,N-13,N-14,N-15}  load-bearing  UI seam unblocks all
N-08 --dependency--> N-11            significant   palette renders sessions/recall
N-16 --dependency--> N-24            load-bearing  ingest→cite acceptance step
N-02 --dependency--> N-24            load-bearing  recall scenario must be real
N-07 --dependency--> N-24            load-bearing  proactive scenario must be real
N-17 --dependency--> N-25            load-bearing  L6 propose-path precedes effectors
N-09 --dependency--> N-26            load-bearing  variant seam enables host-native
N-18 --conditional-> N-02            significant   N-02 may subsume recent_findings →
                                                   sequence after N-02 design [rev:F6]
# sensor-decoupling umbrella [user 2026-06-17]
N-33 --requires----> N-02            load-bearing  "model probes sensor data" = retrieval
N-33 --requires----> N-06            load-bearing  probed perception composed into the turn
N-33 --requires----> N-07            load-bearing  proactive rides the continuous stream
D-18/D-02/D-03 --feed--> N-33        load-bearing  observers/extraction/tick = the services
D-22 --partial-completion--> N-33    load-bearing  step 1 (model→sensor control severed) done
# cross-partition backend edges for the UI-folded nodes [revised: F2]
D-19/D-16 --dependency--> N-12        significant   /ingest + converters back the button
D-18(/voice) --dependency--> N-13     significant   voice endpoint backs PTT
```

**Superseded executable frontier (historical; replaced by §K):**
~~N-01~~ **(done → D-20)**, ~~N-28~~ **(done → D-21)**, **N-02** (unblocked — hard-dep
N-01 satisfied), N-03 (read/extract half), N-09, N-21, N-27, N-29, **N-32** (new:
local turn latency). **User-set order (2026-06-17):** (1) ✅ make the existing
launcher/kernel/server work as envisioned — DONE (D-21: local-first default, launcher
opens, sensors auto-start, Quit/Quit-all, logs viewable); (2) the *existing* UI
revision next → **N-09 (UI seam) → N-10 (classic) / N-11 (palette)**; (3) then
iterative improvements (incl. **N-32** local latency, **N-02** retrieval); (4) new UI
later. So the recommended next pick is **N-09** (then N-10/N-11), with N-32 and N-02
as the high-value iterative wins after the UI revision lands.

---

## §H — Stage-2 AUDIT findings (embedded; part of the deliverable)

Re-read of the committed Stage-1 skeleton against the protocol invariants. **Not
clean** — 7 findings, all addressed in §I.

**Structural.**
- **A1 N-nodes w/ zero incoming D-edges:** N-09,N-12,N-13,N-16,N-19,N-20,N-24,N-25,
  N-26,N-29,N-30. Genuinely independent of the *tracked* done-graph: N-19,N-24,N-25,
  N-29,N-30. **F1:** N-09/N-26 lean on existing `app.js`/host scaffolding (real prior
  art, not a D-node) → noted, they're refactors not greenfield. **F2:** missing
  index edges D-09→N-16, D-04→N-20, and backend edges D-19/D-16→N-12, D-18→N-13.
- **A2 D-nodes w/ zero outflow:** none — every done item has a live stub (expected
  mid-stream). Clean + explained.
- **A3 cycles:** none real. **F3:** `N-06<->N-08` bidirectional notation misread as a
  2-cycle → re-expressed as a diamond off N-02 (converge once, co-design).
- **A4 diamonds:** N-02→{N-06,N-08} marked; turn-convergence (N-05 wraps N-06→N-07)
  named.

**Alignment.**
- **A5 top-3 centrality (N-02,N-09,N-06) triple-anchor:** coherent. N-09's impl-scope
  anchor softened by F1 (app.js prior art).
- **A6 baked-assumption conflicts:** D-14↔N-02, D-18↔N-06, D-13↔N-07 are intentional
  supersessions (marked). **F4:** D-08↔N-08 is NOT a conflict (different stores) →
  stated explicitly so N-08 isn't read as deleting transcripts.

**Edge integrity.**
- **A7 deferrals unblocking nothing:** **F5:** N-24 (acceptance sink) + N-28 (user
  leaf) marked terminal/leaf — honest, not hollow.
- **A8 load-bearing endpoints:** all exist, break conditions testable (spot-checked
  D-14→N-02, D-03→N-07, D-08→N-08, D-09→N-27). Clean.
- **A9 `?:unresolved`:** **F6:** N-18→N-02 resolved to `conditional` (sequence after
  N-02 design; may close obsolete).
- **A10 depth-scaling:** **F7:** N-28 centrality is really L (leaf); its M-depth is
  ambiguity-driven (sudo/verify/scope) + user priority — noted.

## §I — Stage-3 revision log

| Finding | Fix | Where |
|---|---|---|
| F1 | N-09/N-26 lean on existing app.js/host scaffolding (prior art, not a D-node; refactor not greenfield) | N-09 body; DONE.md live-stub note |
| F2 | drew edges D-09→N-16, D-04→N-20, D-19/D-16→N-12, D-18→N-13 | DONE.md D-04/D-09 + index; §G |
| F3 | N-06↔N-08 re-expressed as a diamond off N-02 (converge once, no build cycle) | N-06, N-08, §G |
| F4 | stated N-08 does not delete D-08's durable transcript (clears working set only) | N-08 invariant guard; DONE.md D-08 |
| F5 | marked N-24 terminal (acceptance sink) + N-28 leaf | N-24, N-28 |
| F6 | N-18→N-02 resolved `?:unresolved`→`conditional` (sequence after N-02 design) | N-18, §G |
| F7 | noted N-28 true centrality L; depth driven by ambiguity + user priority | N-28 triage note |

**Carried audit items:**
- **`[resolved → D-32/D-38]` N-07 root cause** — cooldown clocks previously advanced
  on skipped work; successful-work commit plus the unattended hour resolves it.
- **`?:open` N-02 vs N-18 subsumption** — whether the unified index subsumes
  `recent_findings` resolves when N-02's index schema is designed; N-18 is sequenced
  to wait on it.
- **`[resolved]` SOUL confirmation** — the SOUL statement is synthesized from the corpus
  (AUTONOMY §0/§1, ARCHITECTURE). **Resolved 2026-06-18: user confirmed it.**

---

## §J — Unified Perplexity Retrieval Engine + autonomy-loop closure — **SHIPPED 2026-06-18 → D-26** ✅

> **STATUS: SHIPPED.** All of RE-1…RE-13 below are done; `make check` green (32 suites incl.
> `test_retrieval_engine.py`). Recorded as DONE.md **D-26**; N-05 `[x]`, N-03/N-04/N-06/N-07
> advanced. The contract/architecture below is kept as the as-built reference.

> **User directive (this session).** *"Get the system to work autonomously; make it
> capable of capturing running long contexts; write atomic logs; context-adaptive
> journal entries; tiered rolling memory with compaction and compression smartly to
> context; web/doc/notes retrieval — like perplexity — enforced, reranked, iterative,
> consistent citation, context (short & long) based."*
>
> This section is the **authoritative build contract** for that directive. It realizes
> **N-05 (LOOP)** as the spine and folds in **N-03 (WEB)**, **N-04 (DOC)** as
> retrieval *categories*, finishes the recall half of **N-06 (CTX)**, makes **N-07
> (PRO)** ride it, and closes the live **N-02→N-06→N-07** loop. Treatment depth: FULL.

### §J.0 — Directive coverage audit (what exists vs. what this build adds)

| Directive clause | State at audit (2026-06-18) | This build |
|---|---|---|
| work **autonomously** | tick + proactive wired in both kernels (D-03); `run_proactive` rides **web only**, findings/journal **not** re-indexed → recall goes stale | proactive rides the unified engine; **live incremental indexing** closes perceive→remember→recall→act |
| **long context** capture | `ContextStore` dynamic-budget L1→L2→L3 tiering solid (D-01) | unchanged; recall now spans it |
| **atomic logs** | `context-YYYY-MM-DD.log` one-liner-per-event exists (D-01) | unchanged; already indexed by reindex |
| **context-adaptive journal** | WS-J engine: significance-gated, first-person, rolling-revision (D-05) | new entries **incrementally indexed** into recall |
| **tiered rolling memory + compaction/compression** | model compaction L1→L2→L3 + dynamic working budget solid (D-01) | unchanged |
| **web/doc/notes retrieval — perplexity** | `RetrievalPipeline` is **single-shot, web/doc-only, gated, non-iterative**; notes recall is a *separate* block; citations don't span memory | **the centerpiece** — the new `RetrievalEngine` below |

### §J.1 — Decisions locked (2026-06-18 AskUserQuestion)

- **D1 — depth.** Default = a faithful **Perplexity design**: context-grounded, retrieval
  **enforced** once warranted, **reranked**, **iterative**. Make it **configurable +
  dynamic**: simple needs terminate after one round, complex needs iterate deeper; every
  bound is a knob.
- **D2 — fusion shape.** Each **category** (notes / doc / web) runs the **whole chain
  independently and in parallel** — *parse → retrieve → rank → iterate* on its own —
  then a **final collective ranking phase** fuses them. **Precondition:** a
  **context-discernment pass** runs first — the model drafts its understanding of the
  *current* situation (the "Raw/draft"), and **only from that correct context can it
  produce the correct retrieval** queries. ("Context (short & long) based" = the discern
  pass is fed the short rolling tail **and** the long summary/recall digest.)
- **D3 — categories + citations.** Categories: **notes** (own memory — hybrid via
  `MemoryIndex`, N-02), **doc** (local ingested `file://` chunks in `SemanticDB`, N-04),
  **web** (search→read→extract→store, N-03). One **consistent citation space** across all
  three (memory is cited like any source, `memory://<node_id>`).
- **D4 — local-first ([[lawrence-local-first]]).** The discern/assess/refine model calls
  run under a new role **`retrieve`** that is **NOT** in `BACKGROUND_ROLES` → defaults to
  the **local** backend (planning over personal context never ships to cloud by default;
  API still opt-in via `routing.retrieve`). Notes arm embeds locally. No embedding/web
  backend ⇒ the affected arm is **skipped**, never fatal (degrade to what is available).

### §J.2 — Architecture: `retrieval/engine.py :: RetrievalEngine`

```
gather(need, *, short_ctx, long_ctx="", proactive=False, priority, timeout,
       should_stop, live_fn) -> GatherResult
GatherResult(context_understanding: str, evidence: list[CitedResult],
             capture_hires: bool, queries: dict[str,list[str]], iterations: int)
```

- **Phase A — DISCERN (1 model call, role=`retrieve`, schema `RETRIEVAL_PLAN`).** Input =
  short_ctx (rolling tail = recent raw + sticky L2/L3 summaries) + long_ctx (a recall
  digest from `MemoryIndex` + journal) + the need (user question, or "" for proactive →
  prompt framed as "what is worth looking into"). Output = `context_understanding`
  (the Raw/draft), per-category query lists (`notes_queries`/`doc_queries`/`web_queries`),
  `needs_retrieval`, `capture_hires`. **Degrade:** model down/empty → heuristic token
  queries from the need (lexical), so retrieval still runs.
- **Phase B — per-category PARALLEL chains (`ThreadPoolExecutor`, one worker/arm).** Each
  arm runs ≤ `max_iter` rounds: `retrieve(queries, depth) → rank-within-arm → sufficiency`.
  - **notes arm** = `MemoryIndex.recall` per query, merged by `node_id` keeping best rank
    (recall is itself hybrid lexical+vector+graph+recency+link/delete — the per-category
    "chain" is satisfied internally).
  - **web arm** = `SemanticDB.search` (non-`file://` rows) ∪ `search_and_fetch` for
    under-served queries → store new chunks → dedup/cap per URL → BM25 rank.
  - **doc arm** = `SemanticDB.search` filtered to `file://` rows → BM25 rank.
  - **iterate (dynamic):** after a round, an arm under its `min_results` floor (and with
    rounds left) gets **refined queries** from a single shared **ASSESS call** (role
    `retrieve`, schema `RETRIEVAL_ASSESS`, one call covers all arms → returns
    `sufficient` + per-arm `refined_*`). Assessor off (`retrieval_assess=0`) or
    `max_iter=1` ⇒ single-shot per arm. The model's `sufficient` verdict is the dynamic
    stop; `max_iter` + `timeout`/`should_stop` (reuse `TurnCancelled`, D-09) are the hard caps.
- **Phase C — FINAL COLLECTIVE RANK.** **RRF** across the per-arm ranked id-lists
  (parameterless, scale-free; reuse `memory._rrf`) **× a global BM25 blend** of each
  candidate's text vs. the union of all queries (rewards cross-arm agreement *and*
  lexical strength) → dedup by key → assign citation numbers in fused order → top
  `retrieval_top_k`. Returns unified `CitedResult`s tagged with `category`.
- **Invariants.** stdlib core, heavy deps lazy (I4); all model selection behind the
  `retrieve` role (I3); never raises (every phase degrades); web pacing/cooldown reused
  from D-19; no new on-disk store (reuses `SemanticDB` + `MemoryIndex`).

### §J.3 — Granular step-by-step build (RE-1 … RE-13)

**Seams (small, low-risk edits first):**
- **RE-1 — `retrieval/pipeline.py`:** add `category: str = "web"` to `CitedResult`
  (defaulted → positional callers + tests unaffected). Make `format_snippets` /
  `format_for_model` / `format_citations` **category-aware**: tag each item `(notes|doc|
  web)`; render a clickable link only for `http(s)://`/`file://` (notes `memory://` shows
  `(memory)` text, no link). Keep the substrings existing tests assert (`previews`,
  `URL`, `[1]`).
- **RE-2 — `kernel/schemas.py`:** add `RETRIEVAL_PLAN`
  (`context_understanding`, `needs_retrieval`*, `notes_queries[]`, `doc_queries[]`,
  `web_queries[]`, `capture_hires`) and `RETRIEVAL_ASSESS` (`sufficient`*,
  `refined_notes[]`, `refined_doc[]`, `refined_web[]`). `additionalProperties:false`,
  minimal required sets (the schema discipline in the module docstring).
- **RE-3 — `kernel/prompts.py`:** add `RETRIEVAL_PLAN` prompt (discern current situation
  → per-category, *adjacent/complementary* queries; proactive framing when no question)
  and `RETRIEVAL_ASSESS` prompt (judge sufficiency of gathered evidence; emit refined
  per-category queries only for gaps).
- **RE-4 — `config.py`:** add `_ENV_MAP` knobs → `LK_RETRIEVAL_*`: `retrieval_enabled`,
  `retrieval_enforce`, `retrieval_iters` (default 2), `retrieval_assess` (model assessor
  on/off), `retrieval_top_k`, `retrieval_min_results`, `retrieval_depth`,
  `retrieval_categories` (csv: `notes,doc,web`). Round-trip via `lk config`/GUI.
- **RE-5 — `model.py`:** add `"retrieve"` to `ALL_ROLES` (NOT `BACKGROUND_ROLES`) so
  presets cover it and it defaults local; `_routing.get("retrieve") or _backend` already
  resolves it with zero further change.

**Core engine:**
- **RE-6 — `retrieval/engine.py` (NEW):** `RetrievalEngine`, `GatherResult`, internal
  `_Candidate`; Phases A/B/C as in §J.2; the three arm runners; `_rrf` reuse + global
  BM25 blend; heuristic-query + per-arm + whole-engine degrade paths; live-patchable
  knobs read from env each call (so `/set` works without restart).
- **RE-7 — `retrieval/__init__.py`:** export `RetrievalEngine`, `GatherResult`.

**Test gate:**
- **RE-8 — `tests/test_retrieval_engine.py` (NEW, offline, deterministic):** stub model
  (`call_model` monkeypatched to emit canned PLAN/ASSESS JSON) + stub arms (in-mem
  `MemoryIndex` with the bag-of-words embed from `test_memory_index.py`; a fake
  `SemanticDB`; web fetch stubbed). Assert: (a) discern produces per-category queries;
  (b) arms run independently and a single-arm failure is isolated; (c) the iterative
  refine path fires when an arm is under `min_results` and `sufficient=false`, and stops
  on `sufficient=true`/`max_iter`; (d) final RRF orders a cross-arm-agreed candidate
  first; (e) citations are one consistent 1..N space spanning categories; (f) degrade
  with no model (heuristic queries) and with no web/embed (arm skipped). Wire into
  `scripts/check.sh` + `Makefile`.

**Wiring + autonomy-loop closure:**
- **RE-9 — `kernel/invoke.py` `run_turn`:** add `engine: RetrievalEngine | None`. When
  present, replace the separate analysis+retrieve+recall blocks with **one**
  `engine.gather(user_text, short_ctx=ctx_tail, long_ctx=<recall digest>)`; feed
  `context_understanding`→`[SITUATION]`, the unified `evidence`→snippet/expand/citation
  path (works unchanged — `evidence` is `list[CitedResult]`). `engine=None` ⇒ today's
  behavior (back-compat / tests). Honor `capture_hires`.
- **RE-10 — `kernel/invoke.py` `run_proactive`:** accept `engine` + `memory`; when
  present, `engine.gather(need="", short_ctx=tail, proactive=True,
  priority=PRI_PROACTIVE)` → brief over the unified bundle → findings ride notes+web+doc.
- **RE-11 — live incremental indexing (close N-02→N-06→N-07):** index fresh own-memory so
  recall/proactive don't go stale mid-session — `run_turn` upserts the completed turn
  (`memory.upsert(turn_id,"turn",…,embed=False)`); `run_proactive` upserts each finding;
  `kernel/journal.run_journal` upserts each new entry (thread `memory` through
  `JournalTrigger`). `embed=False` live (lexical+graph instant); embeddings backfilled by
  the background pass / `lk reindex`.
- **RE-12 — construct the engine in BOTH kernels:** `cli.py` (REPL) and
  `apps/desktop/scripts/ui_bridge.py` build `RetrievalEngine(db=<SemanticDB>,
  memory=self.memory)` and pass it to `run_turn`/`run_proactive`; wire `memory` into the
  `JournalTrigger`.

**Gate + docs:**
- **RE-13 — `make check` green; record `DONE.md` D-26 (engine), update D-24/D-25 stubs;
  mark N-05 `[x]`, N-03/N-04 advanced, N-06 recall-half `[x]`, N-07 `[~]`/`[x]` per
  result; update memory ([[lawrence-autonomous-spine-decision]], [[lawrence-work-tracker]]).**

### §J.4 — Out of scope here (tracked, deferred)
- **Vision demotion** (N-06's other half — distilled-secondary + on-request hi-res) is
  independent of recall and lands as a follow-up.
- **Doc ingest UI button** (N-12) and **deep-study artifacts** (N-16) consume this engine
  later; not in this build.
- **N-32 (local turn latency)** runs in parallel — the engine adds ≤2 model calls/turn by
  default (discern + at most one assess), all `retrieve`-role-routable to a faster backend
  and all `should_stop`/deadline-bounded; the iteration cap is the latency lever.

### §J.5 — Acceptance (litmus)
- Offline gate green incl. `test_retrieval_engine.py`.
- A turn's answer is grounded in a **single cited bundle spanning notes+web+doc**, the
  model citing memory like a source.
- With the user idle, the proactive loop surfaces a finding **grounded in own memory +
  web** (not web-only), and that finding + journal + turns are **recallable within the
  same session** (live indexing) — i.e. *useful with the user unplugged an hour*.

### §J.6 — Desktop contract alignment (`apps/desktop/*.md|mdx`, reviewed 2026-06-18)
The desktop feature-request docs pin down what "enforced / perplexity-style" must mean at
the bridge boundary. The engine is built to satisfy them (UI rendering stays N-10/N-11):
- **"Enforced" = no classifier gate (FR-003 + README L200).** *"Web search is on by
  default; every turn sends a single-pass web/retrieval request when web is enabled,
  regardless of the prompt."* So `retrieval_enforce` (default **on**) means **every
  enabled category runs every turn** — the DISCERN pass supplies the `context_understanding`
  + queries, but its `needs_retrieval=false` may only suppress *non-enforced* categories;
  an enforced category (web by default) always runs. (Config can disable a category
  entirely; that is the only "off".)
- **Deep-research per-turn (FR `Deep Web Search Turn Flag`; README magnifier).** Bridge
  sends `config.deepSearch:true` → `gather(deep=True)` raises the per-turn profile
  (`searchDepth=comprehensive`, `freshPerQuery≈8`, `topK≈18`, `expandSources=true`,
  `requireCitations=true`, higher `max_iter`) **without mutating global defaults**. Map:
  `deepSearch → RetrievalEngine deep profile`. Knobs: `LK_RETRIEVAL_DEEP_ITERS`,
  `LK_RETRIEVAL_DEEP_TOPK`, `LK_RETRIEVAL_DEEP_FRESH`.
- **Visible progress (FR-003/004).** `gather` emits `live_fn` events per category
  (`[retrieve] web: N sources`, `deep-search: N sources considered`) so the bridge can
  stream them as SSE — long retrieval never waits for turn completion.
- **Typed evidence cards (FR-008).** The unified `CitedResult` bundle maps 1:1 to typed
  `assets` (`{id:"src-N", kind:category, title, url, snippet:text, usedBy}`) — add an
  `evidence_assets(results)` helper so the bridge can push `assets` (scrollable Perplexity
  cards) instead of scraping Markdown links. Engine produces the data now; card rendering
  is N-10/N-11.
- **Managed quality loop (FR-009).** The DISCERN→retrieve→**ASSESS**→refine→retry loop
  with `max_iter`/`toolRounds` caps **is** FR-009's "validate retrieval/tool relevance →
  refine query → retry within toolRounds" half (the format-repair half already lives in
  `invoke._fallback_response` + schema fallback). `agent.toolRounds`/`toolCallLimit` from
  the UI map onto `retrieval_iters`.
- **Unsupported-state honesty (FR `deepSearch`; G5).** If no web backend can browse, the
  web arm is skipped and a structured note surfaces (reuse `web.search_stats()`), never a
  silent empty pass.

---

## §K — Running end-to-end MVP consolidation (authoritative)

### §K.0 — Confirmed MVP boundary

**SOUL:** LAWRENCE is a local-first watcher-assistant that continuously perceives
the user's environment, converts transient activity into inspectable durable
memory, autonomously recalls relevant context, and acts or surfaces useful findings
without waiting for a prompt. The replaceable LLM is one reasoning component;
orchestration, memory, privacy, and continuity are the product.

For this phase, **cloud-first generation is intentional until the MVP works**, but
the implementation must preserve zero-shot/random-turn llama.cpp compatibility.
Cloud-first does not authorize cloud-only state, hidden raw-data upload, or
provider-specific orchestration.

### §K.1 — Stage 1 BUILD artifact

#### Triage

```
[N-34 BOOT]   centrality:H ambiguity:M  → FULL  reproducible running baseline
[N-35 SENSE]  centrality:H ambiguity:H  → FULL  independent adaptive sensors
[N-36 SNAP]   centrality:H ambiguity:H  → FULL  frozen dynamic context
[N-37 KV]     centrality:M ambiguity:H  → medium+deferral  durable llama.cpp KV
[N-38 RETEST] centrality:H ambiguity:M  → FULL  retrieval evidence quality
[N-39 AUTO]   centrality:H ambiguity:H  → FULL  unplugged-user autonomy
[N-40 UI]     centrality:M ambiguity:M  → medium+deferral  truthful classic UI
[N-41 AGENCY] centrality:H ambiguity:H  → FULL  confirmed effectors
[N-42 LOCAL]  centrality:H ambiguity:M  → FULL  random-turn local compatibility
[N-43 POLICY] centrality:H ambiguity:M  → FULL  privacy and trust boundaries
[N-44 ACCEPT] centrality:H ambiguity:L  → FULL  terminal MVP acceptance
```

#### ~~N-34 (BOOT) — Reproducible cloud-first runtime baseline~~ `✅ → D-28`

**Pathway.** D-27 is the hard input. Start bridge/kernel with Gemini routing,
prove writer ownership, observers/tick/journal startup, startup memory backfill,
one typed turn, one indexed turn, and clean shutdown. This is the convergence point
for configuration truth, process ownership, and runtime observability; N-35/N-38/
N-39/N-40/N-42 all consume it. N-39 and N-40 are now complete.

**Triple-anchor.** *Task-local:* one command starts a known-good system and a status
surface explains every degraded branch. *Implementation-scope:* `lk`, `desktopctl`,
bridge health, doctor, logs, writer lock, and backfill already exist but currently
do not prove a populated recall index or working full retrieval. *Soul:* autonomy
cannot be evaluated on a stopped or ambiguously configured stack. **Coherent.**

**Deferral.** Hard-defer none. It is the first executable node. Re-entry: immediate.

**Implementation specifics.** Keep current Gemini routing. Add a non-destructive
`lk mvp-smoke` or equivalent composed check using existing stdlib HTTP/process
helpers; no new framework. It must assert process health, `MemoryIndex.stats().nodes
> 0` after backfill when memory exists, one turn persisted, and stop semantics.
O(memory files + one turn); bound every network/model wait.

**Ambiguity register.**
- Which process this smoke owns: `resolved` → bridge service only; popup behavior
  is verified separately by N-40.
- Cloud secret availability: `crystallizes-during`; report missing, never print it.
- Existing empty memory index cause: `resolve-before-start`.

**Actual result `[revised: implementation evidence]`.** The deterministic smoke is
service-only; popup behavior remains N-40 so this command has one objective. It
proved Gemini health, writer/tick/journal startup, 100-node startup backfill, one
persisted/indexed turn (100→102), and clean shutdown. The first run found and fixed
inherited lifecycle-lock descriptors in both child launch paths. See D-28.

#### ~~N-35 (SENSE) — Independent adaptive sensor services~~ `✅ MVP → D-29`

**Pathway.** D-18/D-22/D-27 supply capture and lifecycle seams. Parallel tracks:
(A) remove response-model modality as a lifecycle prerequisite; (B) vision N-frame
window/region state + information-gain tracking; (C) audio utterance accumulation,
VAD/transcription and gain/dedup adaptation. A+B+C converge on a model-free
`PerceptionEvent`; high information gain then queues N-36 refinement and N-39 action.

**Triple-anchor.** *Task-local:* sensors capture→segment→extract→score continuously,
without invoking the LLM for ordinary low-gain data. *Implementation-scope:*
foreground/region OCR, EMA boxes, pixel/Jaccard/VAD gates and transcription exist;
sensor start is still coupled to `profile.vision/audio`, regions use current-frame
OS rectangles rather than an N-frame boundary history, and extraction currently
uses a droppable LLM call for every passed slice. *Soul:* this is the watcher body,
independent of the replaceable brain. **Current lifecycle coupling is out of
alignment and must be removed.**

**Deferral.** Hard-defer model-based refinement until N-36's event contract; the
model-free service split starts after D-28. Soft-defer learned edge models until
heuristic/statistical gain measures show a measured miss. Re-entry for edge-DL:
recorded corpus demonstrates heuristic recall/precision failure.

**Implementation specifics.** Stdlib + existing Pillow/tesseract/Whisper. Maintain
per-region ring buffers for the last N signatures/boxes/OCR hashes; Hungarian
matching is unnecessary initially—existing IoU matching + EMA is O(W²) for small
window counts. Gain combines pixel delta, OCR novelty, region birth/death, active
app change, speech VAD, transcript novelty and elapsed-time pressure. Target
O(N·W + changed_pixels) memory/time per frame, with bounded ring buffers. The LLM
is invoked only for high-gain refinement, never raw capture cadence.

**Ambiguity register.**
- N-frame size and adaptive thresholds: `crystallizes-during`.
- OS window rectangles vs visual segmentation fallback: `intentionally-open`;
  use OS geometry first, image segmentation only when unavailable.
- Audio intent/wake behavior: `resolve-before-start`; passive context must not
  become a turn per chunk.

**Actual result `[revised: KISS implementation]`.** Existing distilled context
records remain the sensor boundary; no new event hierarchy was added. Lifecycle
guards were removed from bridge/CLI/voice-listen paths while media attachment
guards remain at turn construction. Vision uses a bounded six-frame nearest-state
novelty window and foreground-title boundaries. Existing RMS/OCR/transcript gates
keep low-gain slices away from optional model extraction. See D-29.

#### ~~N-36 (SNAP) — Frozen dynamic context and budget arbitration~~ `✅ MVP → D-30`

**Pathway.** Hard-dep on D-29's distilled perception records; consumes D-01/D-05/D-08/
D-24/D-26. Parallel producers—recent rolling tiers, active session/thread, recalled
memory, current perception, time/reminders, document/web evidence and policy—converge
once into `TurnContextSnapshot`. Snapshot feeds response, journal, proactive and
N-41 agency facets with one `context_version`; stale results are rejected.

**Triple-anchor.** *Task-local:* build one immutable, provenance-tagged, token-budgeted
context reference for each user or autonomous trigger. *Implementation-scope:*
`ContextStore.tail_for_model()` and the retrieval bundle exist, but callers compose
strings ad hoc and the paper contracts are absent. *Soul:* continuity and coherent
parallel evidence require a shared reference frame. **Coherent and load-bearing.**

**Deferral.** The sensor dependency is satisfied by D-29. Snapshot structure can be
coded in parallel with N-38 evaluation fixtures. Re-entry: immediate.

**Implementation specifics.** Dataclasses in a small kernel module:
`TurnContextSnapshot`, typed `EvidenceRef`, `PolicyState`; immutable tuples/dicts at
dispatch. Budget allocation is deterministic: reserve fixed minimums for query,
recent thread and policy; allocate the remainder by source utility/recency with
per-source caps. O(total candidate chars/tokens). Do not copy raw media into durable
state; store references and distilled text.

**Ambiguity register.**
- Exact source budget weights: `crystallizes-during`.
- Snapshot persistence: `resolve-before-start` → log metadata/provenance, not raw
  media or complete prompts.
- Parallel facet scope for MVP: `resolve-before-start` → context, recall/web,
  fast response, journal, agency proposal; slow refinement may arrive late.

**Actual result `[revised: KISS implementation]`.** A frozen
`ContextSnapshot(version, text)` now wraps the existing dynamic L1/L2/L3 tail.
Turns and proactive runs reuse it, and turn logs persist `context_version`.
Retrieval evidence already remains fixed for each run. No second budget allocator,
prompt archive, or facet framework was added. See D-30.

#### ~~N-37 (KV) — llama.cpp KV lifecycle and derived-context cache~~ `✅ MVP → D-37`

**Pathway.** Hard-dep D-30 for stable prompt identities and D-36 for the local
runtime. Uses llama.cpp `/slots/:id_slot` save/restore where supported; cloud mode
uses no fake KV persistence. Derived doc/web/refined-context caches are keyed by
content hash + model/template identity and injected through D-30.

**Alignment.** *Task-local:* reuse expensive stable prefixes and restore local
session state safely. *Implementation-scope:* `cache_prompt:true` provides live
prefix reuse, and bundled llama.cpp exposes slot save/load routes; LAWRENCE has no
durable slot manager or cache provenance. *Soul:* improves edge continuity without
making opaque KV the canonical memory. Markdown remains truth. **Coherent if KV is
strictly derivative.**

**Deferral.** Hard-defer durable slot persistence until D-36 proves exact server
version/API behavior and D-30 provides stable prompt hashes. This does not block
cloud-first MVP behavior, but N-44 requires the local compatibility scenario.
Completing this node unblocks local warm-restart acceptance in N-44.

**Implementation specifics.** HTTP slot API + atomic manifest under `.runtime/`,
never `memory/` canonical data. Validate model hash, chat-template hash, KV type,
context size and prompt-prefix hash before restore; otherwise discard. Disk/time
cost O(KV size); cap snapshots and retain newest valid checkpoint.

**Ambiguity register.**
- Slot API request/response shape for bundled llama.cpp: `resolve-before-start`
  with an isolated live probe.
- GPU/CPU KV offload flags by platform: `crystallizes-during`.
- Cloud provider prompt caching: `intentionally-open`, capability-reported only.

**Actual result `[revised: bundled-runtime constraint]`.** Managed startup now
restores and shutdown saves one profile-keyed text-only slot under `.runtime/kv/`.
The bundled multimodal server required a narrow patch because it rejected text-only
slot state whenever a projector was loaded; media-bearing slots remain rejected.
`make kv-smoke` proves 17 restored prefix tokens and suffix-only continuation.
No second document/web cache was added: whatever stable derived text is actually in
the served prompt is captured by the derivative KV checkpoint. See D-37.

#### ~~N-38 (RETEST) — Retrieval live-corpus stress and Perplexity baseline~~ `✅ → D-31`

**Pathway.** Hard-dep D-28 populated runtime; consumes D-24/D-26. Build a corpus
spanning notes, chats, rolling context, journals, ingested docs and controlled web
pages. Run category-isolation tests in parallel, then convergence tests for
discern→retrieve→assess→refine→fuse. Results inform D-30 budgets and N-39 proactive
quality; acceptance flows to N-44.

**Triple-anchor.** *Task-local:* demonstrate relevant, cited, iterative retrieval
under cache-hit, cold-web, bot-block, missing-embedding and conflicting-source cases.
*Implementation-scope:* deterministic unit coverage is good, but the live index is
empty, local docs absent, and the current diagnostic can return zero citations.
*Soul:* autonomous recall is not real until it retrieves the user's own context
reliably. **Coherent; current evidence is insufficient.**

**Deferral.** Hard-defer none after D-28. Web quality comparisons to external docs
are soft-deferred until the base live corpus produces measurable metrics. Re-entry:
baseline report exists.

**Implementation specifics.** Add fixture-backed relevance judgments and replay
records, not a broad benchmark framework. Metrics: recall@k, MRR, citation coverage,
source diversity, duplicate rate, stale-result rate, rounds, wall time and failure
reason. Compare current RRF+BM25 baseline to only one change at a time. Target
bounded O(rounds·categories·depth); no ANN until measured corpus size requires it.

**Ambiguity register.**
- Perplexity proprietary internals: `intentionally-open`; baseline observable
  behavior (query decomposition, parallel search, rerank, iterative sufficiency,
  citations), not imitation claims.
- Minimum quality thresholds: `resolve-before-start` from a hand-labeled MVP set.
- Network nondeterminism: `resolve-before-start` with recorded pages plus one live lane.

**Actual result `[revised: measured evidence]`.** The labeled production-engine
gate passes recall@5 1.00/MRR 1.00 with clean note/doc/web categories, contiguous
citations and no duplicates. The live Gemini report passes own memory, current PLAN,
original paper and cached web at recall@8 1.00/MRR 0.88. Cold web reports its DDG
bot-block/missing-provider degradation explicitly. Fixes were limited to URL-category
admission and natural-language FTS OR recall. See D-31.

#### ~~N-39 (AUTO) — Autonomous realize→remember→retrieve→surface loop~~ `✅ MVP → D-32`

**Pathway.** Hard-deps D-29, D-30, D-31; D-03/D-05/D-12/D-13 supply tick, journal,
reminders and guards. Event gain queues autonomous work without consuming the
cooldown until admission succeeds. Parallel journal and retrieval branches converge
at a significance/policy/elevation decision; accepted findings are surfaced,
atomically logged, journaled and indexed. Feeds N-44.

**Triple-anchor.** *Task-local:* with no user prompt, LAWRENCE tracks changing
context, writes objective atomic events, updates short/mid/long journal memory and
surfaces a useful non-duplicate finding. *Implementation-scope:* all organs exist,
but droppable admission can starve and cooldown is advanced before useful work is
confirmed. No hour-long behavior test exists. *Soul:* this is the unplugged-user
litmus. **Highest alignment; behavior currently unproven.**

**Deferral.** Retrieval quality is satisfied by D-31; admission/firing
instrumentation can start after D-28. Re-entry: sensor events and snapshot available.

**Implementation specifics.** Introduce an explicit bounded autonomous queue/state
machine: observed→admitted→retrieving→assessed→surfaced|recorded|dropped, with reason
codes. Cooldown begins on admitted/surfaced work, not attempted/skipped work.
Objective event log is append-only JSONL; journal remains synthesized Markdown.
O(queue bound), one in-flight proactive job, backpressure drops low-gain events first.

**Ambiguity register.**
- Minimum surface frequency: `crystallizes-during`; quality beats quota.
- Journal short/mid/long cadence: `resolve-before-start` using event count + elapsed
  time + context shift, not fixed time alone.
- Notification quiet-hours: `resolve-before-start` in N-43 policy.

**Actual result `[revised: KISS implementation]`.** No queue/state-machine hierarchy
was needed. Proactive returns one completion boolean, and proactive/journal clocks
commit only after successful work. Deterministic tests prove failed attempts retry;
the live no-user-turn smoke proves tick→Gemini→finding→persistence→index and then
context→first-person journal→index. See D-32.

#### ~~N-40 (UI) — Classic UI becomes truthful and complete~~ `✅ MVP → D-35`

**Pathway.** Hard-dep D-28 bridge truth; consumes D-30/D-32/D-34 state. Replace
placeholders in parallel: bridge-down behavior, backend reminders, chat/session
workspace, typed evidence/provenance, capability markers, agency confirmations and
autonomy status. Converges in the existing classic variant; no redesign required.

**Alignment.** *Task-local:* every visible control either changes real backend state
or is visibly unavailable with a reason. *Implementation-scope:* transport, SSE,
jobs, source cards and panels work; `localDraft` fabricates answers, reminders are
local drafts, and several backend capabilities are hidden. *Soul:* a transparent
surface must not simulate assistance. **Coherent.**

**Deferral.** Hard-defer agency confirmation UI until N-41 contract; other tracks
start after D-28. Completing backend reminders/session UI unblocks N-44's human
interaction acceptance.

**Implementation specifics.** Use existing ES modules and bridge endpoints. Delete
`localDraft`; render a durable bridge-unavailable error. Replace localStorage
reminders with `/reminders`; expose `/chats` and `/links`; consume typed evidence
assets and backend capability buckets. Maintain the 80-message render cap and
incremental streaming.

**Ambiguity register.**
- Exact session UX: `crystallizes-during`; minimal switch/new/archive first.
- Panel layout: `intentionally-open`; function before polish.
- Unsupported control behavior: `resolve-before-start` → disabled + reason.

**Actual result `[revised: KISS implementation]`.** The existing classic variant was
kept. Fabricated bridge-down answers and browser-only reminder drafts were removed;
reminders and chats now use their existing bridge endpoints; policy is visible; and
agency proposals require explicit typed confirmation. The DOM feature harness,
Python UI seam checks and Rust shell check pass. See D-35.

#### ~~N-41 (AGENCY) — Confirmed, allowlisted, audited effectors~~ `✅ MVP → D-34`

**Pathway.** Hard-deps D-30 snapshot and D-33 policy. Build proposal and execution
as separate states. Parallel effectors may include local file artifact creation,
opening a URL/application, reminder/task mutation and approved command execution;
all converge through one confirmation/admission/audit gate. D-35 renders proposals.
N-44 requires at least one safe state-changing action.

**Triple-anchor.** *Task-local:* the assistant can do useful work, not only emit
text, while the user retains control. *Implementation-scope:* reminders/tasks,
context-pack export and URL opening exist as disconnected explicit calls; there is
no typed model proposal, risk class, confirmation token or unified audit trail.
*Soul:* agentic means controlled action, not silent automation. **Coherent; missing.**

**Deferral.** Hard-defer shell/OS commands until policy and confirmation are proven.
Start with reversible/local effectors after N-43. Re-entry for higher-risk actions:
audit + denial + confirmation tests pass.

**Implementation specifics.** Dataclasses/JSON schemas for `ToolActionProposal`,
`ActionDecision`, `ActionResult`; allowlist registry similar to launcher actions.
Risk levels: read-only, reversible local write, external/state-changing. Model only
proposes. Executor validates arguments, requires a one-use confirmation token where
needed, applies timeout, and appends an audit JSONL record. O(1) registry lookup.

**Ambiguity register.**
- MVP effector set: `resolve-before-start` → artifact write, reminder/task mutation,
  open URL; no arbitrary shell by default.
- Voice confirmation: `intentionally-open`; typed UI confirmation is canonical.
- Rollback semantics: `crystallizes-during` per effector.

**Actual result `[revised: narrower safe MVP]`.** The allowlist is `task.add`,
`reminder.add`, and `artifact.write`; URL launch was omitted because it adds no core
MVP proof. Model output only proposes. One-use typed confirmation executes through
D-33 policy, with durable local action events and hash-only policy audit. Live Gemini
proposal→confirmation→artifact passes. See D-34.

#### ~~N-42 (LOCAL) — Zero-shot/random-turn llama.cpp compatibility~~ `✅ MVP → D-36`

**Pathway.** Follows the completed cloud-first UI lane D-35. Hard-dep D-28 harness;
feeds D-37 and N-44. For every core scenario, randomly select a turn boundary and
run it against bundled llama.cpp without provider-specific code changes. Measure
latency separately; correctness is the first gate.

**Triple-anchor.** *Task-local:* switching backend to local preserves schemas,
retrieval, context, cancellation, proactive, journal and agency proposal behavior.
*Implementation-scope:* one role seam and local server exist; current config is
Gemini, local full turns are historically slow, and no cross-backend contract
matrix proves parity. *Soul:* the brain must remain replaceable. **Coherent.**

**Deferral.** Hard-defer useful-latency optimization until compatibility failures
are fixed and measured. D-37 waits on server capability probes. Re-entry: D-28
scenario harness exists.

**Implementation specifics.** Matrix test with deterministic fixture inputs and
schema-level assertions; cloud and local outputs need not match wording. Random-turn
means start local at different points in a multi-turn replay with the same durable
memory/snapshot inputs. Track first-token/total latency, model calls and tokens.
Use thinking budgets, role token caps, prompt-prefix reuse and GPU layers only after
measurement. No provider branch outside `model.py`.

**Ambiguity register.**
- Acceptable local latency: `crystallizes-during`, report p50/p95 first.
- Gemma schema reliability: `resolve-before-start` from replay evidence.
- Hardware-specific GPU offload: `intentionally-open`.

**Actual result `[revised: correctness before optimization]`.** Server-level
reasoning is disabled when `LK_THINKING` is off, preventing empty structured
responses caused by thought-budget exhaustion. `make local-smoke` passes seven core
contracts including live cancellation, a deterministic random boundary and an
agency proposal. CPU latency is p50 31.79s, p95 98.64s, max 131.96s. See D-36.

#### ~~N-43 (POLICY) — Privacy, provenance and trust-boundary enforcement~~ `✅ → D-33`

**Pathway.** D-17/D-22/D-27 provide routing and sensor controls. Define policy
before N-41 effect execution and thread it through D-29 capture, D-30 snapshots,
D-31 web/cloud retrieval and D-32 surfacing. One `PolicyState` decides capture,
retention, cloud/web disclosure, redaction, notifications and action confirmation.

**Triple-anchor.** *Task-local:* make every boundary explicit and testable.
*Implementation-scope:* toggles and routing exist, but there is no per-trigger policy
object, redaction step or audit of what context leaves the machine. *Soul:* local-first
is control and inspectability, even during temporary cloud-first generation.
**Coherent and mandatory.**

**Deferral.** Hard-defer state-changing effectors until this lands. Basic policy can
start after D-28 and in parallel with sensors/context. Completing it unblocks N-41
and policy acceptance in N-44.

**Implementation specifics.** Small policy dataclass + pure `allow(operation,
snapshot)` decision function. Default: raw media local/transient; cloud receives
distilled/redacted text unless a user turn explicitly attaches media; web queries
exclude secrets/path content; external actions require confirmation. Log decision
metadata and hashes, not secrets/raw buffers.

**Ambiguity register.**
- Redaction vocabulary: `crystallizes-during`, start with secrets, tokens, emails,
  absolute private paths and configured patterns.
- Raw-buffer TTL: `resolve-before-start`.
- Cloud-mode visual/audio consent: `resolve-before-start`, explicit per surface.

**Actual result `[revised: KISS implementation]`.** One process-wide `PolicyState`
covers cloud text/media, web, notifications and external-action confirmation.
Remote text/web are redacted, ambient media is denied, explicit attachments may
pass, unknown operations deny, and each decision writes hash-only JSONL metadata.
Health publishes the policy summary. See D-33.

#### ~~N-44 (ACCEPT) — Running end-to-end MVP acceptance~~ `✅ MVP → D-38`

**Pathway.** Terminal convergence: D-28 + D-29 + D-30 + D-31 + D-32 + D-35 +
D-34 + D-36 + D-33. D-37 is required for the local warm-restart/KV checkpoint
scenario, but cloud-first interactive acceptance can run earlier. This node has no
downstream consumer; it is the proof boundary.

**Triple-anchor.** *Task-local:* prove the whole system, not modules. *Implementation-
scope:* current gates are offline and component-focused. *Soul:* the watcher must be
useful while the user is absent, remember why, surface evidence, and safely act.
**Coherent.**

**Deferral.** Structurally blocked by the incoming MVP nodes. Re-entry: all required
contracts implemented. Each completed predecessor unblocks one acceptance lane:
D-29 perception, D-30 context, D-31 grounding, D-32 autonomy, D-35 UI, D-34 agency,
D-36 local replacement, D-33 privacy.

**Acceptance evidence.**
- Cloud-first cold start → populated memory index → typed turn with cited own/doc/web
  evidence → durable transcript/note/journal.
- One-hour accelerated and one real-duration unattended run: context shifts produce
  bounded atomic logs, tier movement, context-dependent journal updates and at least
  one policy-allowed useful proactive finding, without duplicate storm or queue growth.
- Vision replay validates N-frame region continuity and high-gain refinement;
  audio replay validates utterance accumulation and no turn-per-chunk behavior.
- Classic UI controls real observers, reminders, chats, retrieval, cancellation,
  source provenance, autonomy state and agency confirmation; bridge failure is honest.
- One confirmed effector executes and is audited; one denied/unconfirmed action does not.
- Random-turn local llama.cpp replay passes the same behavioral contracts; restart
  restores only a compatible KV checkpoint and falls back safely when incompatible.
- Full regression gate, Rust check, desktop runtime/features, retrieval report and
  live process cleanup all pass.

**Ambiguity register.**
- "Useful" proactive finding: `resolve-before-start` via a small labeled scenario set.
- Real-hour environmental variability: `intentionally-open`; retain replay lane for
  determinism and real lane for operational proof.

**Actual result `[revised: terminal acceptance]`.** Cloud grounded turns,
three-category retrieval, no-turn autonomy, confirmed agency, truthful UI, local
random-turn compatibility, warm KV restart, a real unattended hour, full offline/UI/
Rust gates and clean process shutdown all pass. Cold public web remains explicitly
degraded without a configured working provider; local CPU latency is measured rather
than hidden. See D-38.

### §K.2 — Stage 1 edge set

```
[D-27] --dependency----------> [D-28] load-bearing  current runtime truth anchored startup
[D-18/D-22/D-27] --partial---> [D-29] load-bearing  observer base became independent
[D-01/D-05/D-08/D-24/D-26] --> [D-30] load-bearing memory/evidence feed the snapshot
[D-20/D-26] --partial--------> [D-37] significant   prompt reuse became durable KV
[D-24/D-26/D-27] --partial---> [D-31] load-bearing retrieval code gained live proof
[D-03/D-05/D-12/D-13/D-27] --> [D-32] load-bearing autonomous organs gained behavior proof
[D-10/D-12/D-23/D-27] -------> [D-35] significant   real backends now drive truthful UI
[D-09/D-10/D-15/D-27] -------> [D-34] significant   cancel/registry primitives shape agency
[D-17/D-20/D-21/D-27] -------> [D-36] load-bearing local seam/runtime is compatible
[D-17/D-22/D-27] ------------> [D-33] load-bearing routing/sensors cross trust boundaries

[D-28] --dependency----------> {D-29,D-31,D-32,D-33,D-35,D-36}
[D-29] --dependency----------> [D-30] load-bearing  distilled perception enters snapshots
[D-29] --dependency----------> [D-32] load-bearing  autonomous triggers use observations
[D-30] --dependency----------> {D-32,D-34} load-bearing shared context for decisions
[D-30] --dependency----------> [D-37] significant   stable prompt identity enables KV
[D-31] --dependency----------> [D-32] load-bearing  proactive quality uses grounded retrieval
[D-32] --dependency----------> [D-35] significant   UI exposes actual autonomy state
[D-33] --dependency----------> [D-34] load-bearing  no action without policy
[D-34] --dependency----------> [D-35] significant   UI renders confirmation/result
[D-36] --dependency----------> [D-37] load-bearing  slot API belongs to local runtime
{D-28,D-29,D-30,D-31,D-32,D-33,D-34,D-35,D-36,D-37} --dependency--> [D-38] load-bearing
```

#### Auditable edge ledger

```
[D-27] --{dependency}--> [D-28]
  Weight: load-bearing
  Meaning: The verified current runtime and configuration became D-28's reproducible baseline.
  Break condition: If D-27's observed config/runtime changes, D-28 fixtures and expected status must be regenerated.

[D-18/D-22/D-27] --{partial-completion}--> [D-29]
  Weight: load-bearing
  Meaning: Existing observers and probe-only controls supplied D-29's sensor substrate.
  Break condition: Replacing observer contracts requires D-29 lifecycle and novelty tests to change together.

[D-01/D-05/D-08/D-24/D-26] --{dependency}--> [D-30]
  Weight: load-bearing
  Meaning: Rolling tiers, journals, sessions, recall and evidence are the source arms of each frozen snapshot.
  Break condition: Removing or changing a source contract changes snapshot provenance and budget allocation.

[D-20/D-26] --{partial-completion}--> [D-37]
  Weight: significant
  Meaning: Model routing and live prompt reuse provide the seam for a derivative durable KV cache.
  Break condition: A model/template/server identity change invalidates saved KV checkpoints.

[D-24/D-26/D-27] --{partial-completion}--> [D-31]
  Weight: load-bearing
  Meaning: The implemented hybrid engine is the system under live-corpus evaluation.
  Break condition: Ranking, indexing or category changes require replay baselines and labels to be rerun.

[D-03/D-05/D-12/D-13/D-27] --{partial-completion}--> [D-32]
  Weight: load-bearing
  Meaning: Tick, journal, scheduler and guards provide autonomous organs whose end-to-end behavior remains unproven.
  Break condition: Removing any trigger/write/guard path invalidates unattended-run acceptance.

[D-10/D-12/D-23/D-27] --{partial-completion}--> [D-35]
  Weight: significant
  Meaning: Capability, scheduler and transport backends already exist behind incomplete or false UI state.
  Break condition: Backend payload changes require the classic UI contract and feature harness to change.

[D-09/D-10/D-15/D-27] --{partial-completion}--> [D-34]
  Weight: significant
  Meaning: Cancellation, capability data and an action registry are reusable controls for safe effectors.
  Break condition: Agency cannot bypass cancellation, capability admission or the shared registry.

[D-17/D-20/D-21/D-27] --{constraint}--> [D-36]
  Weight: load-bearing
  Meaning: The provider seam and installed llama.cpp runtime define mandatory local compatibility.
  Break condition: Provider-specific orchestration outside model.py fails random-turn compatibility.

[D-17/D-22/D-27] --{constraint}--> [D-33]
  Weight: load-bearing
  Meaning: Cloud routing and continuous sensors cross explicit privacy boundaries that need policy enforcement.
  Break condition: New capture, provider or effector paths must be denied until represented in PolicyState.

[D-28] --{dependency}--> [D-29]
  Weight: load-bearing
  Meaning: Sensor behavior was diagnosed against a reproducible running process baseline.
  Break condition: Startup/process ownership changes require sensor service tests to be rerun.

[D-28] --{dependency}--> [D-31]
  Weight: load-bearing
  Meaning: Retrieval stress needs a populated index, working ingestion and observable provider state.
  Break condition: An empty or stale index makes relevance results invalid.

[D-28] --{dependency}--> [D-32]
  Weight: load-bearing
  Meaning: Autonomous firing requires the tick, observers, backends and logs to be demonstrably running.
  Break condition: A stopped/degraded component invalidates unattended-run conclusions.

[D-28] --{dependency}--> [D-35]
  Weight: significant
  Meaning: UI truth must come from a stable bridge/runtime contract.
  Break condition: Bridge endpoint or health-state changes require UI behavior updates.

[D-28] --{dependency}--> [D-36]
  Weight: load-bearing
  Meaning: The same scenario harness is used to compare cloud and local turns.
  Break condition: Divergent harnesses cannot prove backend replaceability.

[D-28] --{dependency}--> [D-33]
  Weight: significant
  Meaning: Policy is attached to the actual cloud-first runtime and its observed outbound paths.
  Break condition: Runtime topology changes require a trust-boundary review.

[D-29] --{dependency}--> [D-30]
  Weight: load-bearing
  Meaning: Frozen snapshots consume distilled context records, not raw observer internals.
  Break condition: Event schema or provenance changes require snapshot construction changes.

[D-29] --{dependency}--> [D-32]
  Weight: load-bearing
  Meaning: Information-gain events are the environmental triggers for autonomous work.
  Break condition: If sensors cannot emit bounded meaningful events, proactive becomes polling or noise.

[D-30] --{dependency}--> [D-32]
  Weight: load-bearing
  Meaning: Proactive reasoning must evaluate one stable current-context reference.
  Break condition: Ad-hoc context reads permit stale or contradictory autonomous findings.

[D-30] --{dependency}--> [D-34]
  Weight: load-bearing
  Meaning: Every action proposal records the snapshot and provenance that justified it.
  Break condition: An action without a snapshot cannot be audited or checked for staleness.

[D-30] --{dependency}--> [D-37]
  Weight: significant
  Meaning: Stable snapshot/prompt identities allow safe KV checkpoint keys.
  Break condition: Unstable prefixes make restored KV incorrect and must force a cache miss.

[D-31] --{dependency}--> [D-32]
  Weight: load-bearing
  Meaning: Proactive findings use the same measured retrieval quality as user turns.
  Break condition: Retrieval below the labeled threshold disables external surfacing.

[D-32] --{dependency}--> [D-35]
  Weight: significant
  Meaning: The UI exposes real autonomous state, findings, drop reasons and journal activity.
  Break condition: Autonomous state-machine changes require matching UI event handling.

[D-33] --{dependency}--> [D-34]
  Weight: load-bearing
  Meaning: Policy admission and confirmation are mandatory before any effector executes.
  Break condition: An unrepresented operation is denied, not executed.

[D-34] --{dependency}--> [D-35]
  Weight: significant
  Meaning: The classic UI is the canonical proposal confirmation and result surface.
  Break condition: Without a confirmation surface, confirmation-required actions stay pending.

[D-36] --{dependency}--> [D-37]
  Weight: load-bearing
  Meaning: Durable KV behavior is implemented and probed only against the supported local runtime.
  Break condition: A llama.cpp server/API version change invalidates the slot adapter.

[D-28/D-29/D-30/D-31/D-32/D-33/D-34/D-35/D-36/D-37] --{dependency}--> [D-38]
  Weight: load-bearing
  Meaning: D-38 is the convergence proof for every required MVP behavior.
  Break condition: Any failed predecessor lane prevents MVP completion.

```

**Current executable frontier `[revised: MVP accepted]`:** none inside §K. D-38 is
the terminal sink. Remaining nodes elsewhere in PLAN.md are post-MVP product backlog.

**Periodic re-triage after three completions.**
- `[D-31] completed` retrieval quality and degraded-state evidence now unblock N-39.
- `[D-36] completed` local compatibility now feeds the terminal acceptance lane.
- `[N-43] centrality:H ambiguity:M` unchanged; required before effectors.
- `[N-39] centrality:H ambiguity:M` is now executable because D-29/D-30/D-31
  fixed its trigger, context and retrieval inputs.

### §K.3 — Stage 2 AUDIT findings

**Structural invariants.**
- N-nodes with zero incoming D-edges: none remain in the MVP partition.
- D-nodes with zero outgoing edges: D-38 only, intentionally, because it is the
  terminal accepted sink; older D-nodes retain live product-backlog outflow.
- Cycles: none. D-30→D-37 and D-36→D-37 converge; D-37 does not feed back into either.
- Diamonds: D-29→{D-30,D-32} converges at D-32; D-28 fans into sensor/retrieval/local/
  policy tracks that converge at D-38; D-30 and D-33 converge at D-34.

**Alignment invariants.**
- Highest-centrality N-34, N-36, N-39 rechecked. D-28 confirms N-34 was operational substrate, not
  product drift; N-36 implements the paper's shared reference frame; N-39 is the
  unplugged-user litmus. All three anchors agree.
- Conflict found: D-21 says the default was restored local-first, while live config
  is Gemini. `[revised: current cloud-first state recorded in D-27 and §K.0; D-21
  retained as historical completion state]`.
- Conflict found: D-26 says the autonomy loop is "closed", but firing and live index
  population are unproven. `[revised: D-27→N-38/N-39 makes wiring vs behavior explicit]`.
- Conflict found: sensor independence claim still has response-model capability
  gates. `[revised: N-35 names removal as a load-bearing requirement]`.

**Edge integrity.**
- Every deferral names an unblocker: N-35 learned models→sensor quality; completed
  D-37→D-38 local warm restart; completed D-34→D-38 agency acceptance.
- Every load-bearing edge has testable endpoints and a break condition in its node.
- The old N-18 question is now resolvable: findings are indexed, but
  `run_proactive` still calls `ContextStore.recent_findings()`. N-18 therefore
  remains a real store-hot-path task unless N-39 deliberately switches dedup to
  `MemoryIndex`; it is no longer marked as potentially already obsolete.

**Depth audit.**
- N-40 was M/M, not H: it is important but does not define core cognition.
- D-37 retained the M/H triage: technically ambiguous but not core cloud cognition;
  it is significant for local continuity.
- N-43 escalated to H/M because cloud-first operation makes privacy policy structural,
  not optional.

### §K.4 — Stage 3 REVISE + FINALIZE

- `[revised: audit conflict]` Cloud-first is the current MVP execution posture;
  local-first remains the architectural destination and local compatibility is a
  hard parallel track, not the current default.
- `[revised: audit conflict]` "Autonomy loop closure" now means the data path is
  wired; N-39 owns behavioral firing, de-starvation and unattended proof.
- `[revised: audit conflict]` Sensors are not called independent until lifecycle
  no longer depends on response-model modality and low-gain processing is model-free.
- `[revised: missing scope]` Added N-37 durable KV lifecycle, N-43 privacy policy,
  N-41 true agency and N-44 end-to-end acceptance.
- `[revised: stale frontier]` N-34 replaces the historical recommendation to build
  already-completed N-02/N-09.
- `[revised: audit correction]` N-18 remains open because the live proactive dedup
  path still uses `recent_findings`; indexing findings alone did not subsume it.
- `[revised: resolved]` Bundled slot save/restore is proven for text-only state even
  with the multimodal projector loaded; media-bearing slot state remains unsupported.
- `[revised: terminal proof]` A real unattended hour produced objective sensor logs,
  durable indexed memory and a journal with zero queue growth; D-38 closes N-44.
- `[revised: resolved]` Retrieval thresholds are backed by the labeled replay report;
  proactive admission is backed by deterministic evidence plus the real unattended run.

### §K.5 — Confirmation gate

**Resolved 2026-06-18.** The user confirmed this MVP DAG and added a hard KISS
constraint: each new function/script/object has one objective; avoid
over-parameterization and leave working implementations alone unless a concrete
failure requires change.

---

## §L — Next-horizon conception (post-MVP) — **CONCEPT ONLY, granular planning deferred**

> **Authority + scope.** Captured 2026-06-19 from a user directive. This section is
> **vision/concept jotting, not a build contract** — deliberately *not* RE-style
> granular steps. Its job: record the intent, direction, and enough specificity that
> any model (frontier or a small local gemma-4-class model) can later pick it up and
> plan it without losing the idea. Nothing here is committed or scheduled. The MVP
> (§K / D-38) stands; these are the *next* horizon and **supersede the heuristic
> placeholders** they name. Concept anchors **N-45 … N-50** are reserved for these so
> later planning has stable IDs; they are marked `[concept]`, not `[ ]` (open) — they
> become open nodes only when granular planning starts.
>
> Standing constraints still bind: local-first ([[lawrence-local-first]]); KISS (§K.5,
> one objective per unit); single writer (I1); provider logic only at the model seam
> (I3); stdlib core, heavy deps lazy (I4); realtime budgets are first-class.

### §L.1 — Systematic perception + multi-horizon Information-Gain pipeline `[concept]` (N-45)
*Supersedes the current heuristic proactive trigger (the change-detection in
[[lawrence-sensor-decoupling]] / N-07 / N-33). Today's "info gain" = pixel-delta +
6-frame novelty + RMS/dedup → a flat threshold. The directive is to make this a
**staged, modality-agnostic, realtime perception pipeline** with a real multi-horizon
info-gain estimator gating model invocation.*

The pipeline, as one cascade per modality (screen, audio, … future sensors), each
stage feeding the next a **structured frame** (the common substrate):

1. **Capture / ingest — one mechanism, parameterized at the call.** A single sensor
   ingester per device whose *call* configures resolution / bit-rate / FPS / window
   etc. (no per-resolution forks — KISS). The capture knobs are inputs, not separate
   code paths.
2. **Per-modality consolidator.** Multiple streams of the *same* modality (e.g. two
   monitors / two cameras / multiple mics) are **timestamp-aligned and fused into one
   structured data frame** for that modality+instant — not handled as N independent
   stragglers. Consolidation is what makes the later stages tractable.
3. **Pre-processor / scene categorizer.** Segment the consolidated frame into
   meaningful regions: for **screen** this is almost always windows / boundaries /
   sections — categorize the relevant sections using the **running context + past
   frames + previous extractions + heuristics** (temporal + contextual priors, not a
   cold per-frame parse). For **audio**, the analogous staged decomposition
   (speaker / source / segment / turn boundaries). Output = a region map over the
   structured frame.
4. **Boundary-respecting extraction.** Extract the data *per region* from stage 3 —
   **without forfeiting the boundary**: the boundary itself is folded into each
   region's data (region content + its delimiting context), so downstream reasoning
   knows where a region begins/ends and what it abuts.
5. **Tiered extraction by info-gain (cheap-first, escalate-on-gain).** A *simple*
   heuristic first estimates whether the info-gain in a region's data is **large**:
   - **large gain →** spend a **complex model** to extract / refine that region.
   - **otherwise →** stay light: a stack of **heuristics + statistical ML + online
     RL / state-space + meta-heuristic** algorithms extracts boundary-respecting data
     and refines it *without* a model call.
6. **Multi-horizon Info-Gain estimator.** A *properly developed* algorithm (not a flat
   threshold) producing info-gain across **multiple horizons** (instantaneous vs.
   short vs. longer-range change/novelty), again from the **heuristics + statistical
   ML + online RL/state-space + meta-heuristic** family. **"Non-heavy" is a hard spec,
   not a vibe:** these must be **edge-case- and low-latency-optimized implementations,
   strictly capable of running realtime at 60 FPS** on the perception stream.
7. **Trigger arbiter.** The multi-horizon info-gain is assessed by **kernel logic +
   heuristics + an HMM-based system** to decide whether to **invoke the model**. The
   HMM gives temporal-state awareness (e.g. "user is mid-task vs. context just
   switched") rather than a memoryless threshold.
8. **Cross-pathway opportunistic pull.** *When one sensor pathway fires a model invoke*
   (after all of the above), immediately do a **quick scan of the other pathways** for
   **un-utilized sensor data with useful info-gain — not necessarily high, even mild,
   just above the noise floor** — and pull that alongside, with a **two-pass retrieval
   already pre-attached** to it (so the invoke arrives with cross-modal evidence in
   hand). This is *additive context staging*, independent of — and prior to — the
   model's own consequent retrieval / high-resolution-recall pipeline, **which still
   executes as designed**.

**Audio cascade specifics — the perception layer the watcher actually needs (added
2026-06-19 after a concrete hallucination finding).** The audio path today is a bare
RMS-energy gate → whisper → word-count/dedup gate, with **no real speech detection**.
It was caught **fabricating fluent sentences from an amplified silent noise floor**
(e.g. "Stay away from me!" with the user silent) and writing them to memory/journal/
proactive — fabricated perception that poisons the whole loop. A tactical fix landed
(faster-whisper `vad_filter` + `no_speech_prob`/`avg_logprob` guards, drop the 20×
noise pump); the *systematic* audio cascade must provide, as proper stages:
- **Real VAD** (Silero/WebRTC-class) as the stage-3 speech/non-speech decision — energy
  alone cannot separate quiet speech from ambient (here both sit near −50 dB). **Every
  stage is hallucination-resistant by contract:** confidence-, VAD-, and scene-gated;
  perception is never fabricated.
- **Acoustic-scene / environment detection + labeling** — classify and *transcribe the
  ambient* (speech / music / TV / keyboard / traffic / silence) as **context**, so
  non-user audio is logged as environment, never mistaken for user speech.
- **Expression / paralinguistics** — detect & transcribe the *how*: prosody, emphasis,
  emotion, laughter, tone (beyond the words).
- **Speaker diarization + addressee detection** — *who* is speaking and *to whom*
  (user→LAWRENCE vs. user→another person vs. media→no-one). Only "addressed to the
  system" (or genuinely significant ambient) should drive a turn/proactive invoke;
  everything else is context. This is the audio twin of the trigger arbiter (stage 7).

These map onto the generic stages: VAD + scene = stage-3 categorizer; expression +
diarization = stage-4 boundary-respecting extraction; addressee = the stage-7 invoke
decision.

**Candidate stack — research 2026-06-19 (survey in [[lawrence-next-horizon-conception]]).**
Direction the user CHOSE 2026-06-19: the **main perception/STT = SenseVoice × sherpa-onnx**
— one non-autoregressive, CPU/GGUF model giving **ASR + emotion(SER) + audio-event(AED) +
diarization** on the **offline sherpa-onnx** runtime; it collapses 3 of the 4 perception
features into one local model and replaces the brittle whisper-on-noise path that
hallucinated. Plus a **best realtime *streaming* transcriber, invoked on-demand (when a
trigger/need calls for it), chosen by latency + reliability, local** — model still TBD.
**End-to-end speech-to-speech and TTS are DEFERRED** (revisit later, out of current scope).

| Layer | Local-first candidates | Status |
|---|---|---|
| Main recognizer (continuous, rich) | **SenseVoice** — ASR+SER+AED+diarization, non-AR, GGUF/ONNX | ✅ chosen |
| Runtime / framework | **sherpa-onnx** — offline STT/TTS/VAD/diar/enhance/source-sep, edge | ✅ chosen |
| On-demand realtime streaming ASR | Parakeet-TDT · Nemotron-streaming · Moonshine v2 · WhisperLiveKit | ⏳ TBD by latency+reliability |
| VAD (stage-1) | **TEN-VAD** (lowest latency) · Silero (lightweight) | ⏳ candidate |
| Diarization / addressee | pyannote 3.1 · NeMo Sortformer (streaming) · SenseVoice diar | ⏳ candidate (realtime diar still 5–15pp worse DER) |
| Expression / SER | SenseVoice SER · emotion2vec | ↳ in main |
| Environment / AED | SenseVoice AED · BEATs/AST/PANNs/CLAP | ↳ in main + scene tagger |
| TTS | Kokoro · Piper · Orpheus · XTTS-v2 · Sesame CSM | ⏸ DEFERRED |
| Speech-to-speech | Moshi · pipecat · LiveKit · speech-LLM omni | ⏸ DEFERRED |

**MVP-deployment check.** This is a **perception/sensor-layer** change, **independent of the
cloud-first generation posture** (§K): sensors are already local + model-independent (D-29),
so swapping whisper → SenseVoice×sherpa-onnx does **not** touch the Gemini generation path
or the accepted MVP loop (D-38). It *advances* the mandatory **local llama.cpp track**
(SenseVoice ships a GGUF/llama.cpp path). New deps (sherpa-onnx / onnxruntime, the SenseVoice
model) must stay **lazy/optional** (I4 — heavy deps off the stdlib core) and **degrade
gracefully** (no model ⇒ fall back, never crash the always-on observer; the D-29 model-
independent sensor contract holds). Deferring S2S + TTS keeps MVP scope tight. **Net:
additive, local-first, MVP-safe** — it lands as part of the N-45 perception cascade through
the N-50 phases, not inside the current MVP. *Still open for planning:* the on-demand
streaming-ASR pick + the VAD/diarization choices (latency/reliability bench on target HW).

**Design tenets.** Realtime (60 FPS) is the budget the whole cascade lives within;
cheap-first / model-only-on-high-gain is the cost doctrine; structured consolidated
frames are the shared substrate across all stages and modalities; the model is the
last and most expensive resort, gated by a real multi-horizon estimator + HMM, never
a flat threshold; **perception is confidence-gated and never fabricated**. *Open
specifics for planning:* which concrete algorithms per stage (e.g. change-point
detection, Bayesian surprise / predictive info-gain, online changepoint +
Kalman/particle state-space, HMM topology), and the structured-frame schema.

### §L.2 — Comprehensive autonomous journal `[concept]` (N-46)
*Extends D-05 / WS-J. Today web-in-journal is **off by default and intentionally
minimal** ([journal.py](../services/lk/kernel/journal.py) `_maybe_web_context`,
throttled, single seed query). The directive: **the journal MUST be comprehensive.***
Concept: the journal is the durable episodic spine, so it should fold in **web + doc +
own-memory** context **comprehensively** (model-decided per-entry retrieval over the
unified engine, not a single throttled seed), while staying first-person,
rolling-revision, and cost-bounded for all-day autonomy. "Comprehensive" > "minimal
seam": an entry should be able to research its own open threads and cite them.
*Open for planning:* the cost ceiling vs. comprehensiveness trade, and whether
per-entry retrieval routes through the N-47 engine.

### §L.3 — Perplexity-Pro-grade / NotebookLM-consistent retrieval `[concept]` (N-47)
*Upgrades the N-02 vector arm and **graduates the deliberate "no ANN dependency"
decision** in [vectors.py](../services/lk/retrieval/vectors.py) (exact brute-force
cosine) now that the quality/scale bar demands it.* The directive sets two bars:
**retrieval as refined as Perplexity Pro "Advanced Search"** (multi-stage, reranked,
iterative, broad+deep) and **citation consistency as reliable as NotebookLM**
(grounded, passage-level, never fabricated). This needs **FAISS or better**
(HNSW / ScaNN / usearch / DiskANN-class) **plus embedding-based semantic hash maps**
(LSH / learned semantic hashing) for fast, scalable approximate-NN over the personal
corpus + web/doc chunks. Pairs tightly with §L.4 (passage-anchored citations need
chunk-level addressing) and §L.5 (scroll-to-chunk). *Open for planning:* exact ANN
backend + dependency/footprint trade vs. I4; hash-map design; rerank model.

### §L.4 — Citation-table contract (enforced, passage-anchored, associative) `[concept]` (N-48)
*Redefines "enforced citations". Today: retrieval runs every turn and a Sources block
is appended, but inline `[N]` is only prompted, and citations point at whole docs
(no passage anchor). The directive makes the **reference table** the citation
substrate and **guarantees citation integrity by construction**.*

A turn builds a **table of candidate references** — drawn from what the model **chose**,
what **retrieval provided**, and what the **user insisted on** — where each row carries
a rich mapping:

- **id ↔ url / content** (stable handle ↔ source);
- **chunk displacement** (offset/locator within the source → enables **scroll-to-the-
  exact-chunk** in the UI);
- **reasonWhy** (why this reference supports the claim);
- **whatWillInvalidateThisCitation** (the condition under which it stops being valid —
  an explicit defeater);
- **whatElseCouldBeRelated** — an **associative map / memory**: 1-click and 2-click
  graph connections to related references/notes (NoteStore edges as the substrate).

**The model only has to select the right rows** from the pulled table; **the system
then formats the final response and fills in the correct citations** from the table.
So the model can't mis-cite — it picks references, the system renders them. This yields
NotebookLM-style passage-grounded, defeater-aware, **associatively navigable** citations.
Depends on §L.3 (chunk-level index for displacement) and feeds §L.5 (browse + jump).
*Open for planning:* the table schema, the select-not-format decoding contract, and how
the associative 1-/2-click expansion is bounded.

### §L.5 — Rich in-window workspace UI (classic-first) — feature vision `[concept]` (N-49)
*The classic overlay becomes a **research workspace + custom search engine**, not a chat
box. Build target stays **classic only** for now (per the user). Today's classic renders
hand-rolled markdown + inert `<pre><code>`; mermaid is only an attachment label; no math /
sandbox / artifacts (see [variants/classic/app.js](../apps/desktop/web/variants/classic/app.js)).*
The envisioned capabilities:

- **In-window browsing / custom search engine** (WolframAlpha + SearXNG feel). A typed
  query yields a **cited response** plus the supporting **links / docs (the specific
  chunk, scrolled-to in the actual doc) / papers / patents / socials / forums /
  discussions**, all **browsable inside the window** — never bouncing to an external
  browser. Grounded in the system's **short ↔ intermediate ↔ long-term** context.
- **Rich rendering + runnable artifacts (sandboxed):** show *and run* code; **Mermaid**
  diagrams; **KaTeX/MathJax** math; **artifacts / small web-apps / WASM**; **graphs,
  geometric drawings, illustrations**.
- **Generated artifacts:** dynamically generated **Marp.js PPTs** with **spanning
  flowchart / graph / diagram** capability (a local **draw.io / Excalidraw-class**
  authoring/render path) — and the **model verifies the deck is legible**; **tabular
  relational SQL / NoSQL data generation**; **MDX generation**.

Scroll-to-chunk depends on §L.4; rich/agentic content depends on §L.3 + the kernel.
All execution surfaces (code/wasm/web-app) must be **sandboxed** (strict-CSP iframe);
this is the largest security surface and is called out as such. *This list will grow —
treat it as the seed of the UI feature set, not its closure.*

### §L.6 — Build methodology — the agreed three-phase process `[concept]` (N-50)
*How we will tackle the §L feature builds — both **§L.5 (UI)** and **§L.1 (the
perception / audio-VAD cascade)** — once concepts are signed off. (User chose
**plan-first** for the audio cascade on 2026-06-19: the tactical whisper-hallucination
fix stays, but real VAD + scene + expression + addressee are designed via these phases
before any code.) Recorded now as the agreed method; the phases themselves are deferred.*

- **Phase 1 — Abstraction DAG.** Build a **dependency / abstraction / "which-feature-
  is-a-special-case-of-which" analysis as a DAG** over the UI feature set (and L.1–L.4
  dependencies). Find the shared primitives so features collapse onto common
  abstractions instead of N bespoke builds.
- **Phase 2 — Implementation-layer assessment.** For each feature/capability, classify
  **where it must live**:
  - **kernel / system-level** implementation or support;
  - **workflow-orchestration** — agentic loop / feedback mechanism with harness
    engineering (n8n / LangGraph-class);
  - **simple config / schema / constrained-decoding modification / template /
    switching**;
  - **additional scripts / MCP / Skills / local-service-servers** — and these must be
    **drivable by a *simple local* model (gemma-4-class tool-calling), not only Claude**;
  - **human-in-the-loop** online iterative refinement — **only for *finalizing*** an
    artifact, never as a routine step;
  - **UI support**;
  - *(extrapolate further buckets as needed: data/storage, security/sandboxing,
    eval/verification of generated artifacts, packaging, …).*
- **Phase 3 — Fold into refined PLAN.md / DONE.md** (granular nodes + edges) and *then*
  implement.

**Cross-cutting constraint (the reason Phase 2 exists):** keep it **local-first and
small-model-drivable** — the orchestration/tooling paths must work with a simple local
model, with frontier models as an enhancement, not a requirement.

---

> **Cross-references for whoever plans §L next.** N-45 supersedes the heuristic trigger
> in N-07/N-33 ([[lawrence-sensor-decoupling]]); N-47 graduates the "no-ANN" call in
> D-20/N-02 and raises the §J engine's quality bar; N-48 redefines D-26/§J.6 "enforced
> citations" and depends on N-47; N-49/N-50 extend the WS-U UI track (N-09 seam done =
> D-23; N-10 classic refactor is the nearest existing surface) and depend on N-47/N-48
> for grounding + scroll-to-chunk. DONE.md is intentionally untouched — nothing here is
> built yet.
