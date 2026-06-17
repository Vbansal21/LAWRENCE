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

### N-01 (EMB) — Embedding seam `[ ]` — FULL
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

### N-02 (RET) — Hybrid retrieval engine 🔁 `[ ]` — FULL — supersedes D-14
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

### N-03 (WEB) — Web search & read rework `[ ]` — medium + deferral
**Pathway.** Independent start; feeds N-02 web arm + N-05. Reuses D-19 chain/pacing/
cooldown.
**Achieves + alignment.** Real search→read→extract→**embed into N-02** (reusable,
cited), policy-gated (single/deep/off per FR-003); query formulation owned by N-05.
*Soul:* web becomes relevant evidence, not a keyword dump.
**Deferral.** Soft-defer the formulation half to N-05; the read/extract/embed half
ships independently and is valuable pre-loop. Re-entry: N-02 index schema exists.

### N-04 (DOC) — Document retrieval & conversion rework `[ ]` — medium — subsumes §6 ingest
**Pathway.** Hard-dep N-01 + N-02 index schema; reuses D-16 converters. Feeds N-02
doc arm. UI button = N-12 (separate).
**Achieves + alignment.** Converters → structural chunk → embed → index with
path/page provenance + citation (FR-005: typed/cited, not opaque blobs). *Soul:*
"doc search useless" was orphaned output; this re-homes it into recall.
**Deferral.** MUST-defer-until N-01+N-02 schema; one more source into the same index.

### N-05 (LOOP) — Agentic retriever loop 🔁 `[ ]` — FULL — supersedes single-shot retrieve (FR-009)
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

### N-06 (CTX) — Turn context assembly rework 🔁 `[ ]` — FULL — supersedes screenshot-attach turn
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

### N-07 (PRO) — Proactive loop actually fires 🔁 `[ ]` — FULL — re-opens D-13
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

### N-09 (U0) — UI seam (Track 0) `[ ]` — FULL
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

### N-28 (L2) — Launcher Quit & Quit-all `[ ]` — medium + deferral *(user 2026-06-17)*
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
# cross-partition backend edges for the UI-folded nodes [revised: F2]
D-19/D-16 --dependency--> N-12        significant   /ingest + converters back the button
D-18(/voice) --dependency--> N-13     significant   voice endpoint backs PTT
```

**Executable frontier right now (no unsatisfied hard-dep, no active hard-defer):**
N-01, N-03 (read/extract half), N-09, N-21, N-27, N-28, N-29. **Recommended pick:
N-01 → N-02** (the soul-critical spine), with N-09 and N-28 as parallel low-coupling
wins.

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
