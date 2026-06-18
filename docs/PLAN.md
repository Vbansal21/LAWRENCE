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

**Executable frontier right now (no unsatisfied hard-dep, no active hard-defer):**
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

**`?:open` (carried, not yet resolvable):**
- **`?:open` N-07 root cause** — whether proactive inertness is config (tick off /
  interval) or structural (slot starvation) cannot be resolved from docs; resolves at
  the N-07 *audit* (instrumentation), which is the task's first step by design.
- **`?:open` N-02 vs N-18 subsumption** — whether the unified index subsumes
  `recent_findings` resolves when N-02's index schema is designed; N-18 is sequenced
  to wait on it.
- **`?:open` SOUL confirmation** — the SOUL statement is synthesized from the corpus
  (AUTONOMY §0/§1, ARCHITECTURE); pending the user's explicit confirmation (§6 gate).

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
