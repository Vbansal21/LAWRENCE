# LAWRENCE — DONE (constraint surface)

> **SOUL** — canonical source: **`docs/papers/LAWRENCE_v0_1_ieee.{tex,pdf}`** (the
> project paper / idea / concept). Distilled: LAWRENCE is a local-first **watcher-
> assistant**, not a stateless chatbot — it perceives continuously (screen + audio),
> turns transient activity into coherent context, remembers durably in human-readable
> linked Markdown, **recalls the right context on its own** (hybrid evidence bundle:
> lexical + vector + graph + recency + thread + journal + optional web), answers
> immediately via a parallel-facet kernel, and keeps thinking after the first answer.
> One swappable, least-trusted LLM behind a gateway; orchestration is the product.
> Litmus: *unplug the user for an hour — does it do anything useful?* It must never
> degenerate into a chat UI that staples on a screenshot and keyword-searches the web.
>
> Produced under the Planning & TODO Consolidation Protocol (BUILD→AUDIT→REVISE).
> Companion: [PLAN.md](PLAN.md). Each node: **Implemented** (concrete) ·
> **Live edges** (stubs/deferrals/assumptions that flow into PLAN) · the **N-node**
> each edge targets. Edge weights: `load-bearing` (removing/altering breaks the
> target) · `significant` (materially shapes it) · `incidental` (informational).
> Supersedes `WORK_COMPLETED.md` (deleted). Code is implementation truth.

---

## D-01 — N-tier memory (WS-M M1/M2/M3)
**Implemented.** `ctx/store.py` N-layer store (`Layer`+`DEFAULT_LAYERS`+config);
per-tier compaction role/target; zettelkasten `ctx/notes.py` (notes + `index.jsonl`
+ `[[links]]` + backlinks). Gate-tested.
**Live edges.**
- `--dependency--> N-02` **load-bearing**: L3/L2 summaries + notes are recall
  sources the hybrid retrieval must index. Break: if N-02 ignores own-memory, the
  rework fails its purpose.
- `--constraint--> N-18` **significant**: any `recent_findings`/store tail-read opt
  must hold the single-writer + golden-regression contract.
**Assumptions baked in.** Single writer (I1); default config is byte-compatible
(golden test); notes are append-only/addressable. The store was built for *recency
tail* reads, **not** semantic recall — that gap is N-02/N-06.

## D-02 — Perception → clean memory (WS-P/B1)
**Implemented.** `ctx/extract.py` + kernel `run_extract`: droppable, context-free
distill of a sensor slice → clean entry + significance + tags. Degraded-safe.
**Live edges.**
- `--dependency--> N-06` **significant**: extraction is how audio/screen become
  context text; N-06 must consume transcripts it produces.
**Assumptions baked in.** Extraction is droppable (`PRI_PROACTIVE`) — under sustained
turn load it starves (see D-06), the seed of N-21/N-07.

## D-03 — Cognitive tick + graded significance (WS-C C1/C2)
**Implemented.** `kernel/tick.py` idle-cheap heartbeat + `ctx/significance.py`
Welford mean±kσ → LOG/NOTE/STUDY. Wired into REPL + bridge.
**Live edges.**
- `--dependency--> N-07` **load-bearing**: the tick is the only thing that *fires*
  proactive; if it's disabled/starved, proactive is inert. Break: N-07's whole
  premise.
**Assumptions baked in.** One droppable action/beat; `LK_TICK` gates it; background
work yields to turns (so it can be perpetually skipped — suspect for N-07 inertness).

## D-04 — Reasoning loops (WS-R R1/R2)
**Implemented.** `kernel/refine.py` slow loop (`LK_SLOW_LOOP` default off) +
`kernel/elevate.py` shared elevation gate (better & Δconf & novel & rate-limited).
Live-smoke-validated.
**Live edges.**
- `--dependency--> N-07` **significant**: `Elevator` rate-limit is the natural home
  for proactive cooldown (N-20).
- `--dependency--> N-20` **significant** `[revised: F2 — edge cited in N-20 body, now
  drawn here]`: `LK_ELEVATE_MAX_PER_MIN` may already satisfy the proactive cooldown
  → N-20 should audit-then-possibly-close as done-by-existing.
