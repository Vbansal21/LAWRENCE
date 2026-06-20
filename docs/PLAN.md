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

> **2026-06-20 — REFINEMENT (user: "proactive is far too over-promised / under-delivered;
> keep its scope, refine/iterate/upgrade"). PLAN-ONLY (no code change this round).** The user's
> verdict matches this node's standing "behavior absent" tension — make it deliver within the
> SAME scope (unprompted findings surfaced on significant context change), not broader.
> **Current reality (code-traced 2026-06-20):** the tick calls `_maybe_proactive` on *every*
> B1 buffer flush; it is gated only by a fixed **600 s** interval + a busy flag + (now, D-51)
> the `proactive_enabled` consent gate — i.e. **time-gated, NOT significance-gated**, despite
> the docstring's "after a significant sensor event." It then surfaces only if the local model
> returns `surface:true` (weak local model ⇒ rarely fires well) → the over-promise/under-deliver.
> **Refinement plan (scope-preserving), to build later:**
> 1. **Significance-gate the trigger** — fire only when context significance/Δ crosses a
>    threshold (reuse the journal/significance machinery), not merely the 600 s clock; idle ⇒ no
>    model calls (already the goal — enforce it at the trigger).
> 2. **Adaptive cadence** — shorten the interval when context is changing fast, lengthen when
>    quiet (bounded), so it feels alive without spamming.
> 3. **Firing observability** — emit `debuglog` records at each decision point (tick on? slot
>    busy? event significant? brief said surface? stale? dup?) via the **D-52 logger now
>    available**; expose the existing `_pstat` counters on /metrics so "why nothing surfaced" is
>    inspectable instead of mysterious (the named "firing audit").
> 4. **De-starvation** — route background proactive off the starved local slot (ties **N-21**).
> 5. **Delivery quality** — only after firing is trustworthy (ties **N-02/N-06**).
> **Typed test plan (to add with the build):** `run_proactive` — *input:* a frozen context tail +
> retrieval; *triggers a surface* when significance≥θ AND brief.surface AND not stale AND not dup;
> *must NOT surface* when context tail is empty · significance<θ · slot busy (droppable→skip) ·
> stale (ctx advanced past tolerance) · duplicate of a recent finding · `proactive_enabled` false.
> *output:* `True` iff DB warmed (regardless of surfacing); `present_fn` called exactly once iff a
> finding is surfaced; finding recorded to ctx (kind=finding) + live-indexed. Extend
> `test_proactive_dedup`/`test_significance`/`test_tick` rather than a new suite where possible.

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
> **DECISION (user 2026-06-19): the current (classic) UI is CANONICAL — one UI, refined
> heavily (N-10). The separate `palette` variant (N-11) is superseded/folded in. The N-09
> variant seam stays (swappability + future N-64 workflow-composition surface), but we do
> not maintain two chat front-ends.**

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

### N-10 (UA) — **Canonical UI: classic, heavily refined** `[ ]` — FULL ↩ folds §5(D-11) **— user 2026-06-19: classic IS the canonical UI**
**Directive (user 2026-06-19).** Make the **current (classic) UI canonical** and **refine
it heavily.** It is no longer "Track A pending a palette successor" — there is one UI, and
it must be excellent. This absorbs N-11's intent (palette is no longer a separate variant;
its good ideas — command-palette ergonomics, ⌘K, settings window, turn-id elevation,
backlink chips — are folded INTO the canonical classic surface where they earn their place).
**Scope (heavy refinement, on the N-09 seam):** drop `localDraft` + all fabricated/hollow
state; truthful toggles from `/health`+SSE; vendored markdown; config off the main bar;
then the **deep pass** — ergonomics, layout, the folded UI nodes (N-12 ingest, N-13 PTT,
N-14 reminders, N-15 capability markers), session/recall/link rendering (N-08), typed
evidence cards (FR-008), and the workflow-composition surface (N-64) as it matures. Every
control must pass the **N-67 integrity audit** (no broadcast-without-substance, §K.0.1 #1).
**Self-align:** `grep -c localDraft`→0; bridge-down ⇒ honest error; each control real or
visibly-disabled-with-reason. **Edges:** `--depends-on--> N-09` · `--absorbs--> N-11` ·
`--gated-by--> N-67` (integrity) · `--hosts--> N-12/13/14/15` · `--renders--> N-08, FR-008`.

### N-72 (UI-SHARED-SPACE) — Responses become a collaborative MDX shared space `[ ]` — FULL — **user 2026-06-20, IN MVP** — extends N-10
**Directive (user 2026-06-20).** Reframe the chat surface from *query → answer bubbles* into a
**rolling stack of "frames," each frame a shared MD/MDX space that the user AND the model(s)
co-edit/update.** This is the canonical response surface (folds into N-10).

**Frame model:**
- A **new frame** is instantiated by **each new user query** OR a **proactive instantiation**.
- **Proactive normally UPDATES the current frame in place** (not a new frame) — it augments the
  active shared space; only a genuinely new proactive thread starts a fresh frame.
- The chat is a **rolling stack of frames** (newest active; older frames scroll up, stay rich).

**Per-frame layout (top→bottom):**
1. **The query** (user text / proactive trigger).
2. **Retrieved-content thumbnails — BETWEEN the query and the shared frame.** Each retrieved
   source renders as a **thumbnail = a static snapshot of the retrieved content**, and **the
   thumbnail's TITLE carries that source's citation footer content** (author/site/date/url).
   **Citations move OUT of an end-of-response Sources block and ONTO the thumbnails** (citation
   at point-of-evidence, not appended). Thumbnails sit in a strip above the shared frame.
3. **The shared MDX space** — collaboratively editable by model(s) + user; the living answer/doc.

**Rich rendering (hard requirement):** the shared space + snapshots must render/showcase **rich
MD, MDX, mermaid.js diagrams, and other JS components** (live components, not just static text),
plus **static snapshots** of retrieved pages and **thumbnails** of retrieved content. (Today the
classic UI hand-rolls a minimal markdown renderer and appends a Sources block — this replaces both.)

**Build notes / open for planning:** sits on the N-09 seam + the bridge SSE contract; needs a real
MD/MDX renderer + mermaid + a sandboxed component host (security: untrusted retrieved content must
render sandboxed); a frame data-model in the bridge (frame_id, query_ref, thumbnails[], shared_doc,
editable regions, proactive-update routing to the active frame); snapshot capture + thumbnailing of
retrieved sources; the citation→thumbnail-title mapping (reuses the retrieval CitedResult fields).
Phases TBD; gated by **N-67 integrity** + KISS. **Edges:** `--extends--> N-10` · `--depends-on-->
N-09` (seam) · `--consumes--> D-24/D-26` (retrieval CitedResults → thumbnails+citations) ·
`--renders--> N-08` (session/recall) · `--coexists--> N-64` (workflow-composition surface).

### N-73 (SERVE-OPT) — Deferred serving optimizations `[ ]` 🔭 — split out of N-65 (user 2026-06-20: "leave building from scratch, proceed with 10 tk/s, mark refinement for later")
**Deferred bundle (post-MVP).** MVP serving baseline is **accepted at native ~10 tok/s** (D-45).
These push toward/past ≥15 but are NOT MVP-blocking now: (a) **from-source `-mcpu=native` Oryon
build** (needs VS Build Tools / MSVC CRT — currently absent); (b) **measure/tune on AC power**
(battery throttles hard); (c) **NPU/GPU offload** (Adreno/Hexagon — drops pure-CPU constraint);
(d) **speculative decoding with Gemma-3n-E2B as the draft model**; (e) `lk serve --autotune`
(thread sweep, on AC). **Edges:** `--refines--> N-65` · `--unblocks-by--> [VS Build Tools install]`.

### N-11 (UB) — ~~Track B `palette` variant~~ `[superseded → N-10]` — **user 2026-06-19: no second UI**
**Superseded.** The separate `palette` variant is dropped: there is one **canonical UI**
(classic, N-10). Its concepts (grow-to-content command-palette geometry, ⌘K menu, settings
window, ⌘L cross-chat link flow + backlink chips, U4 turn-id elevation, native vibrancy) are
**folded into N-10** to adopt where they improve the canonical surface — NOT built as a rival
front-end. The N-09 variant *seam* stays (it is what makes the UI swappable / hosts the
future N-64 workflow-composition surface), but we do not maintain two chat UIs. Mockup
`docs/mockups/palette.html` is now a *design reference for N-10*, not a build target.

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

### N-32 (LOCAL-PERF) — Local turn PIPELINE latency `[ ]` — **HARD MVP, top non-UI priority (user 2026-06-20)** *(finding from D-21)*
> **★ Gate #3 (USABLE-LOCAL) is NOT met by serving alone.** N-65 made *serving* ~10 tok/s, but a full
> `run_turn` still takes MINUTES (the pipeline, not the server). **Approach (user 2026-06-20):**
> **asynchronicity · pipelining · parallelism · caching · predictive caching · pre-preparation ·
> pre-baked results for sub-sections** — i.e. don't run the per-turn stages serially-cold.
> Concretely: (a) **parallelize** independent per-turn model calls (query/analysis/retrieval/response)
> instead of sequential; (b) **pipeline** stages so later turns' prep overlaps earlier turns' decode;
> (c) **cache** stage outputs keyed by input identity (reuse the KV/prefix discipline + memoize
> retrieval/analysis); (d) **predictive/speculative caching + pre-preparation** — anticipate the likely
> next sub-tasks (e.g. retrieval seeds, context bundle, journal/proactive prep) and pre-compute during
> idle; (e) **pre-baked sub-section results** — assemble the response from independently-prepared,
> cached sub-section units. Pairs with **N-22** (deadline/watchdog) so it never hangs, and with the
> parallel-facet runtime (N-70, deferred) which this partially anticipates. **In MVP; ties Phase-1
> chat responsiveness.** *Open:* the per-stage dependency DAG (what's truly parallel vs ordered), cache
> invalidation keys, and the predictive-prefetch budget (must stay local-first + cost-bounded).
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

| Finding | Fix                                                                                                   | Where                              |
| ------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------- |
| F1      | N-09/N-26 lean on existing app.js/host scaffolding (prior art, not a D-node; refactor not greenfield) | N-09 body; DONE.md live-stub note  |
| F2      | drew edges D-09→N-16, D-04→N-20, D-19/D-16→N-12, D-18→N-13                                            | DONE.md D-04/D-09 + index; §G      |
| F3      | N-06↔N-08 re-expressed as a diamond off N-02 (converge once, no build cycle)                          | N-06, N-08, §G                     |
| F4      | stated N-08 does not delete D-08's durable transcript (clears working set only)                       | N-08 invariant guard; DONE.md D-08 |
| F5      | marked N-24 terminal (acceptance sink) + N-28 leaf                                                    | N-24, N-28                         |
| F6      | N-18→N-02 resolved `?:unresolved`→`conditional` (sequence after N-02 design)                          | N-18, §G                           |
| F7      | noted N-28 true centrality L; depth driven by ambiguity + user priority                               | N-28 triage note                   |

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

| Directive clause                                   | State at audit (2026-06-18)                                                                                                                 | This build                                                                                            |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| work **autonomously**                              | tick + proactive wired in both kernels (D-03); `run_proactive` rides **web only**, findings/journal **not** re-indexed → recall goes stale  | proactive rides the unified engine; **live incremental indexing** closes perceive→remember→recall→act |
| **long context** capture                           | `ContextStore` dynamic-budget L1→L2→L3 tiering solid (D-01)                                                                                 | unchanged; recall now spans it                                                                        |
| **atomic logs**                                    | `context-YYYY-MM-DD.log` one-liner-per-event exists (D-01)                                                                                  | unchanged; already indexed by reindex                                                                 |
| **context-adaptive journal**                       | WS-J engine: significance-gated, first-person, rolling-revision (D-05)                                                                      | new entries **incrementally indexed** into recall                                                     |
| **tiered rolling memory + compaction/compression** | model compaction L1→L2→L3 + dynamic working budget solid (D-01)                                                                             | unchanged                                                                                             |
| **web/doc/notes retrieval — perplexity**           | `RetrievalPipeline` is **single-shot, web/doc-only, gated, non-iterative**; notes recall is a *separate* block; citations don't span memory | **the centerpiece** — the new `RetrievalEngine` below                                                 |

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

### §K.0.1 — Refined MVP goal (2026-06-19, user-directed) — **REPLACES the bare "it runs" bar**

The SOUL is unchanged. What "MVP-done" *means* is sharpened by three hard-won lessons
this session (the D-39 over-claim; the Codex audio regression hidden behind a mocked
test; the realization that subsystems must become n8n-composable nodes). A node is not
MVP-done unless it satisfies **all four**:

1. **INTEGRITY — no feature broadcasts more than it delivers.** Every control/endpoint/
   claim exposed to the user (UI button, CLI verb, DONE entry) must be backed by an
   implementation as deep/robust/seamless/non-obstructive/well-integrated as it advertises,
   OR be visibly unavailable with a reason. "Done from wiring alone" and mocked-only test
   evidence do **not** count. (Drives **N-67** UI audit; re-grades D-39.)
2. **ATOMIC + NODAL — one subsystem, one objective, one contract.** Each subsystem is a
   single-responsibility service behind a stable contract (HTTP+MCP), shaped to be a node
   in the future n8n graph (N-64). MVP refactors *toward* this even before n8n exists.
   (Drives **N-66**.)
3. **USABLE LOCAL — correct *and* responsive.** Local llama.cpp must not just produce
   correct output (D-36) but serve it with real production optimizations (KV reuse/restore,
   server-side context-shift, GPU offload) so a turn is interactively usable, not minutes.
   (Drives **N-65**; ties N-32.)
4. **DEPLOYMENT-ACCEPTED — N-62 stands.** The deployment-stress sink (N-59/60/61→N-62)
   remains the acceptance gate, now gated additionally by N-63 (voice regression).

**SCOPE DECISION (user 2026-06-19, RESOLVED): N-65, N-66, N-67, N-68 are ALL hard MVP
requirements — "hard + refined".** No longer "minimum-to-satisfy"; each must reach its
refined bar for acceptance:
- **N-65** must hit the verified CPU-only target (**≥15 tok/s decode @ 32K+, pure CPU, no
  speculative decoding** — see N-65; warm/hot-KV steady-state regime).
- **N-66** atomic/nodal refactor of the subsystem set is required, not aspirational.
- **N-67** the full UI integrity matrix must be clean (every control real or honestly off).
- **N-68** the legible diagram set is a required deliverable.
Both INTEGRITY (#1) and the local-latency floor (#3) are therefore **blocking for MVP**.

**SCOPE ADDITION (user 2026-06-20): N-63 (voice), N-46 (comprehensive journal §L.2), and
N-72 (UI shared-space) are now in the MVP goal.**
- **N-65 — MVP-ACCEPTED @ native ~10 tok/s** (user: "proceed with 10 tk/s, mark refinement for
  later"). Run the prebuilt **natively on Windows ARM64, not in WSL** (native +37% over WSL,
  measured). The ≥15 push is deferred to **N-73** (native -mcpu build / AC / NPU-GPU / spec-decode E2B).
- **N-63** remediated + verified (D-46; live-mic verify pending hardware; opt-in Windows-host capture).
- **N-46** comprehensive journal shipped + verified (D-47; own-memory + web/doc, cost-bounded).
- **N-72 (NEW, MVP)** — chat responses become a **rolling stack of collaborative MDX "shared
  space" frames** (proactive updates the active frame; retrieved sources become **thumbnails with
  the citation as their title, placed between query and frame**; rich MD/MDX/mermaid/JS + static
  snapshots). The big remaining MVP build. See N-72.

**Still genuinely POST-MVP (not required):** the *full* n8n migration + composition UI
(N-64) beyond making subsystems node-shaped; advanced KV compaction (H2O/SnapKV-class)
*if* the verified target is already met without it; speculative decoding (the user reached
the target without it). The MVP diagram set (N-68) is required; an exhaustive every-edge
atlas is not.

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

| Layer                              | Local-first candidates                                              | Status                                             |
| ---------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------- |
| Main recognizer (continuous, rich) | **SenseVoice** — ASR+SER+AED+diarization, non-AR, GGUF/ONNX         | ✅ chosen                                           |
| Runtime / framework                | **sherpa-onnx** — offline STT/TTS/VAD/diar/enhance/source-sep, edge | ✅ chosen                                           |
| On-demand realtime streaming ASR   | Parakeet-TDT · Nemotron-streaming · Moonshine v2 · WhisperLiveKit   | ⏳ TBD by latency+reliability                       |
| VAD (stage-1)                      | **TEN-VAD** (lowest latency) · Silero (lightweight)                 | ⏳ candidate                                        |
| Diarization / addressee            | pyannote 3.1 · NeMo Sortformer (streaming) · SenseVoice diar        | ⏳ candidate (realtime diar still 5–15pp worse DER) |
| Expression / SER                   | SenseVoice SER · emotion2vec                                        | ↳ in main                                          |
| Environment / AED                  | SenseVoice AED · BEATs/AST/PANNs/CLAP                               | ↳ in main + scene tagger                           |
| TTS                                | Kokoro · Piper · Orpheus · XTTS-v2 · Sesame CSM                     | ⏸ DEFERRED                                         |
| Speech-to-speech                   | Moshi · pipecat · LiveKit · speech-LLM omni                         | ⏸ DEFERRED                                         |

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

#### N-45 clarification addendum — dynamic parallel cascades (2026-06-20)

> **This addendum clarifies the existing concept without replacing it.** N-45 is a
> modality-agnostic cascade abstraction instantiated independently for every
> acquisition domain. Stages are
> continuously active, asynchronous and pipelined: while one observation is in a
> later stage, newer observations are already moving through earlier stages; stages
> may maintain temporal state, issue refinements, and layer additional data onto
> already-segmented material without stopping acquisition.

**Inputs covered by the abstraction.** Acquisition is broader than microphone and
screen: audio, video/pixels, action/HID inputs, 3D/CAD/DCC software state, tool- or
workflow-initiated observations, invoked probes, device/peripheral streams, and future
modalities each receive their own parallel instance of the same modality-agnostic
cascade. The abstraction describes *how acquired information is progressively
understood* without prescribing one fixed sensor, model, or serial worker.

**Expanded stage semantics and further directions to explore.**

1. **Acquisition.** Continuously ingest the modality's native signal/state at the
   richest justified rate. For screen/visual sensing, pixels are the primary sensed
   reality. Asynchronous window, accessibility, application, tool and system events
   are secondary layers that can tag, explain or refine the pixel stream; they do not
   replace pixel-first sensing.
2. **Signal hygiene + tagging.** Calibrate/clean the signal, attach source/device/
   clock/configuration metadata, mark quality and uncertainty, and deduplicate exact
   or near-identical material without collapsing meaningful temporal continuity.
3. **Atomic segmentation/classification.** Identify modality-native sections and
   boundaries, classify/tag them provisionally, and assign each atomic section a
   stable unique time identity so every later refinement remains relative to the
   correct segment and neighboring segments.
4. **Cheap semantic extraction.** Apply the strongest available methods whose
   implementation is optimized for the modality's edge case and realtime operating
   budget. "Cheap" means cheap *at runtime for this path*, not simplistic: specialized
   SOTA detectors, trackers, compact encoders, statistical models and hardware-
   optimized inference are valid here.
5. **Short-range temporal semantic refinement + layering.** Refine segments against
   immediately preceding/following segments, track identities and boundaries, merge
   supporting metadata, and revise provisional labels while preserving the unique
   time/segment references. **Stages 1–5, as a continuously pipelined hot path, target
   realtime 60 FPS or better where the modality supplies data at that rate.**
5.1. **Longer-range same-modality semantics + information gain.** Compare the already
   processed output with prior well-processed context from the same modality across
   longer horizons. Derive information gain using complementary heuristic,
   statistical-ML, online-RL, state-space and/or meta-heuristic methods (or any other combination, as found apt later; mark for study/research to); consider multiple
   horizon/state estimates rather than reducing history to raw-frame comparison; the various levels of compressed contexts in project? here that concept will come useful.
6. **Selective specialist escalation.** When high Information Gain (again, a system for determining these built behind) -> Route slice of context, selected segments, ambiguities and/or
   high-value regions to heavier specialist systems for additional extraction,
   correction or refinement, then layer their result back onto the same segment IDs.
7. **Cross-modal arbitration and deep contextual refinement.** Converge useful
   processed outputs from independently running modality cascades; add long context,
   web, documents, previous memory/context recall and other invoked evidence; further
   refine segmentation, tags, metadata, relations and segment-relative extraction.
   Cross-modal evidence may also be opportunistically pulled into earlier refinement
   while cascades continue in parallel; stage 7 is the deep convergence point, not the
   first moment modalities are allowed to inform one another.
8. **Emit.** Only after the relevant cascade processing and arbitration is complete,
   publish the resulting observation/context event to downstream memory, proactive,
   journal, retrieval or user-turn consumers.
9. **Logs** After all this has happened, and the main system has worked its way with the content, prepared it's useful context based processing; write the objective Atomic Logs of the event (the log is supposed to be atomic -> grounded in the timestamp relevant event with context only to understand that temporally atomic event in a broader longer context and multi modality)

**Parallelism invariant.** The numbering describes increasing semantic depth and
available evidence, not stop-the-world execution order. Acquisition never waits for
semantic extraction; short- and long-horizon workers consume bounded streams on their
own cadence; specialist and cross-modal branches return refinements keyed to the
original time/segment identity. Back-pressure may reduce refinement frequency but
must not stall the acquisition path.

**Representation clarification.** The **structured frame remains the common
substrate stated above**. Modality-agnostic means the cascade stages and refinement
semantics apply to any acquisition source; it does not mean every sensor has identical
raw content. The common frame can carry source-appropriate data together with stable
time/segment identity, provenance, confidence/quality, tags, relations and refinement
lineage. Cross-modal models may add aligned representations and relations to those
frames as parallel cascades exchange useful processed evidence.

**Current model/system capability map — candidates to exploit inside the cascade,
not prescriptions for its architecture.**

| System / family                  | Cascade utility                                                                                                                                                                                                                                                                                                                                 |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SAM 2 / 2.1**                  | Streaming-memory image/video segmentation and identity propagation across frames; useful for stages 3–5 short-range visual boundaries, tracked sections and segment-relative continuity.                                                                                                                                                        |
| **SAM 3**                        | Concept-prompted detection, segmentation and tracking with persistent instance identities; useful for stage-3 section discovery, stage-4 concept tagging, stage-5 temporal mask refinement and stage-6 re-query of ambiguous/high-value concepts. The detector and memory tracker can refresh one another while the pixel cascade remains live. |
| **SAM 3D / SAM 3D Body**         | Selective reconstruction of object geometry, texture/layout or human body pose from visual input; useful as stage-6 specialist refinement and as processed evidence for 3D-software, camera and embodied/peripheral cascades.                                                                                                                   |
| **EfficientViT-SAM / MobileSAM** | Edge-oriented promptable segmentation variants for the realtime stages when full SAM-family inference is too expensive; candidate stage-3/4 boundary engines.                                                                                                                                                                                   |
| **Grounding DINO 1.5 Edge**      | Open-set, language-guided detection optimized for edge inference; candidate stage-4 semantic region tagging or prompt generation for SAM tracking. Its reported 75.2 FPS result is TensorRT/hardware-specific evidence that sophisticated open-set extraction can belong in the hot path.                                                       |
| **DINOv3 / Perception Encoder**  | Dense, reusable visual features for tracking, change measurement, classification, retrieval and spatial tasks; useful for stage-4 semantics, stage-5 local correspondence and stage-5.1 comparison against processed same-modality history.                                                                                                     |
| **Florence-2**                   | Prompt-driven captioning, grounding, detection and segmentation through one task interface; useful for selective stage-4 extraction or stage-6 refinement where richer textual/spatial output is needed.                                                                                                                                        |
| **ImageBind**                    | Aligns image, text, audio, depth, thermal and IMU representations; useful for cross-pathway scans, cross-modal similarity, retrieval and consistency signals during stages 5.1 and 7. It supplies an added aligned layer, not a replacement for modality-native cascade state.                                                                  |
| **LanguageBind**                 | Language-centered alignment for video, audio, depth, infrared and related modalities; useful when processed modality outputs need semantic comparison or retrieval through a language-addressable space at stage 7.                                                                                                                             |
| **UniBind**                      | Modality-balanced alignment spanning image, text, audio, point cloud, thermal, video and event data; directly relevant to cross-modal arbitration involving 3D/peripheral/event streams and to learning shared relation scores without collapsing native data.                                                                                  |
| **VGGT**                         | Feed-forward camera, depth, point-map, point-track and 3D reconstruction from one or many views; useful for stage-4/6 visual-to-3D extraction and consolidation of camera or 3D-software cascades.                                                                                                                                              |
| **InfiniteVGGT**                 | Causal long-stream 3D geometry with bounded rolling memory; relevant to stage-5.1 long-range same-modality geometry and persistent 3D scene/peripheral tracking.                                                                                                                                                                                |

**Research references for the capability map.**
- SAM 3: <https://arxiv.org/abs/2511.16719>
- SAM 2: <https://arxiv.org/abs/2408.00714>
- SAM 3D: <https://arxiv.org/abs/2511.16624>
- EfficientViT-SAM: <https://arxiv.org/abs/2402.05008>
- MobileSAM: <https://arxiv.org/abs/2306.14289>
- Grounding DINO 1.5 Edge: <https://arxiv.org/abs/2405.10300>
- DINOv3: <https://arxiv.org/abs/2508.10104>
- Perception Encoder: <https://arxiv.org/abs/2504.13181>
- Florence-2: <https://arxiv.org/abs/2311.06242>
- ImageBind: <https://arxiv.org/abs/2305.05665>
- LanguageBind: <https://arxiv.org/abs/2310.01852>
- UniBind: <https://arxiv.org/abs/2403.12532>
- VGGT: <https://arxiv.org/abs/2503.11651>
- InfiniteVGGT: <https://arxiv.org/abs/2601.02281>

### §L.2 — Comprehensive autonomous journal `[x]` MVP slice DONE 2026-06-20 → D-47 (N-46) — **PULLED INTO MVP (user 2026-06-20)**
> **Status: MVP slice shipped (D-47).** Per-entry research now folds in own durable memory
> (default-on, local) + web/doc over the unified engine (gated+throttled), multi-seed, cost-bounded
> — replacing the single-seed web-only seam. Remaining post-MVP refinement: a model call to *choose*
> the queries, and routing through the N-47 Perplexity-grade engine. Original concept text below.
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

### §L.7 — Atomic-services + n8n workflow substrate `[concept]` (N-64) *(user 2026-06-19, scope extension)*
*Direction (eventually/later, NOT MVP): stop hardcoding each subsystem's workflow in
Python and instead (1) factor every capability into an **atomic service** behind a stable
contract, then (2) **compose them as graphs/workflows in self-hosted n8n (community ed.,
local)** so new looped/feedback workflows can be integrated / developed / composed
**on the fly** — deep research, NotebookLM-like, Claude-Research-like, DeepThink/Qwen-
Deep-Think-like, an OpenCode-class coding-agent harness, etc. The point is not coding per
se but a **general capacity for any looped/feedbacked workflow**. This concretizes N-50
Phase-2's "workflow-orchestration (n8n/LangGraph-class)" bucket into the chosen substrate
and extends N-17 (L6 tools/MCP/skills) + N-45 (perception cascade) + N-25 (effectors).*

**Two layers (the core of the concept).**
- **Atomic capability services** (each independently testable, single-responsibility,
  contract-first):
  - *perception*: per-sensor capture→consolidate→categorize→extract→info-gain services
    (the N-45 cascade), **multi-stage / parallel / realtime / async, N-modality-extensible**;
  - *externalization*: atomic-log writer, contextual rolling-revision journal, tiered
    rolling memory + compaction/compression, **KV-cache management** (incl. doc/web KV
    caching) — the write-side complexities currently tangled in kernel/ctx code;
  - *tool loops* (each with its own dynamic loop): tasks, reminders, notes, scheduled
    tasks, web retrieval, doc retrieval, ranking/re-ranking, semantic search, associative
    memory, associative graph, and a **PDA-like (stack/push-down) I/O channel for the
    model** (structured, resumable tool I/O rather than flat single-shot calls).
- **Orchestration graphs (n8n).** The above services are nodes; n8n wires them into
  workflows (the research/NotebookLM/DeepThink/coding-harness systems above), with loops,
  branches, feedback, and human-in-loop **only at finalization** (N-50). On-the-fly
  composition = adding/editing an n8n workflow, not a code change.
- **Workflow-composition UI (user 2026-06-19).** A **separate, later UI** to **compose /
  select / toggle workflows and connect assemblies of workflows** on the fly — LAWRENCE
  surfaces its own n8n workflow library as a first-class user surface (enable/disable a
  workflow, wire one workflow's output into another, compose assemblies). Sibling to the
  WS-U UI track (a `web/variants/` surface or dedicated window) reading the n8n workflow
  registry. The user-facing half of "on-the-fly composable"; deferred with N-64; depends on
  the service contract + N-49/N-50 UI methodology + N-68 diagram/view work.

**Load-bearing design boundaries (flagged now so planning doesn't trip on them later):**
1. **n8n is NOT the realtime path.** n8n's per-execution / JSON-between-nodes model is
   wrong for the 60-FPS perception hot loop (N-45). Boundary: the **hot sensor cascade
   stays native** and merely **emits events** (webhook/queue) that n8n *subscribes* to;
   n8n owns the coarse-grained, second+-scale workflows (research, retrieval graphs,
   journal/memory orchestration), not the frame loop.
2. **Local-first / privacy is the hard gate (D-33, [[lawrence-local-first]]).** Self-hosted
   n8n is local-OK, but it makes adding a cloud node trivial — every workflow MUST route
   through the same `PolicyState`/redaction boundary; **no personal-data workflow defaults
   to a cloud node.** Personal-data services stay off `BACKGROUND_ROLES`-style cloud paths.
3. **Single-writer + provider-seam invariants survive (I1, I3).** n8n workflows call the
   **memory/journal *service API*, never the store directly** (preserves the single-writer
   contract); model/provider selection stays behind the `model.py` role seam — n8n picks a
   *role*, not a provider. The atomic services are the invariant boundary; n8n is above it.
4. **Small-model-drivable (N-50 cross-cut).** Workflow steps that invoke a model must work
   with a local gemma-4-class tool-caller; frontier models are an enhancement.
5. **Contract substrate.** Atomic services likely exposed as **HTTP + MCP servers** (reuse
   the existing bridge endpoints; MCP makes them both n8n-composable AND directly model-
   tool-callable) — one contract serves orchestration and tool-calling.

**Why it fits the SOUL.** A watcher-assistant whose perception/memory/tools are atomic,
inspectable services composed by editable graphs is *more* local-first, *more* swappable
(workflows replaceable like the model/UI already are), and supports the §L feature vision
(N-46 journal, N-47 retrieval, N-49 workspace) as composed workflows rather than bespoke code.

**Ambiguity register (all deferred — concept only).**
- n8n vs LangGraph-vs-Temporal-vs-custom for the *durable* loop engine `intentionally-open`
  (n8n is the user's current pick; revisit at Phase-2 against realtime/local/embeddability).
- Service contract = HTTP vs MCP vs both `resolve-before-start` (lean: MCP+HTTP dual).
- Migration order `crystallizes-during` — which subsystem gets atomized + lifted to n8n
  first (lowest-risk: a tool loop like web/doc retrieval; NOT the realtime sensor path).
- How n8n state interacts with the frozen `ContextSnapshot` (D-30) / KV lifecycle (D-37)
  `resolve-before-start` of the first migration.

**Edges.** `N-64 --concretizes--> N-50` (Phase-2 orchestration bucket) · `N-64 --extends-->
N-17` (L6 tools/MCP/skills become the service contract) · `N-64 --consumes--> N-45`
(perception services are the realtime producers it subscribes to, never wraps) ·
`N-64 --constraint--> N-25` (effector workflows still gate through confirm/audit) ·
`N-64 --gated-by--> D-33` load-bearing (privacy boundary) · `--gated-by--> I1/I3`
load-bearing (single-writer + provider seam). **Strictly post-MVP; nothing built.**

---

> **Cross-references for whoever plans §L next.** N-45 supersedes the heuristic trigger
> in N-07/N-33 ([[lawrence-sensor-decoupling]]); N-47 graduates the "no-ANN" call in
> D-20/N-02 and raises the §J engine's quality bar; N-48 redefines D-26/§J.6 "enforced
> citations" and depends on N-47; N-49/N-50 extend the WS-U UI track (N-09 seam done =
> D-23; N-10 classic refactor is the nearest existing surface) and depend on N-47/N-48
> for grounding + scroll-to-chunk. DONE.md is intentionally untouched — nothing here is
> built yet.

---

## §M — Live-defect remediation batch (2026-06-19) — **REVISED CURRENT STATE**

*Defects observed in a live run (user, with screenshot): triple/blocky/repetitive voice
bubbles + double "Sources" block in chat; audio clipped at the start and the end of an
utterance; capture needs long continuous speech and chokes on short atomic commands;
"Rebuild popup" from the launcher restarts the whole stack (bridge + model); the global
hotkey still does not summon. These are **fixes to the running MVP**, planned here first
then implemented. IDs N-51…N-58. **STATUS (revised 2026-06-19 §M.5):** N-52/N-56/N-57/N-58
landed (→ D-40/41/42 + the chat-render half of D-39); **N-51/N-53/N-54 RE-OPENED as N-63**
(D-39 over-claimed — see §M.5); N-55 still open. Distinct from §L: N-53/N-54 are the
**tactical** capture loop that §L.1 (SenseVoice×sherpa-onnx) may later supersede behind
the same observer contract.*

### §M.1 — Stage 1 BUILD snapshot

**Triage.**
- `[N-51] centrality:M ambiguity:L` — rebuild lifecycle boundary.
- `[N-52] centrality:M ambiguity:L` — single voice/source rendering path.
- `[N-53] centrality:H ambiguity:M` — continuous capture and utterance segmentation.
- `[N-54] centrality:H ambiguity:M` — voice pending/auto-submit gate.
- `[N-55] centrality:M ambiguity:H` — Windows-global summon replacement.
- `[N-56] centrality:M ambiguity:L` — truthful bottom telemetry.
- `[N-57] centrality:M ambiguity:L` — stable feed plus chat lifecycle.
- `[N-58] centrality:H ambiguity:L` — current-context grounding precedence.

### ~~N-51 (RBLD) — Rebuild must compile only~~ `✅ → D-39`
- **Defect:** launcher *Rebuild* → `lk rebuild` → `cmd_rebuild` ([services/lk/ctl.py](../services/lk/ctl.py)) ends with
  `_desktopctl("restart")`, and the `restart)` case in [desktopctl.sh](../apps/desktop/scripts/desktopctl.sh) does
  `stop popup+bridge → start_bridge → start_app` — so rebuilding the **UI** tears down and
  reloads the **bridge + model** (the "start all"). The web/ is embedded in the Tauri binary;
  only the popup binary needs relaunching. Bridge/model are untouched by a web/Rust rebuild.
- **Implemented `[revised: user clarified rebuild means rebuild only]`:** `cmd_rebuild`
  delegates only to `desktopctl build`; no popup, bridge, kernel, observer, or model
  process is started/stopped/restarted. Two real release builds preserved popup and
  bridge PIDs. See D-39.

### ~~N-52 (CHAT) — De-bloat chat voice/source rendering~~ `✅ → D-39`
- **Defect A (triple voice bubble):** one utterance fires **two** SSE context events —
  `kind:"audio"` (→ `addVoiceUserMessage(..., key="audio:"+t)`, badge *audio transcript*) and
  `kind:"voice"` (→ `key="event:"+t`, badge *spoken audio*) in
  [variants/classic/app.js](../apps/desktop/web/variants/classic/app.js) `connectEvents` —
  whose different key **prefixes** defeat `seenVoiceTurns` dedup, **plus** the enqueued turn
  renders a third user bubble. ⇒ 3 bubbles for one thing.
- **Defect B (double "Sources"):** the model's answer text embeds its own `Sources:` markdown
  list **and** the UI renders source cards/strip from `sources`/`citations` ⇒ two stacked
  Sources blocks with differently-numbered, overlapping entries.
- **Fix:** (1) **single voice path** — in voice-query mode the backend (N-53) emits **one**
  evolving entry; the UI keys all voice dedup on the *normalised transcript only* (no
  `audio:`/`event:` prefix) and never double-renders the heard text as both a context event
  and a turn bubble. (2) **one Sources block** — strip a model-emitted trailing `Sources`/
  `References` list from the answer body when the system will render its own cards (or render
  exactly one, preferring the structured `sources`/`citations`). This is the near-term shim
  for N-48 ("system formats citations, model only selects"). **Acceptance:** one utterance →
  one user bubble; one answer → at most one Sources strip; gate green (`stress_ui.py`).

### ~~N-53 (AUDSEG) — Utterance-segmented streaming capture~~ `✅ → D-39`
- **Defect (issues 1/5 + follow-up):** [obs/audio.py](../services/lk/obs/audio.py) records
  back-to-back **fixed 4 s windows** (`WINDOW_SECONDS=POLL_INTERVAL=4`), transcribes each in
  isolation, gates on `audio_gate` (word-count ≥ 3 + Jaccard). Consequences:
  - **onset clipped** — recording starts at the tick, not at speech start; a word spanning the
    boundary is cut. **tail clipped** — speech after the last full window is dropped on the
    silence flush.
  - **repetition** — a sentence straddling two windows transcribes partially in each.
  - **no atomic commands** — `audio_min_words ≥ 3` kills short commands; "coalesce while busy"
    drops utterances; nothing accumulates.
  - **no streaming** — each window is a new entry, never an evolving one.
- **Fix — utterance loop with VAD boundaries + pre-roll + hangover:**
  1. **Continuous short frames** (e.g. ~0.3–0.5 s reads) feeding a small **rolling pre-roll
     ring buffer** (~0.5–1.0 s) so the captured utterance includes audio *before* the VAD
     trip → **no onset clip**.
  2. **VAD-gated segmentation:** speech onset (energy/VAD over the noise floor) opens an
     utterance; **trailing-silence hangover** (configurable, ~0.6–1.0 s) before close →
     **no tail clip**, and a short atomic command is a complete utterance on its own.
  3. **Streaming partials:** transcribe the growing utterance incrementally and emit
     **partial → partial → final** updates of **one** UI entry (id-keyed), not N bubbles.
  4. **Backend-swappable:** keep faster-whisper now; isolate capture/segmentation from the
     ASR call so §L.1's SenseVoice×sherpa-onnx (+ streaming ASR) drops in behind the same
     interface. Keep the silence/`no_speech_prob`/`avg_logprob` anti-hallucination guards.
  5. **Relax the gate** for segmented utterances: a VAD-confirmed segment need not clear
     `audio_min_words` (atomic commands pass); keep Jaccard dedup against the *previous final*
     only (not per-window).
  - **New config (round-trips via `lk config`, GUI==CLI):** `audio_preroll_ms`,
    `audio_hangover_ms`, `audio_frame_ms`, `audio_max_utterance_s` (hard cap),
    `audio_partial_interval_ms`. All optional, lazy, default-on, degrade gracefully (I4).
- **Acceptance:** a 1–2 word command is captured whole; a long sentence is one entry with no
  start/end clipping and no internal repeat; streaming partials visibly update one bubble.

### ~~N-54 (SILTO) — Silence-timeout voice query gate~~ `✅ → D-39`
- **Goal (issue 6):** after an utterance closes (N-53) and a **configurable** silence
  timeout elapses, the pending transcript is auto-submitted as a (proactive) query —
  **but** the UI first shows a **countdown badge/notification** that is **Dismiss** (cancel,
  drop it) / **Proceed now** (fire immediately) / (let it) **time-out → auto-fire**.
- **Fix:** backend holds the closed-utterance transcript in a pending slot with a timer;
  emits an SSE `voice_pending` event (`{transcript, timeoutMs}`); on timeout (or a `proceed`
  control) enqueues the turn, on `dismiss` drops it. UI renders the countdown chip near the
  composer with the three affordances. **New config:** `voice_silence_timeout_ms`
  (minimum/default 10000), `voice_autoquery` (on/off). **Acceptance:** speak → badge
  counts down for at least 10 seconds → auto-fires; Dismiss cancels; Proceed fires now.

### ~~N-56 (TEL) — Truthful bottom metrics and trajectory~~ `✅ → D-40`
- Per-subsystem chips now carry `ok|active|warn|fail` state, including explicit
  failure highlighting. Session text-token use is estimated transparently and can
  be reset. The compact trajectory reports `user|proactive › stage · context use`.
- **Alignment:** serves the SOUL by exposing real system state without adding a
  second telemetry subsystem. Browser state remains presentation-only.

### ~~N-57 (CHATCTL) — Stable feed and durable chat lifecycle~~ `✅ → D-41`
- Streaming follows only when the user was already near the feed bottom; a query no
  longer steals a manually positioned viewport. Existing `/chats` routes now expose
  Clear/new, Save MDX, Archive, and Restore in the History surface.
- **Deferral:** hard-delete UI remains intentionally deferred; archive is reversible
  and safer. Re-entry requires a specific user need for irreversible deletion.

### ~~N-58 (CURGROUND) — Current-first model interpretation~~ `✅ → D-42`
- Context storage, headers, ordering, logs, journal, memory, and retrieved evidence
  are unchanged. Only analysis/response/retrieval prompts now enforce: current request,
  newest active-chat turns, and recent perception are authoritative; older material
  explains trajectory and cannot override newer evidence.
- **Alignment:** task-local grounding, current code attachment, and SOUL all agree.
  This preserves long-running continuity without answering from stale state.

### N-55 (HOTKEY) — Global hotkey: diagnosis + **blank-slate reimplementation** plan `[ ]` — plan + diagnosis this session
- **Why it fails (root cause, confirmed by code + web research 2026-06-19):** Tauri's
  `global-shortcut` plugin on **Linux is X11-only**, and under **WSLg** the app is an
  Xwayland client whose X11 grab **only fires while a WSLg window has focus** — so it is *not*
  a global summon when the user is in a Windows app. (Wayland has no global-shortcut protocol;
  GitHub `tauri-apps/global-hotkey#28`.) The repo already knows this: `ensure_windows_hotkey`
  in [desktopctl.sh](../apps/desktop/scripts/desktopctl.sh) launches
  [host/windows/GlobalHotkey.ps1](../apps/desktop/host/windows/GlobalHotkey.ps1) on the
  **Windows** side (`RegisterHotKey` WinAPI) → it connects to the in-WSL **control socket**
  `127.0.0.1:8767` (WSL2 localhost forwarding) → sends `show`/`toggle`. So failure is in that
  cross-boundary chain, candidates: (a) `powershell.exe` not on PATH / blocked from WSL;
  (b) the hidden `Start-Process` PS host not surviving; (c) `Ctrl+Shift+L` already held by
  another Windows app → `RegisterHotKey` returns false and the script exits silently;
  (d) localhost forwarding off (mirrored networking / firewall) so the socket is unreachable;
  (e) the PS1 self-terminates ~30 s after a transient socket miss at startup.
- **Possible ways to implement (researched):** (1) **Windows-host RegisterHotKey** helper
  (current) → socket — fragile, depends on a live PS host; (2) **AutoHotkey** script →
  same socket — robust if AHK present; (3) a **tiny bundled compiled Windows tray helper**
  (C#/Rust, auto-started, single source of truth) → socket — most reliable, no PS dependency;
  (4) in-WSL Tauri shortcut — only when focused (keep as a *focused-window* fallback only);
  (5) Wayland/compositor binding — N/A under WSLg.
- **This session's deliverable (per user "find why, search ways, add to plan with total
  re-implementation from scratch"):** the diagnosis above + this plan, **plus** a runtime
  probe so the failure is observable (extend `lk doctor`/`desktopctl doctor`: is the control
  socket listening? is `powershell.exe` reachable? is a `LAWRENCE-GlobalHotkey` PS process
  alive? did `RegisterHotKey` succeed?). **Blank-slate reimplementation (next, not a patch on
  the old path):** a single bundled Windows helper (option 3, AHK = option 2 fallback) that
  is installed/
  started/stopped by the launcher lifecycle; the in-WSL shortcut stays only as the
  focused-window fallback. It owns hotkey registration + retry and reports status back over
  the socket. Keep the control-socket contract (`show|hide|toggle`) unchanged.
- **Acceptance (reimpl):** pressing the hotkey from *any* Windows foreground app summons the
  popup within ~150 ms; `lk doctor` reports the hotkey chain healthy; survives app
  restart/rebuild.

**Execution pathway.** Keep the existing `show|hide|toggle` control-socket contract.
The Windows registration helper and WSL lifecycle integration can be built in parallel,
then converge in one real Windows-host acceptance pass. The host pass is the hard dependency.

**Triple-anchor alignment.**
- Task-local: make summon genuinely global and observable.
- Implementation-scope: attach to the existing control socket and launcher lifecycle.
- Ideation-soul: reduce access friction without coupling cognition to desktop hosting.

**Deferral.** Hard-deferred until a Windows host can build/run and verify registration,
forwarding, restart survival, and foreground-app behavior. Re-entry: a real Windows-host
test session is available.

**Implementation specifics.** Prefer one small Windows-native helper using
`RegisterHotKey`, one retry loop, and the existing TCP command. No tray UI, installer
framework, or secondary protocol until the minimal helper proves reliable.

**Ambiguity register.**
- `resolve-before-start`: C# versus Rust helper, based on installed host toolchain.
- `crystallizes-during`: startup mechanism and localhost-forwarding behavior.
- `intentionally-open`: optional tray/status UI after core acceptance.

### §M.2 — Execution edges

```text
[N-53] --{dependency}--> [N-52]
  Weight: load-bearing
  Meaning: one utterance identity enables one evolving voice bubble.
  Break condition: changing segmentation IDs requires the UI dedup path to change.

[N-53] --{dependency}--> [N-54]
  Weight: load-bearing
  Meaning: the silence timer starts only after a segmented utterance closes.
  Break condition: replacing utterance completion requires re-binding the pending gate.

[D-39] --{constraint}--> [N-45]
  Weight: significant
  Meaning: future streaming ASR must preserve the observer callback contract.
  Break condition: an incompatible ASR interface requires bridge and UI voice rewrites.

[D-39] --{dependency}--> [N-55]
  Weight: incidental
  Meaning: reliable global summon improves access to the repaired runtime.
  Break condition: removing the popup-control socket changes N-55's attachment point.

[D-40] --{partial-completion}--> [N-49]
  Weight: significant
  Meaning: compact truthful telemetry is done; broader UI hierarchy remains.
  Break condition: replacing the bottom strip requires retaining equivalent health truth.

[D-42] --{constraint}--> [N-48]
  Weight: load-bearing
  Meaning: grounding improvements must keep current evidence above historical trajectory.
  Break condition: any retrieval redesign that lets stale memory override current state regresses D-42.

[D-41] --{partial-completion}--> [N-49]
  Weight: significant
  Meaning: scroll stability and chat lifecycle are complete pieces of the larger UI track.
  Break condition: a UI redesign must preserve feed position and durable chat controls.
```

### §M.3 — Stage 2 AUDIT findings

- **Zero-incoming N-nodes:** N-55 is genuinely independent of D-39’s voice internals,
  but depends incidentally on its popup-control attachment; that edge is now explicit.
- **Zero-outgoing D-nodes:** D-39/D-40/D-41 initially appeared settled. `[revised:
  added D-39→N-45/N-55, D-40→N-49, D-41→N-49, D-42→N-48]`.
- **Cycles:** none. Completed remediation flows outward only to open post-MVP work.
- **Diamond:** D-40 and D-41 independently feed N-49; they converge at the future UI
  track and are now marked.
- **Alignment re-check:** N-53, N-54, and N-58 remain coherent. N-58 initially risked
  changing context structure; `[revised: interpretation-only prompt precedence]`.
- **Conflict:** N-54 still documented a 2500 ms default after runtime changed to a
  10000 ms minimum. `[revised: acceptance and config text corrected]`.
- **Load-bearing integrity:** D-42→N-48 endpoints exist and the break condition is
  testable through the current-grounding contract test.
- **Unresolved:** `?:open` N-55 requires a real Windows-host execution pass before
  selecting or validating the replacement helper.

### §M.4 — Stage 3 REVISE + FINALIZE

**Current executable frontier:** N-55 (hotkey). ~~N-63~~ DONE 2026-06-20 → D-46. Deployment
spine now: **N-59/N-60/N-61 → N-62** (N-63 unblocked N-60's voice lane; N-65 levers done → D-45).
N-52/N-56/N-57/N-58 (→ D-40/D-41/D-42 and the chat-render half of D-39) remain
complete; **N-51 + N-53 + N-54 are RE-OPENED** by the §M.5 regression audit — D-39's
voice/rebuild claims do not match the running code. N-45/N-48/N-49 remain broader
post-MVP tracks, not implicit continuation work.

### §M.5 — REGRESSION AUDIT (2026-06-19, post-Codex audio fix) — **D-39 RE-OPENED**

*User live report after a Codex audio fix: "voice unavailable", "Proactive / Voice /
Transcription, none of them working at all", "the rebuild process auto launches all
server/kernel/ui/system — rebuild should only do rebuild." A code read confirms D-39's
"live-verified" claims are **not** true of the current tree. D-39 is downgraded to
REGRESSED in DONE.md §0; the chat-render/telemetry/grounding halves (N-52/56/57/58 →
D-40/41/42) are unaffected. Remediation = **N-63** below.*

#### N-63 (VOICE-FIX) — Voice/runtime regression remediation `[x]` DONE 2026-06-20 → D-46 (live-mic verify pending hardware) — FULL — re-opens D-39 (N-51/N-53/N-54)
**Verified root causes (read this session, not speculation):**
1. **Rebuild is not compile-only.** [ctl.py](../services/lk/ctl.py) `cmd_rebuild` ends with
   `_desktopctl("restart-popup")`; that stops+relaunches the popup (and the popup boot
   chains the bridge/observers back up) — contradicts N-51, the D-39 entry, and the
   launcher hint "compile only; start or restart nothing" ([actions.py](../services/lk/launcher/actions.py)).
2. **VAD gate too strict for WSLg.** [obs/audio.py](../services/lk/obs/audio.py) defaults
   `LK_AUDIO_VAD_DB=-45`, but the file's own notes record that **-42 rejected real speech**
   on the WSLg RDP virtual mic and **-55** was needed. At -45 the per-frame gate
   `_rms_db_bytes(chunk) > vad_db` rarely fires → no utterance opens → voice/transcription/
   proactive are all silent (matches "none working").
3. **Transcription runs inline in the capture loop.** `_finish_utterance` / partials call
   whisper synchronously inside `_capture_loop`; while it decodes (seconds, CPU), nothing
   reads `proc.stdout`. The OS pipe holds ~2.05 s of PCM → overflow → dropped audio + the
   loop blocks (re-introduces the "blocky / cut-off / needs repetition" symptom).
4. **Gain-normalization silently dropped + dead code.** `transcribe()` no longer normalizes;
   `_normalize_gain`/`rms_db`/`SILENCE_DB` are now referenced only in a comment — a real
   degradation on the documented-quiet WSLg mic, dressed up as an "opt-in" that nothing can
   invoke.
5. **Short non-empty read discards the open utterance.** `if not chunk or len(chunk) <
   frame_bytes: break` drops an in-progress `buf` without `_finish_utterance` → tail loss on
   recorder churn (defeats the "no tail clip" goal).
6. **The green test hides all of it.** `stress_sensors.py` §F mocks `_rms_db_bytes`,
   `transcribe`, AND `audio_gate`, so `make check` passing exercises only loop bookkeeping —
   not the threshold, decode, or stall. False confidence.

**Fix (acceptance):**
- `cmd_rebuild` is **compile-only** — returns after `desktopctl build`; starts/stops/
  restarts nothing (the relaunch becomes a separate explicit `lk restart`); the running
  bridge/model/popup PIDs are unchanged across a rebuild. (closes N-51 for real)
- VAD default lowered to the documented working value (**-55**, single source of truth with
  the windowed path) and made the live value; a short atomic command and a longer sentence
  both open→close one utterance each with no onset/tail clip. (N-53)
- Transcription moved OFF the capture thread (worker/queue) so `proc.stdout` is drained
  continuously; capture never blocks on decode. (N-53)
- Gain path resolved: either re-wire `_normalize_gain` on VAD-confirmed speech or delete the
  dead symbols — no comment-only "feature." (N-53)
- Short read finalizes the open utterance before reopening. (N-53)
- A **non-mocked** decode smoke (real `_rms_db_bytes` over a known wav; one fixture utterance
  → one transcript) replaces/augments the fully-mocked §F. (test gate)
- Live cue test: user speaks; partials stream to one bubble; the silence badge appears;
  proceed/dismiss/auto-fire works. (N-54, currently unreachable because step 2/3 starve it)

**Edges.** `N-63 --reopens--> D-39` load-bearing · `N-63 --dependency--> N-60`
load-bearing (live voice endurance can't be honestly stressed until capture actually
fires) · `N-63 --constraint--> N-45` significant (the worker/observer seam must stay
swappable for SenseVoice×sherpa-onnx). Order within §M: **N-63 → N-55**.

---

## §N — Deployment stress revalidation (2026-06-19) — **PLANNED, NOT RUN**

> **SOUL:** LAWRENCE is a local-first watcher-assistant whose value is continuous,
> grounded operation across perception, memory, autonomy, and safe action. Deployment
> is acceptable only if that loop survives sustained use and lifecycle disruption,
> not merely a single successful request.
>
> **Scope:** Revalidate the old completed MVP/remediation nodes with actual runtime
> stress before calling the current tree deployable. Existing completion records stay
> in DONE.md; this section adds a current deployment proof boundary. No implementation
> or test execution is authorized by this planning update.

### §N.1 — Stage 1 BUILD

**Triage.**

```text
[N-59] centrality:H ambiguity:M — kernel/model/retrieval/agency load stress
[N-60] centrality:H ambiguity:M — live vision/audio/voice endurance stress
[N-61] centrality:H ambiguity:H — desktop lifecycle/UI/Windows-host stress
[N-62] centrality:H ambiguity:L — terminal deployment acceptance
```

### N-59 (CORE-STRESS) — Sustained runtime and model-path stress `[ ]`

**Pathway.** Parallel lanes exercise cloud and local turns, retrieval, context
freezing, cancellation, autonomy, policy, agency proposals, and KV restart. They
converge on one report containing latency percentiles, queue high-water mark, memory
growth, error count, duplicate count, and process/port cleanup. This node does not
test microphone, visual UI, or installer behavior.

**Triple-anchor.**
- Task-local: prove the kernel remains correct under repeated and overlapping work.
- Implementation-scope: reuse existing `make *-smoke` entrypoints and bridge metrics;
  add one orchestrator script whose sole job is repeated runtime stress.
- Ideation-soul: continuous cognition is not credible if queues grow, context drifts,
  memory corrupts, or provider replacement fails under repetition. Coherent.

**Deferral.** No hard deferral beyond a configured cloud key and installed local
model. Completing N-59 unblocks N-62's cognition lane.

**Implementation specifics.** Standard-library process/HTTP/threading tooling is
sufficient. Target: bounded batches rather than unlimited load—at least 50 mixed
turns, cancellation during active work, repeated retrieval, 10 autonomous cycles,
three bridge restarts, and three compatible/incompatible KV restarts. Assert zero
torn durable records, zero stuck jobs, bounded queue depth, clean shutdown, and no
silent provider fallback. Report p50/p95/max; do not add a benchmark framework.

**Ambiguity register.**
- `resolve-before-start`: exact concurrency ceiling based on the one-slot inference gate.
- `crystallizes-during`: latency thresholds for local CPU versus cloud.
- `intentionally-open`: provider network variance; correctness remains mandatory.

### N-60 (SENSOR-STRESS) — Live perception and voice endurance stress `[ ]`

**Pathway.** Vision and audio run concurrently through repeated foreground changes,
speech/silence boundaries, short commands, long utterances, partial updates, dismiss,
proceed, and auto-submit. The lane converges on observer health, transcript identity,
capture latency, dropped-event count, CPU/RAM trend, and clean observer shutdown.

**Triple-anchor.**
- Task-local: prove proactive/vision/transcription/voice survive real continuous input.
- Implementation-scope: attach to D-29/D-39 observer and pending-voice contracts;
  retain deterministic replay as a control, but require non-silent hardware evidence.
- Ideation-soul: perception is the watcher-assistant's input boundary. Coherent.

**Deferral.** Hard-deferred only when no real microphone/display host is available.
Completing N-60 unblocks N-62's perception lane.

**Implementation specifics.** One sensor stress script, no new sensor abstraction.
Run at least 30 minutes with scripted screen changes and a labeled audio set plus live
microphone speech. Assert no onset/tail clipping in labeled samples, one utterance
identity per query, timeout never below 10 seconds, bounded spool/temp files, no
observer death, and no duplicate proactive turn from one utterance.

**Ambiguity register.**
- `resolve-before-start`: labeled audio fixture and acceptable word-error threshold.
- `crystallizes-during`: host-specific silence floor.
- `intentionally-open`: ambient hardware quality, recorded with the result.

### N-61 (DESKTOP-STRESS) — Desktop lifecycle, feed, and native-host stress `[ ]`

**Pathway.** Three tracks run in parallel: repeated build/rebuild/start/stop/restart;
high-churn feed/chat/telemetry interaction; Windows ARM64 build/install/start and
cross-boundary bridge recovery. They converge in one real Windows-host pass. N-55
global hotkey remains independently open and is not allowed to hide failures in the
rest of the deployment path.

**Triple-anchor.**
- Task-local: prove the shipped desktop stays stable through realistic lifecycle and UI churn.
- Implementation-scope: reuse `desktopctl.sh`, the DOM harness, and Windows host scripts.
- Ideation-soul: the assistant must remain reachable and truthful without destabilizing
  its cognition services. Coherent.

**Deferral.** The Windows lane is hard-deferred until run on the actual Windows ARM64
host. Completing N-61 unblocks N-62's packaging/interaction lane.

**Implementation specifics.** Keep separate single-purpose scripts: lifecycle stress,
DOM/feed stress, and Windows host acceptance. Minimums: 20 compile-only rebuilds with
unchanged service PIDs; 25 restart cycles with no duplicate listeners; 500 streamed
messages with fixed manual scroll anchor; 100 chat create/archive/restore cycles;
bridge loss/recovery while the popup remains honest; native install into a clean
`%LOCALAPPDATA%\LAWRENCE`, launch, restart, update-over-install, and uninstall-by-
directory removal. Record peak memory and orphan processes.

**Ambiguity register.**
- `resolve-before-start`: whether MVP distribution is portable install directory or
  signed installer; choose portable directory unless the user requires signing.
- `crystallizes-during`: Windows localhost-forwarding behavior.
- `intentionally-open`: N-55 hotkey helper implementation; report it separately.

### N-62 (DEPLOY-ACCEPT) — Current-tree MVP deployment acceptance `[ ]`

**Pathway.** Diamond convergence: N-59 core stress, N-60 sensor endurance, and N-61
desktop/host stress must all pass against the same commit and configuration manifest.
N-62 only collects evidence and declares pass/fail; it does not repair failures.

**Triple-anchor.**
- Task-local: establish one reproducible deployable build and evidence bundle.
- Implementation-scope: supersedes D-38 only as the current deployment proof boundary,
  not as an implementation rewrite.
- Ideation-soul: proves the complete watcher loop remains useful and safe under sustained
  operation on the intended host. Coherent.

**Deferral.** Hard-deferred until N-59, N-60, and N-61 pass. Completion makes the MVP
ready for limited deployment; failures return only the affected lane to the frontier.

**Implementation specifics.** Store commit, config hash, dependency versions, model
profile, host details, test commands, measured results, and known degraded capabilities.
Acceptance requires no unresolved data corruption, stuck process, false UI health,
silent sensor death, or bypassed confirmation. N-55 may remain a declared access
limitation only if manual summon works and the user accepts it.

**Ambiguity register.**
- `resolve-before-start`: target deployment audience—single-user current machine is
  assumed for MVP.
- `intentionally-open`: code signing and auto-update remain post-MVP unless required.

### §N.2 — Stage 1 edge set

```text
[D-28,D-30,D-31,D-32,D-33,D-34,D-36,D-37] --{constraint}--> [N-59]
  Weight: load-bearing
  Meaning: previously smoke-verified cognition contracts must survive repeated mixed load.
  Break condition: changing any runtime contract changes the stress scenario and invalidates its report.

[D-29,D-32,D-39] --{constraint}--> [N-60]
  Weight: load-bearing
  Meaning: sensor, proactive, and repaired voice paths define the live endurance target.
  Break condition: observer or utterance identity changes require sensor stress fixtures to change.

[D-28,D-35,D-37,D-40,D-41] --{constraint}--> [N-61]
  Weight: load-bearing
  Meaning: lifecycle, UI truth, continuity, telemetry, and chat behavior must survive host churn.
  Break condition: changing build/start/bridge/feed contracts invalidates desktop stress evidence.

[N-59] --{dependency}--> [N-62]
  Weight: load-bearing
  Meaning: deployment cannot pass without sustained cognition correctness.
  Break condition: any stuck job, corruption, unsafe action, or unexplained fallback fails acceptance.

[N-60] --{dependency}--> [N-62]
  Weight: load-bearing
  Meaning: deployment cannot pass without live non-silent perception endurance.
  Break condition: clipping, duplication, silent observer death, or unbounded capture files fails acceptance.

[N-61] --{dependency}--> [N-62]
  Weight: load-bearing
  Meaning: deployment cannot pass without repeatable desktop lifecycle and host installation.
  Break condition: duplicate processes, false health, scroll regression, or failed clean host install fails acceptance.

[D-38,D-39,D-40,D-41,D-42] --{partial-completion}--> [N-62]
  Weight: significant
  Meaning: accepted MVP behavior and recent repairs are the baseline revalidated by the new deployment gate.
  Break condition: modifying those behaviors requires rerunning all affected N-62 lanes.
```

### §N.3 — Stage 2 AUDIT findings

- **Zero-incoming N-nodes:** none. N-59/N-60/N-61 inherit explicit completed
  contracts; N-62 depends on all three.
- **Zero-outgoing D-nodes:** D-38 was previously terminal. `[revised: D-38 now has a
  partial-completion edge to N-62 because implementation acceptance is not current
  deployment stress proof]`.
- **Cycles:** none. Completed nodes feed stress lanes; stress lanes converge once at N-62.
- **Diamond:** N-59, N-60, and N-61 are independent lanes that must converge at N-62.
- **Triple-anchor recheck:** N-59, N-60, and N-61 each test a distinct product boundary;
  no node introduces a new feature or post-MVP redesign.
- **Assumption conflicts:** D-38 allowed replay-only microphone evidence and deferred
  Windows packaging. `[revised: N-60 requires non-silent hardware evidence; N-61
  requires a real Windows-host install]`.
- **Deferral integrity:** N-59 unblocks N-62 cognition; N-60 unblocks N-62 perception;
  N-61 unblocks N-62 packaging/interaction.
- **Load-bearing integrity:** every endpoint exists and every break condition is
  observable through jobs, files, processes, ports, UI state, or install artifacts.
- **Unresolved edges:** none. N-55 remains an explicit limitation, not an untracked
  dependency; N-62 requires user acceptance if it remains open.

### §N.4 — Stage 3 REVISE + FINALIZE

- `[revised: smoke is insufficient]` D-28…D-42 remain implemented, but DONE.md now
  marks deployment-sensitive rows ⏳ until N-59…N-62 pass.
- `[revised: KISS boundary]` Four nodes replace one oversized “test everything”
  script. Each planned script has one objective and can fail independently.
- `[revised: real-host evidence]` Replay remains a deterministic control, but cannot
  substitute for live microphone/display and Windows ARM64 installation evidence.
- `[revised: acceptance authority]` N-62 becomes the current deployability sink;
  D-38 remains the historical MVP implementation sink.

**Current executable frontier:** N-59 can run on the current WSL environment once
credentials/model services are available. N-60 requires a real non-silent microphone
and display session. N-61's Linux/DOM lanes can start now; its terminal lane requires
Windows ARM64. N-62 is blocked by all three.

### §N.5 — Confirmation gate

Stop here. Do not implement or run N-59…N-62 until the user explicitly confirms
this stress-revalidation scope.

---

## §O — Nodal substrate, production serving, UI integrity & system diagrams (2026-06-19) — **PLANNED**

*Four user directives this session, captured plan-first. They sharpen the refined MVP
goal (§K.0.1) and the post-MVP n8n substrate (N-64 / §L.7). IDs N-65…N-68.*

```
[N-65 SERVE]    centrality:H ambiguity:M — production-grade local llama.cpp serving
[N-66 ATOMIC]   centrality:H ambiguity:M — drive subsystems to atomic/nodal services
[N-67 UI-AUDIT] centrality:H ambiguity:L — every exposed feature audited for integrity
[N-68 DIAGRAMS] centrality:M ambiguity:M — dense legible system diagrams (mermaid→SVG)
```

### N-66 (ATOMIC) — Drive subsystems to atomic, single-objective, nodal services `[ ]` — FULL
**Directive (user 2026-06-19).** Refine the implementation so each subsystem, while
achieving **one and only one** objective, is also a **well-defined node-level object** for
the future n8n system (N-64). This is both a near-term *refactoring principle* applied to
current work AND a tracked node. It is the bridge between today's hardcoded kernel and the
N-64 substrate: do the atomization *now* (behind the existing in-process calls), lift to
n8n *later*.
**Anchor.** *Task-local:* every subsystem = a service with one responsibility + one stable
contract (HTTP+MCP), no hidden cross-writes. *Impl-scope:* today perception/memory/journal/
retrieval/tools are interwoven in `kernel/`+`ctx/`+`retrieval/`; many do >1 thing or write
stores directly. *Soul:* atomic, inspectable, replaceable parts = more local-first + more
swappable. **Coherent — it is N-64's precondition.**
**Method.** Apply N-50 Phase-1 (abstraction DAG → shared primitives) + Phase-2 (where each
lives). Output a **service inventory**: name · single objective · inputs/outputs · contract
· current coupling to break · invariant it must preserve (I1 single-writer, I3 provider
seam). Refactor in dependency order; each extraction is gate-guarded (behavior-preserving).
**Invariants.** Memory/journal writes stay behind the single-writer service (I1); provider
choice stays behind the `model.py` role seam (I3); no atomic service defaults personal data
to cloud (D-33 / local-first). **Edges.** `--enables--> N-64` load-bearing · `--shapes-->
N-65/N-67/N-68` (serving, UI, and diagrams all describe the same node set).

### N-65 (SERVE) — Production-grade local llama.cpp serving `[x]` MVP-ACCEPTED 2026-06-20 @ native ~10 tok/s (refinement → N-73) — see D-45 — FULL — concretizes N-32, extends D-37
> **★ DECISION (user 2026-06-20): "leave building from scratch, proceed with 10 tk/s, mark
> refinement/optimizations for later."** MVP serving baseline = **native Windows ARM64 ~10 tok/s**
> (run the official prebuilt natively, NOT in WSL; default 9 threads). The ≥15 push (native -mcpu
> build, AC tuning, NPU/GPU, spec-decode E2B) is split out to **N-73** (deferred). Detail below.
> **★ MEASURED REALITY (2026-06-20, D-45) — corrected after two over-conclusions:** host =
> **Snapdragon X Elite (Oryon, 12c), ARM64**. Model = Gemma-3n-E4B (7.52B total but **~4B
> EFFECTIVE** via PLE/MatFormer — so ≥15 IS plausible; my "too big" call was wrong). VERIFIED:
> prefix-reuse works; **native Windows ARM64 ≈10 tok/s vs WSL 7.4 (+37%)**, WSL thread-cliff absent
> natively. THREADS: sweeps were on **battery** (throttling → ±4–5 noise; 8≈9 indistinguishable) →
> **reverted to 9 (user's deliberate choice)**, capped by cores; `LK_THREADS` overrides. ≥15 NOT yet
> reproduced but NOT disproven — confounds are **battery + a generic (non-Oryon) prebuilt**. PATH
> (user 2026-06-20): **build llama.cpp natively for Windows (-mcpu=native Oryon) + run on AC**;
> blocked on missing **MSVC CRT** (clang present, no VS Build Tools, not admin) → needs Build Tools
> install. After ≥12 tok/s verified → add **NPU/GPU + speculative decoding w/ Gemma-3n-E2B draft**.
**Directive (user 2026-06-19, "use brain").** The serving layer uses almost no production
optimization — and this is about *serving*, not compiling with -O3. Current argv
([services/lk/server.py](../services/lk/server.py) ~164–188): `--ctx-size`, `--threads 9`,
**`--n-gpu-layers 0` (pure CPU default)**, `--defrag-thold 0.1`, `--mlock`, `--parallel 1`,
`--slot-save-path`, optional `--flash-attn`/`--cache-type-k/v`/`--jinja`, `--reasoning off`.
Real KV is *quantized* (cache-type) and a single text-only session slot is saved (D-37), but
**every turn re-evaluates the full prompt** → D-36 p50 31.8s. This node is the
usability lever (§K.0.1 #3).
**Optimization menu (the substance — prioritized):**
1. **Cross-turn KV prefix reuse.** Ensure `cache_prompt:true` on every completion + adopt
   llama.cpp **`--cache-reuse N`** so a shifted prompt reuses the longest common KV prefix
   instead of recomputing. Today trimming happens at the app layer (`tail_for_model`), which
   *defeats* prefix reuse — align app-side context shaping with server-side KV identity.
2. **Server-side sliding-window context-shift.** Keep **BOS + system prompt + tool/skill/
   MCP/skill defs + pinned context FIXED** (llama.cpp `--keep` + context-shift) and trim
   only the rolling middle — so the expensive stable prefix is never re-evaluated. Replaces
   blunt app-layer truncation.
3. **KV-as-content-cache (extends D-37 beyond a session slot).** Pre-compute + **save KV
   slots for hot, reused content blocks** (frequently-loaded docs, web pages, notes, the
   system/tool/skill/MCP def block) and **restore** them to skip attention recompute on
   reuse — "dirty loads" of docs/web/notes into KV. Keyed by content+model+template hash
   (reuse D-37's identity discipline); invalid → cold. KV is derivative, never canonical (I).
4. **KV compaction via dynamic compression, not trimming.** Beyond cache-type quant: evaluate
   importance-based KV eviction/compression (H2O/SnapKV/Scissorhands-class, or llama.cpp
   native shift) so long context degrades gracefully instead of hard-trimming. (advanced →
   post-MVP per §K.0.1.)
5. **Compute placement.** GPU offload default when available (`--n-gpu-layers` auto from
   `LLAMACPP_GPU_LAYERS` probe, not hardcoded 0); thread count = cores not fixed 9; tune
   `--batch-size`/`--ubatch-size` for prompt-eval throughput.
6. **Model + KV quantization** review (model GGUF quant level vs quality; KV q8/q4 with flash
   attn). 7. **Speculative decoding** (`--model-draft`) for local latency. (advanced → post-MVP.)
**Anchor.** *Soul:* "the whole system optimised for local" — a watcher that takes minutes
fails the responsiveness bar. **MVP scope (hard, per §K.0.1 RESOLVED):** items **1, 2, 3**
(KV prefix reuse + context-shift + slot save/restore) ARE the MVP — they create the verified
warm/hot-KV regime — plus `-fa`-always + KV-q8 + physical-core threads. Item 4 (dynamic KV
compaction) and item 7 (speculative decoding) stay post-MVP; spec-decode is explicitly NOT
in the target path (target is met without it). **Edges.** `--concretizes--> N-32`
load-bearing · `--extends--> D-37` (KV slots → content-cache) · `--constraint--> D-36`
(must stay random-turn compatible) · `--feeds--> N-62` (usable-local acceptance lane).
**Ambiguity.** Per-block KV-cache eviction policy `crystallizes-during`; context-shift vs
app-trim boundary `resolve-before-start`; GPU availability on this host `crystallizes-during`.

**Performance TARGET (user 2026-06-19, VERIFIED BY USER): ≥ 15 tok/s decode at 32K+
context, PURE CPU — no GPU, no NPU, AND NO SPECULATIVE DECODING.** The user has *tested
and confirmed* this is achievable on the deployment host. **Measurement regime (user-
specified, this is what the target is defined against):** steady-state decode **excluding
TTFT**, with **warm caches, a hot server, and a hot KV** — i.e. the prompt prefix is
already resident in KV and we are measuring token generation, not first-token latency.
**Consequence for the build:** the levers that *create and preserve the hot-KV warm regime*
are the MVP-critical ones — not raw decode tricks. Spec-decode is explicitly OUT of the
target path (it is a bonus, not a requirement, and the bar is met without it).
**CPU-only mechanics, RE-RANKED for the warm/hot-KV target (2026-06-19):**
- **(MVP-critical) Keep the KV hot across turns — cross-turn prefix reuse.** The whole
  target assumes the prefix is already in KV. So `cache_prompt:true` on every completion +
  llama.cpp **`--cache-reuse N`**, and **stop app-layer trimming (`tail_for_model`) from
  defeating prefix identity**. This is item 1 above — promoted to the dominant lever because
  the verified regime *is* the warm-KV regime.
- **(MVP-critical) Server-side context-shift with a FIXED prefix** (item 2: `--keep` +
  context-shift; BOS + system + tool/skill/MCP defs + pinned context never re-evaluated).
  This keeps the hot region stable so warm decode stays warm as the rolling middle moves.
- **(MVP-critical) KV slot save/restore for hot content** (item 3, extends D-37): restoring
  a saved KV *is* "hot KV without paying TTFT" — the literal mechanism behind the regime.
- **Flash attention `-fa on` ALWAYS** — smaller KV/token + **hard prerequisite for KV
  quant** (without `-fa`, quantized KV is dequantized every step → slower). Make default-on.
- **KV-cache quant `--cache-type-k/v q8_0`** — halves KV bytes → **less memory bandwidth per
  decoded token**, the dominant steady-state CPU cost at 32K. Requires `-fa`. (q8_0 = safe.)
- **Quant level for CPU = go smaller** — decode tracks memory bandwidth, so a smaller weight
  quant is *faster*: prefer **Q4_K_M**; evaluate **Q4_0 online-repacked AVX2/AVX-512/AMX
  kernels** that llama.cpp accelerates on CPU; measure quality.
- **Threads `-t` = PHYSICAL cores** (not hardcoded 9) + `--cpu-mask`/`--numa` pinning.
- **`--ubatch-size`/`--batch-size` 1024–2048** — prefill lever (affects TTFT, which the
  target *excludes*, but still matters for the cold path → warm transition).
- **Build** — `third_party/llama.cpp` must carry the 2026 Gemma-4 KV-cache fix (~40%
  context-heavy memory cut) and be built for the host ISA (AVX-512/AMX).
- **Validation.** Reproduce the user's measurement (warm/hot-KV, TTFT-excluded) and record
  p50/p95 decode tok/s @ 32K in D-36 to confirm ≥15 holds in our harness. Sources in §O.

### N-67 (UI-AUDIT) — Exposed-feature integrity audit `[~]` — FULL — extends N-10, re-checks D-35/D-39/D-40/D-41
**PASS-1 DONE 2026-06-20 → D-51 (control-surface sweep).** Enumerated every classic-variant
button/toggle and traced each to its backend path. **Verdict matrix:** all REAL except the
**`proactive-toggle` = OVER-CLAIMED** (wrote `config.proactive` per-turn but nothing gated the
background `_maybe_proactive` loop → unprompted findings kept firing when "off"). **Fixed:** real
consent gate `proactive_enabled` (UI → `/observer {observer:"proactive"}` → loop early-return),
proven by a test that flips it off and asserts no `run_proactive` call. Remaining for N-67:
the qualitative pass (elegant / non-obstructive / well-integrated thresholds — `crystallizes-during`)
and an explicit re-grade of D-35/D-39(voice→N-63)/D-40(telemetry)/D-41(chat lifecycle).
**Directive (user 2026-06-19).** Go through the current UI; cross-check **every single
button/feature exposed to the user** — is it implemented as deeply / seamlessly / robustly /
non-obstructively / well-integratedly / elegantly / in-a-well-defined-manner as it
broadcasts itself? This operationalizes §K.0.1 #1 (integrity) and is the natural extension
of N-10 (classic refactor: drop `localDraft`, truthful toggles).
**Method.** Enumerate the full control surface (classic variant `app.js` toggles/buttons:
voice, audio, retrieval, deep-search, vision, ingest, reminders, chats save/archive/restore,
stop/cancel, actions confirm, telemetry strip, …). For each, produce an **integrity matrix
row:** control → advertised behavior → actual backend path → verdict {real / partial /
hollow / over-claimed} → fix. Then fix or honestly disable the gaps (no broadcast-without-
substance). Cross-check against D-35 (truthful UI), D-39 (voice — known regressed), D-40
(telemetry), D-41 (chat lifecycle). **Edges.** `--extends--> N-10` · `--re-grades-->
D-35/D-39/D-40/D-41` · `--feeds--> N-61` (desktop/UI stress) · `--gated-by--> §K.0.1 #1`.
**Ambiguity.** "Elegant/non-obstructive" thresholds `crystallizes-during` (start with
functional truth, polish second).

### N-68 (DIAGRAMS) — Dense, legible system diagrams `[~]` → **MVP 1.2 (user 2026-06-20: "other things first")** — was HARD-MVP, now deferred to the 1.2 sub-phase
**STATUS 2026-06-19 — FULL SET DRAWN (28 diagrams), level corrected after user review.**
Contract (user-clarified, after 3 wrong attempts — see below): **every LAWRENCE subsystem
whose code runs in the live process gets TWO diagrams.** (1) **granular = systems
architecture, generalized yet granular** — real components as GENERALIZED ROLES (not impl
names like BM25/RRF/MemoryIndex) + **how the subsystem meshes with the others (the gears)**
with the NATURE of each coupling labelled on the edge (realtime/transient/independent ·
temporally-atomic · async-decoupled · least-privilege seam · proactive invocation ·
context-refined · single-writer · persist-before-act). NOT source-code transcription, NOT
generic boxes. (2) **n8n = the same subsystem rebuilt from the real n8n node library**,
honoring n8n's real restrictions (each forcing-restriction called out inline `n8n:` —
no realtime capture, stateless-per-execution, loop-only-via-Loop-Over-Items/recursion,
explicit Merge, **no SSE/token-streaming**, invariants enforced by convention not engine).
**14 subsystems × 2 = 28 diagrams, all legibility-OK (0 overlaps):** S1 sensors · S2
context-gating · S3 kernel/proactive · S4 retrieval · S5 memory+notes · S6 journal · S7
model+serving · S8 agency · S9 scheduler · S10 notify · S11 policy · S12 capability-resolve
· S13 ui-bridge · S14 control/CLI. Index + level-definitions + legend in
[docs/diagrams/README.md](../docs/diagrams/README.md). Pipeline: mermaid `src/*.mmd` →
`tools/mmd2svg.py` → Graphviz `dot` (Sugiyama layering + barycenter crossing-min) → SVG +
geometry lint (crossings≤12/rank≤9/nodes≤40/overlaps=0).
**Process note (lesson):** first pass was rejected twice — (a) too abstract (generic
process/store boxes), then (b) too code-literal (method signatures). The accepted level is
generalized-architecture-WITH-inter-subsystem-interactions. The earlier "n8n-substrate" and
"hard question (transitive realtime components)" framings were MY inventions and were cut.
**Remaining for full close:** (a) true raster *visual* check — blocked in sandbox (no
chromium/cairosvg/rsvg); SVGs render in browser/VSCode/GitHub, geometry lint is the gate
meanwhile; (b) re-grade vs N-66 once service boundaries are refactored.

**Original spec (unchanged):**
### N-68 (DIAGRAMS) — Dense, legible system diagrams — medium
**Directive (user 2026-06-19).** Prepare dense diagrams of how the subsystems work — for
**every looped / feedback / agentic / retrieval / web-call / tool-call** system — using
mermaid.js. Ensure **legibility**: render to **SVG and check visually**, detect + handle
**edge intersections**, and run a **graph algorithm to choose the best node ordering**
(layering/topological + crossing-minimization) before presenting. Dual perspective:
**(a) n8n view** (services as nodes, workflows as graphs) and **(b) granular view**
(internal control flow). **Hard question to resolve:** how to display **transitive,
realtime, independent components** (the always-on sensor cascade that *emits* events vs.
the event-driven workflows that *consume* them) — likely separate swimlanes / a legend for
"async event boundary," since they don't share a synchronous call graph.
**Method.** Per subsystem: build the graph model → topological layering + barycenter/median
crossing-reduction ordering → emit mermaid → render SVG (headless) → programmatic check
(overflow, overlapping bounding boxes, crossing count) → iterate until legible → visual
confirm. Keep diagrams in `docs/diagrams/`. **Subsystems to cover:** retrieval engine
(discern→parallel arms→assess→RRF, §J), proactive loop (D-32), journal (D-05), turn
pipeline (D-30/D-26), sensor cascade (N-45/N-33), agency (D-34), scheduler (D-12), memory
tiers+recall (D-01/D-24), the voice path (N-63), and the n8n-substrate target (N-64).
**Edges.** `--depends-on--> N-66` (the node set it draws) · `--serves--> N-64` (the n8n
composition view) · `--serves--> N-29` (docs). **Ambiguity.** SVG legibility-check tooling
`resolve-before-start` (mermaid-cli + a crossing/overlap linter); realtime-component
notation `crystallizes-during`.

### §O edges
```
N-66 --enables-----> N-64   load-bearing  atomic services are the n8n nodes
N-66 --shapes------> N-65   significant   serving optimizes the same node boundary
N-66 --shapes------> N-67   significant   UI audit checks node contracts end-to-end
N-66 --shapes------> N-68   load-bearing  diagrams render the node set
N-65 --concretizes-> N-32   load-bearing  the local-latency lever, made specific
N-65 --extends-----> D-37   significant   session KV slot → content KV cache
N-67 --extends-----> N-10   significant   truthful-UI refactor, audited exhaustively
N-68 --serves------> N-64   significant   the composition/workflow view
{N-65,N-67} --feed-> N-62   significant   usable-local + UI integrity acceptance lanes
```

## §P — SOUL-CONFORMANCE GATE (2026-06-19, user-directed) — **THE MVP GATE**

> **Directive (user 2026-06-19):** "Focus on the singular goal now, MVP — deliverable, first.
> … But first, in MVP, ensure the system follows its soul vision fully." CI/CD / Docker /
> installer / Android-tolerance + emulated test cases come **after** MVP. The *soul* =
> `docs/papers/LAWRENCE_v0_1_ieee.tex`. This section is the authoritative, code-grounded
> verdict on how far the live process actually honors that paper, and the nodes that close
> the gap. Method: read the running code (kernel/invoke.py, retrieval/{engine,memory}.py,
> ctx/{distill,notes,store}.py, policy.py, model.py, agency.py) against the paper's contracts
> and algorithms — not the docs' self-claims.

### §P.1 — Conformance scorecard (grounded 2026-06-19)

| Soul contract / algorithm (paper)                                     | Live code reality                                                                                                                        | Verdict                                        |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **TurnContextSnapshot** — typed evidence index (Eq.1 + contracts tbl) | `ContextSnapshot{version,text}` (invoke.py) — frozen rolling-context string + version only                                               | **DEGENERATE**                                 |
| **Parallel-facet runtime** — `ProcessTurn` (Alg.1, §VII)              | `run_turn` = serial `analysis→retrieve→respond`; no facets, no fast-threshold loop, no merge                                             | **ABSENT (serial)**                            |
| Fast loop + Slow loop (§VII-C)                                        | fast answer + `dispatch_refine` slow-loop elevation (refine.py)                                                                          | **PARTIAL ✓**                                  |
| `context_version` stale-discard (Eq.1 purpose)                        | used in `run_proactive` stale-guard + logged per turn                                                                                    | **CONFORMANT ✓**                               |
| **Retrieval `S_ret`** 6-term (Eq.5)                                   | memory.py: L(bm25/FTS5)+V(cosine)+G(graph)+R(recency)+link-boost(H)−P(delete) + RRF                                                      | **CONFORMANT ✓**                               |
| **Retrieval bundle `B_t`** typed (Eq.6)                               | `engine.gather`: recent-ctx ∪ notes/doc/web arms, parallel, cited bundle                                                                 | **CONFORMANT ✓**                               |
| Markdown Zettelkasten + metadata (Eq.2, tbl)                          | ctx/notes.py: md+frontmatter+`[[id]]`+backlinks+edges.jsonl                                                                              | **CONFORMANT ✓**                               |
| Note taxonomy {context_log, journal_daily, task_note, knowledge_note} | promotion (D-43) now writes `context_log`/`task_note`/`knowledge_note`; journal writes `journal_daily`                                   | **CONFORMANT ✓**                               |
| **Distillation `P_dist`** promotion (Eq.3, Alg.2)                     | `ctx/promote.py` `pdist()` scorer → promotes worth-keeping turns to durable notes (D-43)                                                 | **CONFORMANT ✓**                               |
| **Auto-linking `S_link`** (Eq.4)                                      | `ctx/promote.py` `slink()` (lexcos+jaccard+recency+thread) auto-links on promotion (D-43)                                                | **CONFORMANT ✓**                               |
| Journal synthesis `J_d` (Eq.)                                         | kernel/journal.py (WS-J rolling first-person)                                                                                            | **CONFORMANT ✓**                               |
| Proactive loop fires unprompted (§VII)                                | `run_proactive` wired from 4 drivers (vision/audio/tick/spool) → throttled convergence → card+notify; **verified + instrumented** (D-44) | **CONFORMANT ✓**                               |
| Provider gateway / LLMProviderAdapter (tbl)                           | model.py role seam (I3)                                                                                                                  | **CONFORMANT ✓**                               |
| Policy gating (§XII-C)                                                | policy.py: `allow→Decision` + `audit` + `redact_text` + `prepare_messages`                                                               | **CONFORMANT ✓**                               |
| ToolActionProposal (tbl)                                              | agency.py propose→token→decide→execute + RESPONSE.actions                                                                                | **CONFORMANT ✓**                               |
| Failure: degrade branch-by-branch (§XVII)                             | try/except fallbacks throughout (recall/retrieve/refine/extract)                                                                         | **CONFORMANT ✓**                               |
| Supervisory control PID/Petri/MDP (§XVI)                              | none                                                                                                                                     | **POST-MVP** (paper: explicitly control-plane) |

**Tally (updated 2026-06-19 after D-43/D-44):** 15 conformant · 1 partial (fast/slow) · 1 degenerate (snapshot) · 1 absent (parallel-facet) · 1 deferred. **Durable-memory formation is now closed** (D-43: P_dist promotion + S_link auto-linking + soul note taxonomy) and **the proactive loop is verified+instrumented** (D-44). The only remaining unfollowed core is the **turn runtime** — serial pipeline + degenerate `{version,text}` snapshot (N-69 snapshot, N-70 parallel-facet) — **deliberately deferred to the next MVP iteration** per user (§P.3).

### §P.2 — Gap-closure nodes

- **N-69 (SNAP) — `TurnContextSnapshot` enrichment** `[ ]` — FULL. Promote `ContextSnapshot{version,text}` to the soul's typed frozen index: + screen_ref, audio_ref, thread_ref, app_ref, time_ref, reminder_ref, latest_chat_refs, policy_state (context_version already there). Foundational, additive, low-risk. **Subsumes N-06**'s vision-demotion + per-chat split. → MVP.
- **N-70 (FACET) — parallel-facet turn runtime** `[ ]` — FULL. Dispatch independent evidence producers concurrently over the frozen snapshot; fast-threshold immediate emit; deferred merge same turn_id. Soul's centerpiece **and** the local-latency win (subsumes/serves N-32, N-65 regime). **The high-risk rebuild on a working serial turn — see §P.3 FORK.**
- **N-71 (DISTILL) — `P_dist` promotion + DistillAndLink + `S_link`** `[x]` — FULL — **DONE 2026-06-19 → D-43**. Heuristic, **model-call-free** scorer over signals already present (novelty vs recent, extractor significance, user-emphasis "remember"/pin, thread/tag overlap, actionability from tasks/actions) → promote turns/findings to durable `context_log`/`task_note`/`knowledge_note`; on promotion run DistillAndLink (entities/tags → candidate notes → `S_link` λ-score → keep>τ → write linked zettel). Closes 3 gaps at once; populates retrieval's (conformant but edge-starved) graph arm. Additive, testable offline. → MVP.
- **N-07 (PRO) reframed** `[x]` — **DONE 2026-06-19 → D-44**. Verified wired end-to-end (4 drivers → throttled `run_proactive` → card+notify; "may never fire" was uncertainty, not a break) + instrumented (`proactive_stats()` counters + `/status` line). Firing is throttled **by design** (600s + droppable + tier≥2).
- **N-08 (SESS)** `[ ]` — chat session lifecycle (unchanged). → MVP.

### §P.3 — THE FORK (needs user call)
Does MVP "follow the soul fully" require **N-70 (rebuild the turn into the true parallel-facet runtime)**, or is the present **serial turn + slow-loop refinement + try/except branch-degradation + parallel retrieval arms** an acceptable MVP *realization* of the parallel intent — with N-70 deferred post-MVP and MVP focusing on the additive, low-risk conformance wins (N-69 snapshot, N-71 distillation/linking, N-07 proactive verify)? This trades soul-purity vs deliverability/risk and is the user's decision.

### §P edges
```
N-69 --foundation--> N-70   load-bearing  the typed snapshot is what facets share
N-69 --subsumes----> N-06   significant   snapshot typing folds vision-demotion + per-chat split
N-71 --feeds-------> N-02   significant   auto-links populate the (edge-starved) graph arm G
N-70 --realizes----> soul   load-bearing  the parallel-facet intent (§VII)
N-70 --serves------> N-65   significant   parallel producers are the local-latency win
{N-69,N-71,N-07} --feed--> N-62   significant   soul-conformance acceptance lane
```

---

## §Q — CONSOLIDATED UI/CHAT PLAN (all scattered ideas in one place) — **user 2026-06-20**
> **Why this exists (user 2026-06-20):** "There are many spread-out plans/ideas for UI chat
> upgrades/refinements. Retrieve … consolidate all, then we'll split it into phases, and what's
> for now and what's for later." This section GATHERS every UI/chat idea scattered across §C, §D,
> §L.4/§L.5/§L.6, §G, the FR list, and the memory files — deduplicated, grouped, each tagged with
> its source node. **The now/later phase split below is a PROPOSAL to refine together** (the user
> will decide the cut). Canonical UI = the single classic surface (N-10); seam = N-09 (done).

### §Q.1 — The full inventory (grouped; source nodes in brackets)

**G1 · Foundation / shell / architecture**
- [N-09 ✅ D-23] UI seam: variant arch, `web/lib/bridge.js` (sole transport), `bootstrap.js`,
  `variants/classic/app.js`, `/health.uiVariant`. Swappable UI; hosts future composition surface.
- [N-10] Canonical classic UI, refine HEAVILY: drop `localDraft` + all hollow/fabricated state;
  truthful toggles driven by `/health`+SSE; vendored markdown renderer; config off the main bar.
- [N-11 → folded into N-10] command-palette ergonomics (⌘K), grow-to-content geometry, settings as
  a separate window, ⌘L cross-chat link flow, backlink chips, turn-id elevation, native vibrancy/blur.
- [N-27] Tauri shell rebuild so live **Stop/Esc** fire `bridge_delete` (cancel). Mechanical.
- [N-26] Host-native UI (FR-011) — strategic, on the seam (`apps/desktop/host/windows/`).
- [N-67] **Integrity audit — GATES all UI work:** every exposed control real / honestly disabled;
  no broadcast-without-substance (§K.0.1 #1). Integrity matrix per control.

**G2 · Chat / session model + memory (BASE shipped; UI half pending)**
- [N-08] Session lifecycle: dynamic session boundaries (idle-gap / day-rollover / explicit), clear
  the *working set* (L1/L2) on new cycle (durable transcript + WS-J summary persist), rolling
  model-conducted chat journal, recall / review / restore / load-old / link. BASE (ChatStore +
  NoteStore edges) shipped; the **recall/review UI half** is pending.
- [N-08/ui-redesign mem] Hybrid memory model: one global mind (journal + notes + L3) + per-chat
  L1/L2; cross-chat links = backlinked GRAPH over NoteStore; backlink chips per message; click navigates.

**G3 · Response surface = collaborative MDX "shared space"  [N-72, the NEW centerpiece]**
- Chat becomes a **rolling stack of frames**; a new frame per **new user query** OR **proactive
  instantiation**; **proactive normally UPDATES the active frame** (only a new thread starts a frame).
- Per-frame layout: **(1) query → (2) retrieved-content thumbnails BETWEEN query and frame** (each =
  a static snapshot; **thumbnail TITLE = that source's citation footer content**) **→ (3) the shared
  MDX space** co-edited by model(s) + user.
- The shared space is a **living MD/MDX document**, not a one-shot bubble.

**G4 · Citations — table contract, passage-anchored, associative  [N-48 / §L.4]**
- A turn builds a **table of candidate references** (from what the model chose + retrieval provided +
  user insisted). **Model SELECTS rows; the system FORMATS the citations** → can't mis-cite.
- Each row: `id ↔ url/content`; **chunk displacement** (→ scroll-to-exact-chunk in-window);
  `reasonWhy`; `whatWillInvalidateThisCitation` (explicit defeater); `whatElseCouldBeRelated`
  (**1-/2-click associative graph** over NoteStore edges).
- Citations live **at point-of-evidence** (on the G3 thumbnails), **not** an end-of-response Sources block.

**G5 · Rich rendering + runnable artifacts (sandboxed)  [N-49 / §L.5, N-16]**
- Rich render: **Mermaid**, **KaTeX/MathJax math**, rich MD/MDX, **other live JS components**,
  graphs / geometric drawings / illustrations; **static snapshots** of retrieved pages + thumbnails.
- **Runnable, SANDBOXED artifacts** (strict-CSP iframe — the largest security surface): run code,
  small web-apps, **WASM**.
- **In-window browsing / custom search engine** (WolframAlpha + SearXNG feel): cited response +
  browsable links / docs (scrolled to the exact chunk) / papers / patents / socials / forums —
  never bounce to an external browser; grounded in short↔intermediate↔long-term context.
- **Generated artifacts:** Marp.js PPTs with spanning flowchart/diagram (draw.io / Excalidraw-class),
  **model verifies legibility**; tabular SQL/NoSQL data generation; MDX generation.
- [N-16] Artifact / deep-study engine (WS-A): `make(spec)->path`, md-first under `memory/vault/`,
  real citations + provenance footer, provider-blind (I3).

**G6 · Folded UI controls  [N-12/13/14/15, N-30]**
- [N-12] Ingest button ("Save to KB" → status; FR-005 UI half).
- [N-13] Push-to-talk voice (POST /voice exists; PTT button + streaming transcript; ties N-63).
- [N-14] Reminders panel/badge (badge from backend counts).
- [N-15] Capability markers in popup (FR-010).
- [N-30] Cards — fold into parents: telemetry (FR-004 → N-10 + honest `/metrics`), **evidence cards
  (FR-008 → typed `CitedResult` cards, pairs N-16/G4)**, asset/panel (FR-010 → N-15).

**G7 · Composition surface  [N-64, post-MVP]**
- n8n workflow-composition UI; the N-09 seam hosts it later. Out of MVP.

**G8 · Build methodology  [N-50 / §L.6]**
- Phase 1 **Abstraction DAG** — "which feature is a special case of which" → collapse onto shared
  primitives (do THIS first when we split). Phase 2 implementation-layer assessment. Phase 3 build.

### §Q.2 — PROPOSED now/later split (SEED — to finalize together)
**NOW (MVP) — the responsive, honest, shared-space core:**
- N-67 integrity audit (gate) · N-10 hygiene (drop localDraft, truthful toggles, vendored md, config
  off bar) · **N-72 shared-space frames** (query → thumbnails-with-citation → shared MDX) ·
  **rich render: MD/MDX + Mermaid + KaTeX** (G5 *render*, not yet *runnable*) · static snapshots +
  thumbnails · **N-48 citation-table core** (select-not-format + thumbnail titles + scroll-to-chunk) ·
  N-08 recall/review UI half · N-27 live cancel · folded controls N-12/13/14/15.
**LATER (post-MVP):**
- G5 *runnable/sandboxed* artifacts (code exec, WASM, web-apps), Marp/draw.io generation, in-window
  custom-search-engine breadth · N-16 deep-study engine · N-48 associative 1-/2-click graph expansion ·
  N-64 composition UI · N-26 host-native UI.
**FIRST STEP when we build:** N-50 Phase-1 Abstraction DAG over G1–G6 to find the shared primitives
(frame model · renderer · citation table · snapshot/thumbnail · sandbox host) before any code.

### §Q.3 — Detailed breakdown (each item: what it is · the primitive it needs · what it touches · deps)

**G1 Foundation**
- **N-09 seam ✅** — `web/lib/bridge.js` sole transport, `bootstrap.js` variant loader, `/health.uiVariant`. *Primitive:* the transport+variant boundary (DONE). *Deps:* none.
- **N-10 canonical classic** — remove `localDraft`/hollow state; toggles truthful from `/health`+SSE; **vendored markdown**; config off main bar. *Touches:* `variants/classic/app.js`, `ui_bridge.py /health`. *Deps:* N-09. *Primitive introduced:* truthful-state binding (UI reflects backend, never fabricates).
- **N-11 → folded** — ⌘K palette, grow-to-content, settings window, ⌘L links, backlink chips, turn-id elevation, vibrancy. *No standalone build* — adopt into N-10.
- **N-27 live cancel** — rebuild Tauri so Stop/Esc fire `bridge_delete`. *Primitive:* turn-cancel signal. *Deps:* Rust rebuild.
- **N-26 host-native UI** — native windows on the seam. Strategic/later.
- **N-67 integrity audit** — per-control matrix {real/partial/hollow/over-claimed}→fix. *Gate on all UI work,* not a feature.

**G2 Chat/session + memory**
- **N-08 sessions** — boundary policy (idle/day/explicit); clear *working set* on new cycle (transcript+WS-J persist); rolling chat journal; recall/review/restore/load/link. *Primitive:* the **session/working-set lifecycle** + recall surface. *State:* BASE done (ChatStore `messages.jsonl`, NoteStore edges); UI half pending. *Deps:* N-02 (recall quality, done), WS-J (done).
- **Hybrid memory + links** — global mind (journal+notes+L3) + per-chat L1/L2; cross-chat links = NoteStore graph; backlink chips. *Primitive:* the **note/graph substrate** (NoteStore, done).

**G3 Shared-space frames [N-72]**
- **Frame** = {query_ref, thumbnails[], shared_doc(MDX), editable_regions, rev}. New frame per query/proactive-instantiation; **proactive UPDATES active frame** normally. Rolling stack. *Primitives:* the **frame data-model**, **proactive→active-frame router**, **co-edit/merge discipline**. *Touches:* bridge protocol (frames, edits, SSE), `ChatStore`. *Deps:* renderer (G5), reference-record (G4), snapshot (G5), N-08 session.

**G4 Citation-table [N-48/§L.4]**
- Per-turn **reference table**; model SELECTS rows, system FORMATS → can't mis-cite. Row = {id↔url/content, **chunk displacement**, reasonWhy, whatWillInvalidateThisCitation, whatElseCouldBeRelated(1-/2-click NoteStore graph)}. *Primitive:* the **reference record** + select-not-format decoding contract + associative expansion. *Deps:* `CitedResult` (done D-26); **chunk displacement needs §L.3 chunk-level index (N-47, post-MVP)**; associative map needs NoteStore (done).

**G5 Rich render + artifacts [N-49/§L.5, N-16]**
- *Render:* Mermaid, KaTeX/MathJax, MD/MDX, live JS components, static snapshots+thumbnails. *Runnable (sandboxed):* code/web-apps/WASM in strict-CSP iframe. *Browse:* in-window cited search engine (links/docs/papers/patents/socials), scroll-to-chunk. *Generate:* Marp PPTs + draw.io/Excalidraw diagrams (model verifies legibility), SQL/NoSQL tables, MDX. *N-16:* `make(spec)->path` md under `memory/vault/` + provenance. *Primitives:* the **MDX+component renderer**, the **sandbox host**, the **snapshot/thumbnail capturer**, the **artifact generator/store**.

**G6 Folded controls [N-12/13/14/15, N-30]**
- N-12 ingest→status · N-13 PTT (POST /voice, ties N-63) · N-14 reminders badge · N-15 capability markers · N-30 cards (telemetry FR-004, **evidence FR-008 = a rendering of the reference record**, asset FR-010). All fold into parents.

**G7 Composition [N-64]** — n8n workflow surface on the seam. Post-MVP.
**G8 Methodology [N-50]** — Phase-1 Abstraction DAG (this §Q.3/§Q.4) → Phase-2 layer assessment → Phase-3 build.

### §Q.4 — Intersections / conflicts / overlaps (the Phase-1 finding)

**Shared primitives (intersections — build ONCE, reused widely):**
- **P1 · MDX+component renderer** (Mermaid/KaTeX/MD/MDX/JS) — used by G3 shared doc, G3 thumbnails, G4 reasonWhy, G2 recall/journal display, G5 artifacts. *The single most reused primitive.*
- **P2 · Reference record** (id/url/chunk/reasonWhy/defeater/related) — the one object behind **G3 thumbnail-title**, **G4 citation-row**, **G6 FR-008 evidence card**. Three views, one record.
- **P3 · Sandbox host** (strict-CSP iframe) — needed by G5 runnable artifacts AND by G3 displaying untrusted retrieved content/snapshots. *Display-sandbox is needed as early as G3, not only for "runnable later."*
- **P4 · Snapshot/thumbnail capturer** — G3 thumbnails ⊂ G5 static page snapshots; same capture path.
- **P5 · Frame data-model + bridge protocol** — G3 frames, G2 sessions (a session = a stack of frames), proactive routing, co-edit. Unifies G2↔G3.
- **P6 · NoteStore graph** — G2 backlink chips AND G4 associative 1-/2-click map share the same edges (done).
- **P7 · Co-edit / rolling-revision discipline** — G3 "model+user co-edit the shared doc" reuses the **WS-J journal rolling-revision** pattern (model revises a living MD doc, single-writer + atomic). Reuse, don't reinvent.

**Conflicts (resolve before building):**
- **C1 · Renderer scope** — N-10 says "vendored *markdown*"; G5 needs full MDX+Mermaid+KaTeX+components. Building minimal-md first then replacing = wasted work. **Resolve:** define P1's scope once; N-10 adopts P1, not a throwaway md renderer.
- **C2 · Sandbox timing** — proposed split put sandbox "later (runnable)", but G3/G5 rendering of untrusted *retrieved* content NOW requires the *display* sandbox. **Resolve:** P3 display-sandbox is NOW; only code/WASM *execution* is later (same primitive, staged capability).
- **C3 · Frame vs existing message model** — N-72 frame ⊋ ChatStore `messages.jsonl` message (frame carries thumbnails+shared_doc+edits+rev). **Resolve:** frames EXTEND messages additively (I5: add, never rename); a message becomes a frame's seed.
- **C4 · Concurrency on the active frame** — model stream + user edits + "proactive updates the active frame" all write one shared_doc. **Resolve:** single-writer + rolling-revision (P7); proactive merges as a revision, never clobbers a user edit in flight; define edit-region ownership.
- **C5 · Three citation surfaces** — thumbnail (G3) vs end-of-response Sources (current) vs evidence card (G6). **Resolve:** one P2 record; the end Sources block is REPLACED by point-of-evidence thumbnails; the card is the same record in a different slot.
- **C6 · scroll-to-chunk dependency** — G4/G5 scroll-to-exact-chunk needs **chunk-level addressing (§L.3/N-47, post-MVP)**; today `vectors.py` is doc-level brute-force. **Resolve:** NOW = doc-level citation + open-in-window; **chunk-displacement/scroll-to-chunk moves to LATER** with N-47. (Corrects the seed split, which had scroll-to-chunk in NOW.)
- **C7 · Proactive create-vs-update rule** — "new frame per proactive instantiation" vs "proactive usually updates current frame" need an explicit predicate. **Resolve:** proactive UPDATES the active frame unless it opens a genuinely new thread (define the thread-change signal, ties N-07).

**Overlaps (collapse / subsume):**
- **O1** N-10 vendored-markdown ⊂ P1 renderer (do P1 once).
- **O2** G3 thumbnail = G4 row = G6 FR-008 card = **P2** (one record, three renderings).
- **O3** G3 thumbnail-snapshot ⊂ G5 static-snapshot = **P4**.
- **O4** N-30 cards have no standalone build (FR-008→P2/G4, FR-004→N-10, FR-010→N-15).
- **O5** N-11 fully ⊂ N-10 (superseded).
- **O6** N-16 (generate+store artifacts) vs G5 (render/showcase artifacts) — N-16 = backend engine, G5 = display; related, keep distinct but share P1.
- **O7** G5 "in-window custom search engine" = G3 thumbnails + P2 + retrieval (D-26) + scroll-to-chunk (C6), scaled to full browsing — it's an *expansion of G3*, not a separate stack.

### §Q.5 — Revised dependency-aware phasing (supersedes §Q.2 seed)
**Build order forced by the DAG:** N-67 gate · **P1 renderer** + **P3 display-sandbox** + **P2 reference record** are the foundation (everything renders through them) → then **P5 frame model** (+P7 co-edit reuse) → then G3 shared-space assembles P1–P5 → G4 citation core (doc-level) → N-08 recall UI · G6 controls · N-27 cancel.
**NOW (MVP):** N-67 · N-10 hygiene-on-P1 · **P1 (MD/MDX+Mermaid+KaTeX) · P2 reference record · P3 display-sandbox · P4 snapshot/thumbnail · P5 frame model + P7 co-edit** · **N-72 shared-space** (query→citation-titled thumbnails→co-edited MDX, proactive-updates-active-frame) · G4 **doc-level** citation (select-not-format, thumbnail titles) · N-08 recall UI · G6 folded controls · N-27 cancel.
**LATER (post-MVP):** P3 *execution* sandbox (code/WASM/web-apps) · Marp/draw.io generation · **C6 scroll-to-chunk + G4 chunk displacement (needs N-47/§L.3)** · G4 associative 1-/2-click graph · G5 full in-window search-engine breadth · N-16 deep-study · N-64 composition · N-26 host-native.

### §Q.6 — MVP Phase-1 REFRAMED: chat-flow / lifecycle / ops / search-modes (user 2026-06-20)
> **User reframing:** the primitive-phasing read convoluted; the REAL Phase-1 MVP is **refining the
> CHAT UI FLOW + chat lifecycle + response operations + enforced search-modes** — NOT the full
> shared-space/artifact machinery. Phase-1 primitives chosen: **P1, P2, P4, P6.**

**P-cut (Phase-1): P1, P2, P4, P6.** Deferred: P3 sandbox, P5-full frame model, P7-full co-edit.
- **C1 (user): renderer is TWO-PHASE.** Phase-1 P1 = regular responses with sections/partitions/
  formatting + **mermaid.js** + **charts/graphs/plots** (Chart.js/Vega-Lite/D3-class). Phase-2 P1 =
  the full artifact-frame render (runnable/sandboxed). *(Corrects C1: no throwaway minimal-md.)*
- **C2 RE-RESOLVED (corrects my "sandbox now"):** Phase-1 **P4 = STATIC IMAGE snapshots** and the
  renderer shows only our own model output + declarative diagrams → **no P3 sandbox needed in
  Phase-1.** Sandbox returns later with runnable artifacts + live/interactive retrieved content.
  *Sub-decision:* model-authored charts as **declarative specs (Vega-Lite/Chart.js JSON)** stay
  sandbox-free; raw model-authored **D3/JS** is arbitrary code → would pull P3 in now. Recommend declarative.
- **Flow features pull in LITE forms of the deferred primitives (not the full ones):**
  - **P5-lite** = addressable messages + **sub-section anchors** + chat lifecycle (NOT a co-edited
    frame). Needed by branch-off, reply-to-section, link-at-arbitrary-points.
  - **P7-lite** = **edit→diff**: an edited/regenerated response is captured and **presented to the
    model as a diff in the context** (ties N-06 assembly) — NOT concurrent CRDT co-editing.

**Phase-1 work, bucketed (the user's flow list):**
- **A · Thread-flow fixes (reported bugs):** kill the constant **scroll-back** on query / voice-query
  trigger / transcription; stop the main thread **bloating** (virtualize/paginate + N-08 working-set
  clear). → **N-10**.
- **B · Chat lifecycle/history:** init / new-chat / switch / view / restore / backup / archive. →
  **N-08** (BASE done — ChatStore CRUD/switch/export; build the UI half + boundary/clear).
- **C · Response operations:** edit-response (as diff), regenerate, **branch-off**, format-change,
  copy/paste **formatted** chats, **reply to specific sections**. → **N-75 (NEW · CHAT-OPS)** on P5-lite+P7-lite.
- **D · Linking/reference graph:** link-at-arbitrary-points (model-understandable), reference other
  responses/chats, backlinks. → **P6 NoteStore** (done) + sub-anchors (P5-lite).
- **E · Enforced search-modes (beyond regular search):** **deep** · **socials** (forums/threads/
  communities/discussions/articles) · **research/patent/publication** · **financials** · **video/
  content** · **tutorials/codebases/technicals** · … → **N-74 (NEW · SEARCH-MODES)** over the unified
  engine (extends N-02/N-03/D-26 categories with typed, user/model-enforceable modes; each mode = a
  source-set + query-shaping + a render lens). Pairs with P2 reference records + P4 thumbnails.

**Net:** the **shared-space/artifact vision (N-72 full, G5 runnable, N-48 chunk/associative) moves to
Phase-2+**; Phase-1 = a solid, non-bloating, navigable chat with real lifecycle, edit/branch/link
ops, and typed search-modes. **Open to confirm:** (1) new nodes N-74 (search-modes) + N-75 (chat-ops)?
(2) P5-lite/P7-lite as the minimal forms? (3) P4 = static images (sandbox stays deferred)? (4) charts
declarative (Vega-Lite/Chart.js) vs raw D3?

### §Q.7 — Phase-1/2 decisions locked (user 2026-06-20, round 2)
**New nodes created:** **N-74 (SEARCH-MODES)**, **N-75 (CHAT-OPS)**, **N-76 (TRAJECTORY)** — see below.

**Moved INTO Phase-1 (MVP):**
- **Chunk + associative citations** (reverses C6). Pulls in **N-47-lite = a chunk-level LOCATOR**
  (offset/displacement within each retrieved source) — enough for scroll-to-exact-chunk + snapshot
  positioning. The full ANN/FAISS scaling (N-47 proper) stays Phase-2; the *associative 1-/2-click*
  map rides P6 NoteStore (done). So Phase-1 citation = select-not-format **+ chunk locator + associative**.
- **P4 = static PRE-RENDERED snapshots of the retrieved content** (web pages **pre-rendered/compiled
  to static**, + docs), **scrolled to the relevant chunk**. Headless render → static image/sanitized
  static (no live DOM) ⇒ still **no P3 sandbox** in Phase-1. This is P4's real definition, not a bare thumbnail.
- **P5-lite + P7-lite** — implement **abstract/atomic** (clean, swappable interfaces) so they upgrade
  to full P5 frame-model / P7 co-edit later without rework. P5-lite = addressable messages + sub-section
  anchors + chat lifecycle; P7-lite = edit→diff presented to the model in context.
- **Charts/plots:** **non-D3 (Vega-Lite / Chart.js / mermaid) in Phase-1; D3.js in Phase-2** (raw JS → sandbox).
- **Streaming + non-streaming UX.** Streaming ALREADY works end-to-end (model `_post_stream` → bridge
  SSE `delta` → classic `onDelta` evolving bubble + cursor; `streamState` Queued/Thinking/Cancelling).
  Phase-1 fix = the **non-streaming config path**: today it shows ONE "Thinking" bubble + a background
  job — replace with a **progress bar / chunked reveal / better feedback** (UX refinement, bucket A).
- **Cancellation + regeneration.** Cancel: UI shows "Cancelling" but the real backend stop needs
  **N-27** (Rust `bridge_delete` rebuild so Stop/Esc actually abort the turn). Regenerate: **N-75**. Both Phase-1.

**Phase-2 (deferred, recorded now):**
- **Semantic search of chats** (over the unified engine + embeddings).
- **N-76 (TRAJECTORY) — post-response trajectory awareness.** After a response generates, semantically
  pull *that response's* related responses/logs/journals + infer the **query-trajectory**, feed back to
  the model with an **enforced-JSON short confirmation** (keep / alter) so it can anticipate where the
  thread is headed and adjust before finalizing. Phase-2 (builds on semantic-chat-search + P2/P6).
- **Full co-edit concurrency model (C4 resolution, Phase-2):** **single write-lock — model XOR user at a
  time**; while the model writes, the editor is **non-editable**, BUT the user may drop **comments /
  markers / highlights / questions / exclamations / revision-requests mid-stream**, which inject an
  **on-the-fly refinement pass into the stream**. (P7 full.)
- Runnable/sandboxed artifacts (P3 exec), D3.js, Marp/draw.io gen, full N-47 ANN scaling, N-72 full
  shared-space, N-64 composition, N-26 host-native.

### §Q.8 — New nodes
**N-74 (SEARCH-MODES)** `[ ]` Phase-1 — Enforced, typed search modes over the unified engine (N-02/
N-03/D-26): **deep · socials (forums/threads/communities/discussions/articles) · research/patent/
publication · financials · video/content · tutorials/codebases/technicals · …** plus regular. Each mode
= {source-set + query-shaping + render lens}; user- AND model-enforceable. Pairs with P2 records + P4
snapshots. *Open:* per-mode source adapters; how the model requests a mode vs the user pinning one.

**N-75 (CHAT-OPS)** `[~]` Phase-1 — Response/thread operations on **P5-lite + P7-lite**. Scope locked
with the user 2026-06-20 (branching/edit check-in). **Data-model + bridge + UI + launcher BUILT &
offline-gated → D-48 (model) + D-49 (bridge/UI/launcher) + D-50 (cut-corner hardening).** Remaining:
**live visual verification needs a `cargo build --release` + WSLg relaunch** (the plan's documented Live
step) — offline gate is green. **Cut-corner audit 2026-06-20 (D-50):** removed `window.prompt` (unreliable
in the Tauri webview) → in-UI `promptInline`; **surfaced the previously-unreachable §3a ops** (selective/
explain via real text selection, extend/compress-by-N); branch/variant-switch/minimap now **load the chosen
path into the live feed** (was history-preview only); no-response note **never drops** (adopts/creates a chat).
- **Three kinds of branching:** **(1)** in-chat **alternative trajectories** — regenerations are
  *browsable siblings* (`q→r₁,r₂,r₃`), not destructive replace, with a **minimap** (reduced tree, current
  node highlighted); **(2)** **branch-off** into a separate chat (path-prefix seed); **(3) → N-77, Phase-2.**
- **§3a regeneration operations** (single-response; default whole-response, optional selected section via
  P5-lite anchors): **informed** (regen + a second "what to consider" guidance input) · **selective**
  (select a section → in-place section diff) · **preset** (longer/shorter/formal/academic/casual/humanize
  [AI-plag] / extend-by-N / compress-to-N — **preset set configurable in the launcher**) · **explain/
  elaborate a section** · **iterative grounding hardening** (cross-check + stricter citations + more
  content, additive each trigger). One extensible endpoint shape: `{op, guidance?, preset?, n?, section?}`.
- **Edit + diff:** edit responses **and** queries; **toggleable inline diff** in chat; the heavier
  **VCS-management view lives in the launcher** (simple viewer, not a main chat element). **Atomic to the
  chat — NOT git, NOT the chat-as-repo idea** (that stays a deferred rewrite exploration).
- **No-response input:** submit text → formatted/contextualized → pushed to **logs + journal**, **no model
  turn**; success via below-input-bar metrics/notif.
- Storage realised as a **DAG over the append-only event log** (parent/kind/edit_of/diff + `head.json`
  path cursor) in `ctx/chats.py` — see D-48. Multi-parent in-edges already supported (seam for N-77).

**N-76 (TRAJECTORY)** `[ ]` Phase-2 — post-response semantic trajectory-awareness + enforced-JSON
keep/alter confirmation (see §Q.7). Depends on semantic-chat-search + P2/P6.

**N-77 (SYNTHESIS / informed multi-select regen)** `[ ]` **Phase-2 (NOT MVP)** — checklist multi-select
(max **7**, configurable; one node-adjacency) of preferred responses across nodes + a new query → an
*informed* new response built from {selected responses + their queries + their retrieved content + fresh
retrieval} (ties **N-06** assembly + **P2** reference records). The DAG's multi-parent in-edges are the
reserved seam. Distinct from §3a *informed regeneration* (which is single-source).

### §Q.9 — PHASE-1 CONSOLIDATED SPEC (authoritative; is / isn't per item) — user 2026-06-20
> Supersedes the scattered splits in §Q.2/§Q.5/§Q.6/§Q.7 for *what Phase-1 contains*. Each item:
> **IS** = what it delivers · **ISN'T** = the explicit boundary (prevents scope creep). Phase-2 lives in §Q.10.

**Foundations (build first):**
- **P1 · Renderer.** **IS:** renders model responses — sections/partitions/formatting, GFM markdown,
  MDX structure, **mermaid.js**, and **non-D3 declarative charts/plots** (Vega-Lite / Chart.js); also
  renders P4 static snapshots. **ISN'T:** no runnable/executable artifacts, **no raw D3/JS**, no WASM /
  web-apps, no live interactive components, nothing needing a sandbox (→ Phase-2).
- **P2 · Reference record.** **IS:** one canonical citation object per source — `{id, url/source, title,
  snippet, chunk_locator, reasonWhy, whatInvalidates(defeater), related(graph refs)}` — rendered THREE
  ways (thumbnail title · inline citation · evidence card); model SELECTS rows, system FORMATS. Extends
  the existing `CitedResult` (D-26). **ISN'T:** not a new retrieval engine, not the ANN/chunk index (N-47).
- **P4 · Static snapshots.** **IS:** static **pre-rendered/compiled** captures of the actual retrieved
  content (web pages rendered to static image / sanitized-static, + docs), **scrolled to the relevant
  chunk**; shown as the thumbnail strip **between query and response**. **ISN'T:** not live/interactive
  embeds, not an in-window live browser, not script-executing (pre-render → freeze ⇒ no sandbox).
- **P6 · Graph (done).** **IS:** NoteStore edges linking messages/chats/notes/citations (backlinks,
  cross-refs, associative citation map). **ISN'T:** not a new store.
- **P5-lite · Addressability.** **IS:** stable ids for messages **+ sub-section anchors** + thread
  structure realised as a **DAG over the append-only log** (parent/kind/edit_of/diff + `head.json` path
  cursor; regen/edit = browsable siblings, variant-switch, branch-off; multi-parent seam for N-77) — an
  **atomic/abstract** layer that branch/reply/link target. **Data model DONE → D-48** (`ctx/chats.py`,
  back-compatible with legacy flat transcripts). **ISN'T:** not the full co-edited frame model, not shared
  docs, not concurrent editing (→ Phase-2 N-72-full); not git / chat-as-repo.
- **P7-lite · Edit→diff. DONE → D-48/D-49** (`ChatStore.edit_message` stores a unified diff; UI inline
  diff toggle + model-facing diff via `_persist_turn`). **IS:** capture an edited/regenerated response and
  present it to the model **as a diff in context**. **ISN'T:** not concurrent co-editing, not CRDT/OT, not
  the write-lock + mid-stream-annotation model (→ Phase-2).
- **N-47-lite · Chunk locator.** **IS:** a chunk offset/locator within each retrieved source (enough for
  scroll-to-chunk + snapshot positioning). **If too much effort → defer to MVP 1.1, but leave the code
  seam now.** **ISN'T:** not ANN/FAISS/HNSW, not semantic hashing, not the full §L.3/N-47 scaling.

**Phase-1 features (on the foundations):**
- **A · Flow fixes [N-10].** **IS:** kill the constant scroll-back on query/voice/transcription; fix
  thread **bloat** (virtualize/paginate + N-08 working-set clear); **non-streaming progress UX** (progress
  bar / chunked reveal — streaming already works); truthful toggles from `/health`+SSE; drop `localDraft`.
  **ISN'T:** not a UI rewrite, not the shared-space.
- **N-08 · Lifecycle (UI half).** **IS:** init / new / switch / view / restore / backup / archive over
  ChatStore (BASE done); boundary policy + clear working-set on new cycle. **ISN'T:** never deletes
  durable transcripts; not semantic chat search (Phase-2).
- **N-75 · Chat-ops. BUILT & OFFLINE-GATED → D-48/D-49** (live visual verify pending Tauri rebuild).
  **IS:** edit-as-diff · regenerate (+§3a ops: informed/grounding/preset/selective/explain) · in-chat
  variant trajectories + minimap · branch-off · no-response input · link/reference (P6). **ISN'T:** not
  shared-space co-editing, not runnable content, not kind-3 synthesis (→ N-77 Phase-2).
- **N-74 · Search-modes.** **IS:** typed enforceable modes over the unified engine — deep · socials
  (forums/threads/communities/articles) · research/patent/publication · financials · video/content ·
  tutorials/codebases/technicals · regular; each = source-set + query-shaping + render lens. **ISN'T:**
  not a new per-mode crawler (reuse web/doc arms + source filters), not semantic chat search.
- **Citations (P2 applied).** **IS:** select-not-format + chunk-locator + associative 1-/2-click (P6) +
  thumbnail titles. **ISN'T:** no end-of-response Sources block (replaced by point-of-evidence thumbnails).
- **N-27 · Cancellation.** **IS:** Rust `bridge_delete` rebuild so Stop/Esc abort the live turn.
  Regeneration rides N-75. **ISN'T:** not partial-undo; just turn abort.
- **N-67 · Integrity gate.** **IS:** every Phase-1 control real or visibly-disabled-with-reason. **ISN'T:**
  not optional — it gates Phase-1 acceptance.

### §Q.10 — PHASE-2 OFFLOAD (deferred; do NOT build in Phase-1) — to be re-specified before Phase-2
> User: "we'll specify Phase-2 later — just consolidate; offload Phase-2 content; focus Phase-1."
- **N-72-full** collaborative shared-space + **full co-edit concurrency**: single write-lock (model XOR
  user), editor non-editable while model writes, BUT user may add comments/markers/highlights/questions/
  revision-requests mid-stream → an on-the-fly refinement pass into the stream (P7-full).
- **Semantic search of chats**; **N-76 TRAJECTORY** (post-response semantic look-ahead + enforced-JSON keep/alter).
- **N-77 SYNTHESIS** (multi-select informed regen — checklist max 7, one node-adjacency; selected responses +
  their queries + retrieved content + fresh retrieval → informed new response; N-06 + P2). DAG multi-parent
  seam reserved in Phase-1. Distinct from §3a single-source informed regeneration.
- **chat-as-git-repo** (each chat a mini-repo: commit-per-message, branch/merge) — eventual UI-rewrite
  exploration only; kept distinct from N-75's atomic in-app edit/diff.
- **P3 sandbox** (runnable code / WASM / web-apps) · **D3.js** · Marp/draw.io generation · in-window live
  custom-search-engine breadth · **N-16** deep-study engine · **full N-47** ANN/chunk scaling ·
  **N-64** composition UI · **N-26** host-native UI · N-49/§L.5 full artifact vision.

---

## §R — MVP COMPLETENESS AUDIT (what's in MVP BEYOND the §Q UI work) — user 2026-06-20 "we're missing something"
> Read of §K.0.1 four gates + every open node. The UI plan (§Q) is one slice; these are the rest of MVP.

**★ THE LIKELY "MISSING" PIECE — N-32 (LOCAL-PERF, turn PIPELINE latency).** §K.0.1 gate #3
(USABLE-LOCAL) is NOT satisfied by serving alone. N-65 made *serving* ~10 tok/s, but **a full `run_turn`
still takes MINUTES** (D-21 finding) because the *pipeline* makes many sequential model calls + a
retrieval loop per turn. A 10 tok/s server behind a minutes-long pipeline is still unusable. **N-32 must
land for MVP** — budget/parallelize the per-turn calls, cap the retrieval loop, add the deadline/watchdog
(N-22). Ties directly to the chat-flow Phase-1 (a turn must feel responsive). **HIGH priority, non-UI.**

**The formal MVP gates (§K.0.1) still open:**
- **#1 INTEGRITY → N-67** UI integrity audit — **pass-1 DONE (D-51: control-surface sweep; proactive
  over-claim fixed)**; remainder = qualitative pass + D-35/39/40/41 re-grade. Blocking; also gates §Q Phase-1.
- **#2 ATOMIC/NODAL → N-66** — drive subsystems to atomic single-objective services behind stable
  contracts (HTTP+MCP), n8n-shaped. Hard MVP.
- **#3 USABLE-LOCAL → N-65 (done@10) + N-32 (OPEN, above) + N-22 watchdog.**
- **#4 DEPLOYMENT → N-59 (core stress) · N-60 (sensor/voice endurance) · N-61 (desktop/host) → N-62
  (acceptance sink).** All open. N-63 (voice) done unblocks N-60's voice lane.
- **N-68 diagrams** — RESOLVED (user 2026-06-20): **→ MVP 1.2** (other things first); not in the
  current MVP cut.

**Smaller open MVP-adjacent items (triage needed):**
- **N-22** turn deadline/watchdog (pairs N-32) · **N-21** background degrade/offload (enables proactive) ·
  **N-17** capability routing L4–L7 (esp. **L6 tools/MCP/skills** — needed for n8n-node shape + agency) ·
  **N-55** global hotkey reimplementation (open frontier) · **N-06/N-69** typed turn snapshot (recall half
  done; assembly half = deferred N-69) · **N-33** sensor-decouple `[~]` (FULL — confirm closed) ·
  **N-18/N-19/N-20/N-23** small refinement streams.
- **NEW (2026-06-20):**
  - **N-78 (HOST-PROCESS HYGIENE)** `[~]` — the Windows host accrued 100+ `aspnet_compiler.exe` +
    powershells + `msiexec`. **Root-cause fixed → D-52** (notify dedupe/throttle/cap+reap, `cli._notify`
    delegates, `screen_windows()` TTL-cached, no Popen leak). **Remaining:** audit the *other* powershell
    callers for churn/leaks (hotkey relaunch path in `desktopctl.sh`, `ctl.py` status probes, `obs`
    one-shots); prefer a single long-lived helper / WSLg-native notifier over per-event WinForms spawns.
    Feeds **#4 N-61** (desktop/host endurance).
  - **N-79 (DEBUG-LOGGING)** `[~]` — shared `debuglog.py` mechanism shipped (D-52; counters + structured
    `[debug]`, `LK_DEBUG`). **Remaining:** roll `debug(...)` calls into bridge turn, proactive (the firing
    audit), observers, schedule; surface counters on `/metrics`; add a launcher debug toggle. Supports
    N-07 firing observability + N-67 integrity.
- **N-07 (PROACTIVE)** firing-audit + scope-preserving refinement — see the 2026-06-20 refinement block at
  N-07 (significance-gated trigger · adaptive cadence · firing observability via N-79 · de-starve via N-21).
- **Carry-overs:** N-63 live-mic verify (pending hardware) · the `test_retrieval_engine` full-suite
  ordering flake (housekeeping).

**Proposed MVP completion order (non-UI), to confirm:** N-32 pipeline latency (+N-22 watchdog) →
N-67 integrity audit (pass-2) → N-66 atomic/nodal → N-59/60/61 → N-62 acceptance; **N-78/N-79 host-hygiene +
debug-logging fold into N-61/N-67**; N-07 proactive refinement rides N-21+N-79; N-68 + N-17/55 triaged in.

### §Q.11 — PHASE-2 is / isn't spec (user 2026-06-20; details §Q.10; to re-confirm before Phase-2)
> Bounds each deferred item so Phase-2 scope is unambiguous when we open it. **IS** = delivers · **ISN'T** = boundary.

- **N-72-full · Collaborative shared-space + co-edit.** **IS:** the rolling-frame shared MD/MDX doc
  co-edited by model(s)+user under a **single write-lock (model XOR user)** — editor non-editable while
  the model writes, but the user may inject **comments / markers / highlights / questions / revision-
  requests mid-stream**, triggering an **on-the-fly refinement pass into the stream**; proactive updates
  the active frame. Builds on Phase-1 P5-lite/P7-lite. **ISN'T:** no simultaneous multi-writer/multi-cursor
  editing; not a general-purpose doc editor (it's the response surface); not unbounded auto-revision.
- **Semantic chat search.** **IS:** embedding/vector search over chats/messages/responses via the existing
  MemoryIndex vector arm + unified engine, surfaced in the chat UI. **ISN'T:** not a new index/store; not
  the Phase-1 regular/keyword search; not the search-modes (N-74).
- **N-76 · Trajectory awareness.** **IS:** ONE post-response pass — semantically pull that response's
  related responses/logs/journals, infer the **query-trajectory**, feed back with an **enforced-JSON
  short keep/alter confirmation** so the model can adjust before finalizing. **ISN'T:** not pre-response;
  not a full regeneration loop; not unbounded (single confirmation, cost-capped).
- **P3 · Sandbox + runnable artifacts.** **IS:** strict-CSP iframe host to **run** model/retrieved code,
  **WASM**, small web-apps, live interactive components, raw **D3/JS** charts. **ISN'T:** no host/system
  access; not unsandboxed; not the Phase-1 static render.
- **D3.js charts.** **IS:** raw-JS custom visualizations (needs P3). **ISN'T:** not the Phase-1 declarative
  charts (Vega-Lite/Chart.js/mermaid).
- **Generated artifacts (Marp / draw.io).** **IS:** model-generated Marp.js decks + draw.io/Excalidraw-class
  diagrams with **legibility self-verification**; SQL/NoSQL table gen; MDX gen. **ISN'T:** not Phase-1; needs
  renderer + sandbox.
- **In-window live custom search engine.** **IS:** fully browsable in-window results (links/docs/papers/
  patents/socials), live navigation, **scroll-to-chunk in the actual live doc**, never bounce to an external
  browser. **ISN'T:** not the Phase-1 static snapshots + typed search-modes (N-74) — this is their live/
  interactive expansion.
- **N-16 · Deep-study engine.** **IS:** `make(spec)->path` artifact/deep-study generation, md-first under
  `memory/vault/`, real citations + provenance, provider-blind. **ISN'T:** not the inline response renderer
  (it is a generation+storage engine the UI then shows).
- **Full N-47 · ANN/chunk scaling.** **IS:** FAISS/HNSW/usearch ANN + semantic hashing for scalable
  approximate-NN + the full chunk-level index. **ISN'T:** not the Phase-1 brute-force + N-47-lite locator.
- **N-64 composition UI** (n8n workflow surface) · **N-26 host-native UI** — **IS:** post-MVP surfaces on
  the N-09 seam. **ISN'T:** not the Phase-1/2 core chat.