- `--partial-completion--> N-11` **significant**: U4 in-place elevation renders the
  `refined` SSE but targets "last assistant", not turn-id.
**Assumptions baked in.** Depth-1 refine; elevation idempotent per turn-id. Audio-turn
+ `run_proactive` are **not** routed through the shared Elevator yet.

## D-05 — Journal (WS-J)
**Implemented.** Autonomous, first-person, rolling-revision durable episodic memory
(`kernel/journal.py` + addressable entries in `admin.py`), tick-driven.
**Live edges.**
- `--dependency--> N-02` **load-bearing**: journal fragments are a primary recall
  source (SCHEMAS "Retrieval Bundle"). Break: recall without journal = amnesiac.
- `--dependency--> N-08` **significant**: reuse the WS-J engine to write a per-session
  rolling chat-journal — don't build a parallel summarizer.
**Assumptions baked in.** Journal is the durable-memory spine; it is currently
written but **never retrieved into a turn** (the N-02 gap).

## D-06 — Stress-hardening campaign
**Implemented.** 6 stress suites; fixed memory data-loss race, summary-eviction,
journal corruption, observer-shutdown shadowing, malformed-POST.
**Live edges.**
- `--constraint--> N-07 / N-21` **load-bearing**: documented finding "local
  proactive/extract STARVE under sustained turn load (droppable by design)" — this
  is the prime suspect for proactive inertness and the rationale for N-21.
**Assumptions baked in.** Priority gate is correct under contention; starvation of
background roles is *by design*, mitigated only by routing them to a remote backend.

## D-07 — Launcher clean-shutdown fix
**Implemented.** Bridge reaps tick+observers on exit; `lk stop --all` force-reaps the
stateless model.
**Live edges.**
- `--dependency--> N-28` **load-bearing**: Quit-all reuses `cmd_stop --all` semantics
  + the reaping logic; it extends them with verify/escalate.
**Assumptions baked in.** Warm-on-plain-stop vs kill-on-stop-all distinction; the
model is stateless and safe to force-reap.

## D-08 — WS-U BASE: chats CRUD + cross-chat graph (Track 1/2)
**Implemented.** `ctx/chats.py ChatStore` (registry + per-chat durable transcript
`<id>/messages.jsonl` stable ids + active-pointer + auto-title + CRUD/export);
hybrid memory primitives `promote_fn`/`ingest_summary`; per-chat L1/L2 → shared L3;
NoteStore edges (chats/messages/notes as graph nodes). `/chats`+`/links`, `lk
chats`/`lk links`. Satisfies FR-002.
**Live edges.**
- `--partial-completion--> N-08` **load-bearing**: CRUD + promote primitives exist,
  but there is **no session lifecycle** — `ensure_default()` makes one "Scratch"
  chat and appends forever → unbounded bloat. Break: the user's "single long bloated
  list" is exactly this missing piece.
- `--dependency--> N-02` **load-bearing**: NoteStore edges = the graph arm of hybrid
  retrieval; past chats/turns are recall sources.
- `--dependency--> N-11` **significant**: Track B must render sessions/recall/links,
  not one infinite scroll.
**Assumptions baked in.** Transcript is append-only/unbounded; "one mind, per-chat
working set" hybrid model; ambient=global, conversation=per-chat (merged at read).
`[revised: F4 — clarify the N-08 boundary]` **N-08 does NOT delete this durable
transcript** — it clears only the per-session *working memory* (L1/L2) on a new cycle
and changes the *recall surface*; the append-only `messages.jsonl` + its journal
summary persist and stay recallable. So N-08 does not violate D-08's append-only
invariant; "bloat" = the unbounded *working stream fed to the model*, not the archive.

## D-09 — Job cancel + hard timeouts (§3)
**Implemented.** `DELETE /jobs/{id}` cooperative cancel; local non-streaming
wall-clock deadline; releases gate; no memory write on cancel.
**Live edges.**
- `--dependency--> N-27` **load-bearing**: Rust `bridge_delete` exists; UI Stop/Esc
  dark until the Tauri shell rebuilds. Break: cancel is backend-only.
- `--dependency--> N-05 / N-22` **significant**: the deadline machinery bounds the
  retriever loop and any long op.
- `--dependency--> N-16` **significant** `[revised: F2 — cited in N-16 body, now drawn
  here]`: artifact jobs are async + cancellable, reusing this cancel/deadline path.
**Assumptions baked in.** Cooperative (not kill) cancel; `TurnCancelled` raised
through the stream loops; idempotent on terminal jobs.

## D-10 — Capability routing core (§4 / WS-K layers 1–3)
**Implemented.** Data-driven `capabilities.py` (single source of truth =
`model._API_OPTION_KEYS`); resolver → active/inactive/unavailable; `/health.capabilities`
+ per-turn `uiInactiveConfig`/`uiUnavailableConfig`.
**Live edges.**
- `--partial-completion--> N-17` **significant**: layers 4–7 (schema routing, prefill
  enforcement, tools/MCP/skills, probe→cache) unbuilt.
- `--partial-completion--> N-15` **significant**: backend buckets exist; popup
  per-control markers not rendered (launcher does).
**Assumptions baked in.** Registry is *data*, not `if provider==` (I3); unsupported
fields persisted-but-never-sent.

## D-11 — UI truth cleanup: launcher surface (§5 partial)
**Implemented.** Launcher renders only kernel-backed state; honest `/metrics`
(null⇒n/a); dots/chip from `/health`+lock+config.
**Live edges.**
- `--partial-completion--> N-10` **significant**: the popup `app.js` still has
  `localDraft` fabricated answers + hollow toggles.
**Assumptions baked in.** `/metrics` shape is fixed; subsystems report null until
they learn to publish.

## D-12 — Scheduler / reminders backend (§8)
**Implemented.** `schedule.py` durable append-only log; fires exactly once,
restart-safe; tz-aware; model-free; tick `due_fn`/`fire_fn`; `/reminders` + CLI.
**Live edges.**
- `--partial-completion--> N-14` **load-bearing**: panel/badge UI must read
  `/health.reminders` (backend truth), not localStorage. Break: the hollow panel.
**Assumptions baked in.** One-shot only (recurrence cut); badge count from backend.

## D-13 — Proactive dedup + stale guard (§9)
**Implemented.** `ctx/store.py` monotone `_version` + `recent_findings`;
`run_proactive` stale-drop + difflib dedup. Both drops silent.
**Live edges.**
- `--partial-completion--> N-07` **load-bearing**: the dedup/stale *logic* landed,
  but the user reports **proactive does not actually fire**. The "done" is a guard on
  a loop that may never run. Break: N-07 re-opens the end-to-end behavior.
- `--dependency--> N-02` **significant**: dedup compares findings; N-02's unified
  index may subsume `recent_findings`.
**Assumptions baked in.** A proactive finding will actually be produced (untested
end-to-end under real load); `recent_findings` parses the full resident layer (N-18).

## D-14 — Retrieval dedup / caps / recency (§10)
**Implemented.** `retrieval/pipeline.py` near-dup collapse + per-URL cap(3) +
recency nudge; `file://` never stale; stable citation numbering.
**Live edges.**
- `--conflict--> N-02` **load-bearing**: **the assumption baked here is the
  problem** — retrieval is **lexical BM25 + SQLite FTS5, web/doc only, single-shot
  off keyword guesses, with ZERO embeddings and ZERO recall over the agent's own
  memory.** N-02 is a 🔁 TOTAL REWORK that supersedes this. Break/resolution: §10's
  *behaviors* (cap, recency, file://-never-stale, dedup, numbering) survive as N-02
  regression tests; its *substance* is replaced.
**Assumptions baked in (the regression the rework must undo).** "Semantic DB" is a
misnomer — it is lexical. Retrieval = external evidence only; the agent never
recalls its own journal/notes/L3/turns/transcripts. Queries are model-guessed
keywords, used once.

## D-15 — Launcher rework (§15)
**Implemented.** 4 surfaces → 2 over one `actions.py` registry (+ lifted admission
gate); PySide6+pyte window (front view, tabs, read-only-default PTY consoles, guided
Tier-4 editor) + stdlib console; honest `/metrics`. Gate=30 suites.
**Live edges.**
- `--dependency--> N-28` **load-bearing**: Quit/Quit-all are two new `actions.py`
  registry entries wired into both surfaces. Break: no full-stop control today.
- `--partial-completion--> N-18/N-19/N-20/N-21/N-22/N-23` **significant**: R/A/R3
  streams explicitly deferred from this rework's scope.
**Assumptions baked in.** Registry is the single source for GUI+console; Qt imports
lazy off the control path; `[gui]` extra records PySide6+pyte.

## D-16 — Converter engine
**Implemented.** `converters.py` (text/md/latex/html/json/jsonl/xml/csv/tsv/image/
+yaml/xlsx) + `retrieval/ingest.py`; `test_converters` green in isolation.
**Live edges.**
- `--partial-completion--> N-04` **significant**: converters work but feed a
  lexical-only, rarely-recalled index with no provenance/citation typing (FR-005).
  Break: "doc conversion useless" is the orphaned-output symptom, not a converter bug.
**Assumptions baked in.** Conversion is correct; chunking is naive; output lands in
the lexical FTS, not a typed/embedded/cited index.

## D-17 — Backends / per-role routing / secrets (V3.T1/T2)
**Implemented.** `config.py` PROVIDERS + routing; `model.py` thread-local per-role
backend + local fallback; secrets in `~/.lawrence/secrets.env` (off-repo). Native
Anthropic; OpenAI-compat (Gemini/OpenRouter/POE/LM Studio).
**Live edges.**
- `--dependency--> N-01` **load-bearing**: `embed()` routes through this same seam
  (local `/embedding` or API `/embeddings`) as a background role. Break: no embedding
  transport without it.
- `--dependency--> N-21` **significant**: per-role routing is the offload mechanism
  for starved background roles.
**Assumptions baked in.** Provider logic only in `model.py` (I3); background roles
routable to a fast API with local fallback.

## D-18 — Observers: vision + audio capture
**Implemented.** Vision foreground-window capture + per-window OCR + RegionTracker;
audio parec + whisper + VAD + gates. Both distill into context.
**Live edges.**
- `--constraint--> N-06` **load-bearing**: today vision is the loud channel (screenshot
  attach) and audio→context is underwired (V3.T4 open: a turn-per-chunk bug history).
  N-06 must invert this to "audio/text primary, vision secondary" (ARCHITECTURE).
  Break: the screenshot-centric turn is exactly this assumption.
**Assumptions baked in.** Capture is heavy on CPU (hi-res vision encode = latency
killer, V3.T7); audio is sampled but its transcript isn't a first-class recall source.

## D-19 — Web provider chain + ingest path (P6.T1/T2)
**Implemented.** `retrieval/web.py` provider chain (ddg_html→ddg_lite→searxng→brave)
+ pacing + bot-block cooldown + `search_stats` in `/health`; `/ingest` + `lk ingest`.
**Live edges.**
- `--partial-completion--> N-03` **significant**: the chain/pacing/cooldown are
  reusable; query *formulation* is raw-keyword and *reading* is single-shot.
- `--partial-completion--> N-05` **significant**: web is retrieved once, not in an
  iterative assess→refine loop (FR-009).
**Assumptions baked in.** Web = keyword search of DDG; one pass; results ranked by
BM25; no embedding of fetched pages for reuse.

---

## Live-stub index (every D-node's outflow, for audit) `[revised: F2 — added D-04→N-20, D-09→N-16]`
D-01→N-02,N-18 · D-02→N-06 · D-03→N-07 · D-04→N-07,N-11,N-20 · D-05→N-02,N-08 ·
D-06→N-07,N-21 · D-07→N-28 · D-08→N-08,N-02,N-11 · D-09→N-27,N-05,N-22,N-16 ·
D-10→N-17,N-15 · D-11→N-10 · D-12→N-14 · D-13→N-07,N-02 · **D-14→N-02 (conflict)** ·
D-15→N-28,N-18..N-23 · D-16→N-04 · D-17→N-01,N-21 · D-18→N-06 · D-19→N-03,N-05,N-12,N-13.

*(No D-node is a sink with zero outflow — every done item has a live follow-up, as
expected mid-stream. N-09/N-19/N-24/N-25/N-26/N-29/N-30 are genuinely independent of
the tracked done-graph; N-09/N-26 lean on existing **app.js / host scaffolding** that
predates this tracker and is not itself a D-node — see PLAN.md §H audit F1.)*
