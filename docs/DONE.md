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
>
> **MVP consolidation (2026-06-18):** the SOUL above is user-confirmed. D-27 is
> the current-state verification boundary for the running-MVP phase. Earlier
> "local-first default" wording records the state at that task's completion; the
> current selected runtime is cloud-first (Gemini) until MVP acceptance, while
> local llama.cpp compatibility remains mandatory.

---

## §0 — Consolidated DONE roll-up (verification status — 2026-06-19)

> **What this is.** A single compact, scannable record of every completed node,
> consolidated from PLAN.md's done-markers (`[x]` / SHIPPED) and **graded by what was
> actually verified in this session** vs. documented from prior runs. Detailed
> per-node entries (with live-edges) follow below; the open/concept frontier stays in
> PLAN.md (open §A–§I nodes + §L concepts).
>
> **Legend** — ✅ offline gate (`make check`, ~39 suites — **re-run & PASS 2026-06-19**)
> + source inspected this session · ⚠ live behavior documented from prior runs,
> **NOT re-run this session** (needs running bridge + network + Gemini key) · ➖ superseded
> (its behaviors survive as regression guards inside a later node).

| D | Node | One-line | Verified |
|---|---|---|---|
| D-01 | N-tier memory | configurable rolling tiers + dynamic budget + cascade compaction | ✅ |
| D-02 | perception→clean | droppable extract distils a sensor slice before memory | ✅ |
| D-03 | tick + significance | idle-cheap heartbeat + Welford LOG/NOTE/STUDY | ✅ |
| D-04 | reasoning loops | slow refine + shared elevation gate | ✅ |
| D-05 | journal (WS-J) | autonomous first-person rolling-revision episodic memory | ✅ |
| D-06 | stress-hardening | 6 suites; data-loss/eviction/corruption races fixed | ✅ |
| D-07 | launcher shutdown | bridge reaps tick+observers; `stop --all` force-reaps | ✅ |
| D-08 | chats + graph | ChatStore CRUD + per-chat transcript + NoteStore edges | ✅ |
| D-09 | cancel + timeouts | cooperative `DELETE /jobs`; wall-clock deadline | ✅ |
| D-10 | capability routing | data-driven resolver; `/health.capabilities` | ✅ |
| D-11 | UI truth (launcher) | launcher renders only kernel-backed state | ✅ |
| D-12 | scheduler/reminders | durable one-shot fire; tz-aware; `/reminders` | ✅ |
| D-13 | proactive dedup | version/stale-drop + difflib dedup (firing proven D-32) | ✅ |
| D-14 | retrieval caps/recency | dedup + per-URL cap + recency nudge | ➖ |
| D-15 | launcher rework | 4→2 surfaces over one registry; PySide6+pyte | ✅ |
| D-16 | converter engine | text/pdf/docx/html/csv/… + ingest chunker | ✅ |
| D-17 | backends/routing | per-role routing; secrets off-repo; multi-provider | ✅ |
| D-18 | observers | vision capture+OCR; audio parec+whisper+VAD | ✅ (audio path re-checked offline today) |
| D-19 | web chain + ingest | ddg/searxng/brave + pacing; `/ingest` | ✅ code · ⚠ fresh web degraded (DDG blocks) |
| D-20 | embedding seam | `embed()` role-routed + `VectorIndex` exact cosine (no FAISS) | ✅ |
| D-21 | operational spine | local-first default, launcher opens, sensors auto-start | ✅ · ⚠ local turn latency (minutes) |
| D-22 | sensors decoupled | schema probe-only; model can't toggle lifecycle | ✅ |
| D-23 | UI seam (N-09) | one transport module + variant switch; zero visual change | ✅ |
| D-24 | hybrid recall (N-02) | MemoryIndex: RRF lexical+vector+graph+recency+link/del | ✅ |
| D-25 | recall in turn (N-06 core) | `[RECALLED MEMORY]` block injected per turn | ✅ |
| D-26 | unified engine (N-05) | discern→parallel arms→assess/refine→RRF+BM25 cited bundle | ✅ |
| D-27 | MVP substrate verify | honest current-state boundary (lists runtime caveats) | ✅ (as honest doc) |
| D-28 | cloud-first smoke | `make mvp-smoke`: start→cited turn→index→stop | ⚠ |
| D-29 | model-indep sensors | observers start from config, not model modality | ✅ gate · ⚠ live hour |
| D-30 | frozen context | immutable versioned `ContextSnapshot` per run | ✅ |
| D-31 | retrieval quality | labeled corpus recall@5/MRR + live corpus | ✅ gate · ⚠ live smoke |
| D-32 | unattended autonomy | proactive/journal fire; cooldown-on-success | ✅ gate · ⚠ live smoke/hour |
| D-33 | privacy boundary | redact/gate/audit (hash-only); confirm effectors | ✅ |
| D-34 | confirmed agency | allowlist + one-use token; atomic artifact write | ✅ code · ⚠ live smoke |
| D-35 | truthful classic UI | no fabricated answers; real reminders/chats/actions | ✅ gate · ⚠ live DOM harness |
| D-36 | local llama.cpp compat | random-turn parity; p50 31.8s/p95 98.6s CPU | ⚠ |
| D-37 | local KV checkpoint | profile-keyed text-only slot save/restore | ⚠ |
| D-38 | running e2e MVP accept | SOUL loop runs as one system (aggregated terminal evidence) | ⚠ |

**Net (2026-06-19).** D-01…D-26 plus the **offline-testable portions** of D-27…D-38
are ✅ gate+code verified by me this session. The **live MVP behaviors** (D-28/31/32/34/36/37/38
smoke runs, the unattended hour, local latency, KV restart) are ⚠ — the code is real and
the offline gate is green, but their *live numbers* are prior-run documentation I did **not**
reproduce here (no running server / network / Gemini key). Runtime posture is **cloud-first
(Gemini)**; **no local embed GGUF installed**, so the vector arm degrades to lexical+graph
locally. To upgrade any ⚠ to ✅: run the relevant `make *-smoke` against a live bridge.

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

## D-20 — Embedding seam (N-01 built) — **LOCAL-FIRST**
**Implemented.** `model.embed(texts, role="embed")` — OpenAI-compatible
`/embeddings` transport through the **same role-routing seam as `call_model`**
(invariant I3), batched + order-restoring (by response `index`). **Local-first by
design:** the default serves a **dedicated, kernel-managed local embedding
server** — `server.ensure_embeddings()` lazily starts a *second* llama-server
(`--embeddings`, on `EMB_PORT 8191`, chat untouched on 8190) from a local
embedding GGUF auto-discovered in `models/local/embed/` (or `embed_model_path`);
`stop()` reaps it. Personal memory is embedded on-device and never leaves the
machine. The API path is an **opt-in TESTING convenience only** — `embed` is
deliberately NOT in `BACKGROUND_ROLES`, so no preset ships personal data to a
cloud; a user opts in with `{"routing":{"embed":"gemini"}}`. Anthropic has no
embeddings API → routes around it to local. `retrieval/vectors.py VectorIndex`:
exact cosine over a packed L2-normalised float32 matrix (numpy-accelerated;
**pure-Python fallback keeps the core stdlib-only, I4; no ANN dep**), stdlib
on-disk persistence (`array('f')` blob + JSON, numpy-independent). Config:
`embed_model_path`/`embed_pooling`/`embed_model`/`embed_url` round-trip through
`lk config`; `numpy` optional extra (`.[embed]`/`.[full]`). **Verified end-to-end
live** (embed→VectorIndex→cosine search retrieves the right doc) via the testing
Gemini route (`gemini-embedding-001`, dim 3072; `text-embedding-004` is 404 on
v1beta). Gate = `test_embed.py` (VectorIndex numpy + forced pure-Python; embed
routing/order/batching/degrade/local-fallback/local-first-graceful), 30-suite
`make check` green.
**Live edges.**
- `--dependency--> N-02` **load-bearing**: `VectorIndex` is the vector arm and
  `embed()` is how each source becomes a vector; N-02 fuses it (RRF) with the
  FTS5 lexical arm + NoteStore graph arm. Break: no semantic recall — the spine.
- `--dependency--> N-06/N-07/N-08` **significant**: the semantic-recall surface
  they consume flows from this seam (via N-02).
**Assumptions baked in.** Embedding dim is discovered at first use and recorded
in the index (no fixed-dim config). Local embeddings require the server started
`--embeddings` **or** `LK_EMBED_URL` pointing at a dedicated embed server; absent
that, the vector arm is unavailable and retrieval must degrade to lexical+graph
(callers treat an `embed()` RuntimeError as "vector arm down", never a turn
failure — the degraded-path doctrine). Satisfies D-17's `--dependency--> N-01`.

## D-21 — Operational spine made to work as envisioned (launcher + kernel + server, LOCAL-FIRST)
**Implemented.** A "carefully, this time" pass to make the *existing* launcher,
kernel and server actually run as designed (user directive 2026-06-17), before any
UI revision or new features:
- **Local-first default restored.** `lk.json` was fully cloud-routed (`backend:
  gemini`, every role → gemini); the local llama-server was never exercised.
  Switched to the `local` preset (backend local, no routing) — kernel + server now
  run on-device. Reversible (`lk preset use hybrid|gemini`); prior config backed up
  to `.runtime/lk.json.gemini-bak`; secrets untouched. See [[lawrence-local-first]].
- **Launcher GUI opens under WSLg.** Qt auto-selected the *unshipped* `wayland` QPA
  plugin (WAYLAND_DISPLAY set) → the window silently never appeared. `qt_app.
  _select_qt_platform()` forces `xcb` when an X display exists (honours an explicit
  `QT_QPA_PLATFORM`, incl. `offscreen` tests). Verified: real window on the
  2880×1800 screen; single-instance raise works.
- **Sensors perceive at boot.** Observers only started on a UI `/observer` POST →
  always inactive on a headless/auto start. `BridgeState._autostart_observers()`
  starts sensors per config (LK_VISION/LK_AUDIO), best-effort + dep-gated (text-only
  model or missing capture tool → off with a logged reason, never a startup
  failure). Verified: vision active at boot (`observers.vision` True, `pipeline.
  visual` "observer active"); audio off by default (not enabled → no silent mic).
  Launcher front view now reads sensors **active** + detailed "vision on · audio off".
- **Launcher Quit + Quit-all (= N-28).** `quit` (tier-1, closes the launcher ONLY;
  services keep running) + `quit_all` (tier-2 dropdown, confirm-gated; terminates
  EVERY LAWRENCE process incl. other launcher windows, then re-scans + reports
  survivors). One source — `ctl.quit_all()` + `lk quit-all [--yes]` — rendered by
  both the Qt front view (`_quit_all`) and the stdlib console (`_act_quit_all`).
- **Started-process logs viewable.** Front-view actions ran detached with stdout/
  stderr → /dev/null (output lost), and the Consoles tab lacked popup/embed logs.
  Front actions now stream through the console seam (output visible + auto-switch to
  Consoles); ConsolesTab gained **Popup log** (`.runtime/desktop/app.log`) and
  **Embed log** (`.runtime/lk-embed-server.log`) live tails beside Server/Bridge.
- **`lk doctor` honesty.** Probed the obsolete `tkinter`; now probes PySide6 + pyte.
- Gate: `make check` green (30 suites); launcher suite + headless build verified the
  new front Quit action + 6 console tabs.
**Live edges.**
- `--finding--> N-32 (local turn latency)` **load-bearing**: a full `run_turn` takes
  *minutes* on CPU though the raw llama-server completes in ~0.7s — the bottleneck is
  the turn pipeline (multiple model calls + gemma thinking-token burn), NOT the
  server. This is the headline "optimise for local" lever (see [[lawrence-thinking-
  token-budget]]); levers: `LK_THINKING` / per-role token ceilings / pipeline call
  count. Opened as **N-32**.
- `--dependency--> N-09/N-11` **significant**: launcher consoles + sensor honesty
  inform the eventual UI revision (next, per the user's stated order).
**Assumptions baked in.** Local model present + llama-server built (verified);
vision capture via `powershell.exe` works on WSLg; audio stays opt-in (parec is
available but NOT enabled by default — privacy). Satisfies D-07/D-15's
`--dependency--> N-28`.

## D-22 — Sensors decoupled from the model (probe-only) — first step of N-33
**Implemented.** A user directive (2026-06-17): *sensors are independent, always-on
services the USER controls; the model only probes them for data and never drives
their lifecycle.* Verifying D-21 via the gemini route surfaced the root cause of
"sensors always inactive": the turn schema marked `controls.{vision,audio}` as
**required**, so the model emitted a default `"off"` every turn → `_apply_model_
controls` actuated it → the auto-started observers died after the first turn.
- **Schema** (`kernel/schemas.py`): `controls` no longer requires vision/audio;
  they are optional and documented as probe-only (not lifecycle).
- **Prompt** (`kernel/prompts.py`): tells the model the sensors are always-on,
  user-controlled services it must NOT turn on/off; the only control it may request
  is `vision: "hi"` (a one-off fresh screen capture / probe).
- **Handlers** (`ui_bridge._apply_model_controls` + REPL `cli._apply_controls`):
  honor only `vision:"hi"` (one-shot `capture_now`, works even if the ambient
  observer is off); `"on"/"off"` are ignored — sensor start/stop is a user action
  (UI `/observer` toggle · `/vision on|off` · config). **Verified live (gemini):**
  vision auto-starts at boot and **stays on across multiple turns**; the model now
  emits no vision/audio controls at all. `make check` green (30 suites).
**Live edges.**
- `--dependency--> N-33` **load-bearing**: this is step 1 (sever model→sensor
  control). N-33 carries the rest — sensors as continuous services feeding
  OCR/transcription/logging/context/tracking/adaptation, the model *probing* that
  data (= N-02), and the proactive loop extrapolated onto the stream (= N-07).
- `--deferred--> N-33` **significant**: the "model may relay an OFF only when a
  user/voice/proactive query explicitly asks" case needs an intent-aware path
  (not the per-turn envelope) — deferred to N-33.
**Assumptions baked in.** A per-turn control envelope is the wrong place to carry a
device-lifecycle command (models over-fill it). Probe (`hi`) is safe + stateless.

---

## D-23 — UI seam: the base made robust to the UI (N-09, Track 0)
**Implemented.** WS-U Track 0 (the keystone of the existing-UI revision): two front-ends
can now coexist over one stable bridge/SSE contract, so the UI is as swappable as the
model — with **zero visual change** to today's overlay. Pure extraction + indirection;
**no Rust change**.
- **One transport module** (`apps/desktop/web/lib/bridge.js`, NEW): the *only* code
  allowed to touch the bridge — `bridgeBaseUrl`/`fetchJson`/`postBridge`/`getBridge`/
  `deleteBridge` (Tauri `invoke("bridge_*")` with a `fetch` fallback) + `connectEvents
  (url,onPayload,onError)` owning the single deduped `EventSource` and JSON-parsing each
  frame. A variant supplies the `payload.type` dispatch; it never opens its own socket.
- **Classic variant** (`web/app.js` → `web/variants/classic/app.js`, git-moved, 2368
  lines): identical logic, except it now `import`s transport from `../../lib/bridge.js`
  and delegates `connectEvents`. (It still uses `__TAURI__` for native **shell** APIs —
  windows, panels, `open_url` — a legitimate front-end concern, not bridge transport.)
- **Variant switch** (`web/bootstrap.js`, NEW; `index.html` now loads it): reads
  `uiVariant` from `/health`, dynamic-imports `./variants/<v>/app.js`, and on **any**
  error falls back to classic so the UI never comes up blank. `?uiVariant=` honored in
  dev (file://localhost) only.
- **Config + health**: `ui_variant`→`LK_UI_VARIANT` in `config.py` `_ENV_MAP` (default
  `classic`, GUI==CLI round-trip); `/health` advertises `uiVariant` (`ui_bridge.py`).
- **Tests/build**: `stress_ui.py` section D repointed to the classic variant + new
  section I (transport isolation: no variant calls `window.fetch`/`new EventSource`/
  `bridge_*` invoke directly; bootstrap reads health + falls back; `node --check` on all
  three entrypoints). `scripts/check.sh` + `apps/desktop/scripts/stress-ui.sh` node-check
  the three entrypoints. **`make check` green (30 suites).**
**Live edges.**
- `--dependency--> N-10` **load-bearing**: Track A (classic refactor — vendor markdown,
  drop `localDraft`, truthful toggles) builds on this seam.
- `--dependency--> N-11` **load-bearing**: the `palette` variant is a sibling under
  `web/variants/` selected by `ui_variant` with no Rust rebuild.
- `--enables--> N-12,N-13,N-14,N-15` **significant**: folded UI nodes land in a variant.
**Assumptions baked in.** Transport was already cleanly isolated in app.js, so the seam
is extraction, not new transport. The embedded frontend means a `cargo build --release`
+ relaunch is needed to *see* it live; the offline gate proves the contract statically.

## D-24 — Hybrid recall over own memory (N-02 RET — the keystone; supersedes D-14)
**Implemented.** The *probe*: the watcher now recalls the right context on its own from
its OWN memory, instead of replaying a recency tail. New unified index + fused recall —
the highest-soul-alignment node, and the apex of the autonomous context spine.
- **`retrieval/memory.py` (NEW) — `MemoryIndex`**: one durable SQLite store
  (`memory/memory_index.db`) of every memory node (`source_kind`+ts+provenance+text+
  embedding blob), with three retrieval **arms** fused by **Reciprocal Rank Fusion**
  (parameterless): **lexical** (FTS5/BM25, LIKE fallback), **vector** (cosine over the
  D-20 `VectorIndex`, rebuilt in-memory from the SQLite blobs on load — single source of
  truth, no second file to desync), and **graph** (NoteStore neighbourhood expansion).
  Post-fusion shaping per the paper's `S_ret`: a **recency** multiplier (R, half-life
  decay), a **link boost** (G — explicit `link` edges promote a node), and a reversible
  **delete penalty** (P — `mark_deleted`/`clear_deleted` suppress a node without dropping
  it). A cosine floor keeps the dense arm from injecting near-orthogonal noise. Results
  are provenance-tagged (`RecallResult`: node_id/kind/ts/text/score/arms).
- **LOCAL-FIRST** ([[lawrence-local-first]]): the vector arm embeds via `model.embed`
  (local server first; API opt-in only). No embedding backend ⇒ the arm is *skipped*,
  never fatal — recall degrades to lexical+graph. Heavy deps lazy (I4); numpy only
  accelerates the scan.
- **`retrieval/reindex.py` (NEW)**: `backfill()` indexes notes/chats/rolling/log/journal
  (idempotent by text-hash → cheap re-runs); `startup_backfill()` does a fast
  lexical/graph pass synchronously then fills the vector arm on a **background** thread so
  a cold embed backend never delays kernel start. `lk reindex [--no-embed]` is the manual
  full rebuild (writer-lock-guarded).
- **Tests**: `tests/test_memory_index.py` (offline, deterministic stub embed) — RRF,
  recency, lexical, isolated-vector, graph expansion + link boost, delete penalty,
  degrade-without-embed, persistence reopen, 5-source backfill, `format_recall`.
  Smoke-verified live over the real `memory/` (97 nodes across all five kinds).
  **`make check` green (31 suites).**
**Live edges.**
- `--dependency--> N-06` **load-bearing**: recall composition consumes `recall()` (core
  landed = D-25). `--dependency--> N-07` **load-bearing**: proactive findings ride recall.
- `--dependency--> N-05` **significant**: the agentic retriever loop orchestrates over
  `recall()` (bounded rounds) — not yet built.
- `--enables--> N-03 (web arm),N-04 (doc arm)` **significant**: more sources into the same
  `source_kind` index/fusion.
- `--feeds--> N-08/N-10/N-11` **significant**: the chat link/delete UX feeds G/P signals
  (`add_edge`/`mark_deleted`) rather than hard-mutating a working set (weighted relevance).
**Assumptions baked in.** Own-memory is the apex; web stays in `SemanticDB` (N-03 fuses
later). Startup vector backfill is best-effort/background. SQLite serialized-mode allows
the background embed thread + loop to share one connection (same contract as `SemanticDB`).

## D-25 — Recall composed into the turn (N-06 core; partial)
**Implemented.** The recall→turn half of N-06: `run_turn` now takes an optional
`memory: MemoryIndex` and, before the response pass, runs **one** hybrid `recall(user_text)`
over own memory and injects a provenance-tagged `[RECALLED MEMORY]` block (`format_recall`,
budget-bounded) right after the working-memory tail. Best-effort: a recall failure (incl.
no embedding backend) never breaks the turn. Wired in **both** kernels (REPL `cli.py` +
UI bridge `ui_bridge.py`): each builds a `MemoryIndex`, routes note writes into it
(alongside `SemanticDB`), runs `startup_backfill`, and the bridge indexes each durable
chat message as it is written (so past conversation becomes recallable). The `/links`
endpoint already feeds the +G link boost for free (NoteStore edges).
**Live edges.**
- `--remaining--> N-06` **load-bearing**: the rest of N-06 (demote vision to distilled-
  secondary + on-request hi-res; include audio transcript primary; recall/recency budget
  split tuning) is **not** done — only the recall-composition half landed.
- `--dependency--> N-05` **significant**: today it is single-shot recall/turn; the bounded
  retriever loop wraps it later.
- `--feeds--> N-07` **load-bearing**: proactive reuses the same recall path.
**Assumptions baked in.** One recall call/turn (matches the plan). Recall is injected into
the *response* pass only (kept out of analysis to protect the thinking-token budget,
[[lawrence-thinking-token-budget]]). `memory=None` ⇒ identical pre-N-06 behaviour.

---

## D-26 — Unified Perplexity retrieval engine (N-05 LOOP; folds N-03/N-04 as categories; closes the N-02→N-06→N-07 loop)
**Implemented (build contract = PLAN.md §J, steps RE-1…RE-13).** The single-shot
`analysis → one retrieve → answer` path is replaced by `retrieval/engine.py`
`RetrievalEngine.gather()` — a context-grounded, configurable+dynamic, Perplexity-style loop:
- **DISCERN (Phase A).** One `retrieve`-role model call (schema `RETRIEVAL_PLAN`, prompt
  `prompts.RETRIEVAL_PLAN`) drafts the *current situation* (the "Raw/draft") from the short
  rolling tail + a long recall/summary digest, and ONLY from that emits per-category queries
  (notes/doc/web) + `capture_hires`. Degrade: model down → heuristic token queries from the
  need, so retrieval still runs.
- **PER-CATEGORY PARALLEL CHAINS (Phase B).** Each category runs its own retrieve→rank chain
  in a thread: **notes** = `MemoryIndex.recall` (hybrid lexical+vector+graph+recency+link/del),
  **doc** = `SemanticDB` `file://` rows (BM25), **web** = cached web rows ∪ fresh
  search→read→extract (D-19 chain), BM25-ranked. Under-filled arms get refined queries from a
  single shared **ASSESS** call (schema `RETRIEVAL_ASSESS`) and loop; the model's `sufficient`
  verdict is the dynamic stop, `max_iter` + `should_stop`/deadline (D-09) the hard caps. A
  failing arm is isolated; a missing backend skips its arm (never fatal).
- **FINAL COLLECTIVE RANK (Phase C).** RRF across the per-arm rankings (reuses `memory._rrf`)
  blended with a global BM25 score → one **consistently-cited** bundle (`CitedResult` now
  carries `category`; memory is cited as `memory://<id>`). `evidence_assets()` maps it to
  typed FR-008 cards.
**Local-first ([[lawrence-local-first]]).** New `retrieve` role added to `ALL_ROLES` but **not**
`BACKGROUND_ROLES` → DISCERN/ASSESS default to the LOCAL backend (planning over personal
context never ships to cloud; API opt-in via `routing.retrieve`).
**Wiring + loop closure.** `run_turn(…, engine=…)` uses the engine (own memory is now a cited
category in ONE bundle, not a side block); `run_proactive(…, engine=…, memory=…)` rides the
same notes+doc+web evidence (N-07 findings no longer web-only). **Live incremental indexing**
closes perceive→remember→recall→act: completed turns, proactive findings, and new journal
entries are `memory.upsert`'d immediately (lexical/graph now; embedding via background
backfill / `lk reindex`). Constructed in **both** kernels (`cli.py` + `ui_bridge.py`); the
UI magnifier's `deepSearch` maps to `cfg.deep_search` → a wider/deeper per-turn profile.
**Config.** `LK_RETRIEVAL[_ENFORCE|_CATEGORIES|_ITERS|_ASSESS|_TOP_K|_MIN_RESULTS|_DEPTH|
_DEEP_ITERS|_DEEP_TOPK|_DEEP_FRESH]` — all live-patchable; "enforced" = an enabled category
runs every turn regardless of the classifier (FR-003).
**Tests.** `tests/test_retrieval_engine.py` (22 checks, offline, stub model + real
MemoryIndex/SemanticDB, web fetch neutralised): discern, parallel arms, arm isolation,
dynamic iterate/stop, collective fusion + consistent 1..N citations, FR-008 assets, and every
degrade path. In `make check` (now 32 suites) + `make test`. Real-data smoke: notes arm fused
correctly over the live 97-node corpus via the degrade path.
**Live edges.**
- `--realizes--> N-05` **load-bearing**: this IS the agentic retriever loop (bounded,
  assess-refine, deadline-capped).
- `--subsumes--> N-03,N-04` **significant**: web + doc are now retrieval *categories* in the
  engine (full doc ingest UI = N-12; deep-study artifacts = N-16 consume this later).
- `--completes--> N-06` **load-bearing**: recall is now a first-class cited category, not a
  side block (the vision-demote/transcript half of N-06 remains).
- `--feeds--> N-07` **load-bearing**: proactive findings ride notes+doc+web via the engine.
- `--relates--> N-32` **significant**: ≤2 model calls/turn by default (discern + ≤1 assess),
  all `retrieve`-role-routable + deadline-bounded; iteration cap is the latency lever.
**Assumptions baked in.** `engine=None` ⇒ legacy analysis+recall+single-shot path (back-compat
/ tests). The full web/doc arms + model DISCERN/ASSESS need a running model + network (not
exercised offline); architecture/fusion/iteration/degrade are gate-covered. RRF across arms
fuses disjoint key-spaces fairly (no arm starved); the global BM25 blend rewards lexical
strength.

## D-27 — Current MVP substrate verification (2026-06-18)
**Implemented and verified.** Current tree at `83ae0ee`: `make check` passes every
offline/stress suite; Tauri `cargo check` passes; desktop runtime contract passes;
the DOM feature harness passes 24 declared behaviors. The live code contains:
algorithmic screen/audio observers, extraction + information-gain gating, graded
significance, tick-driven proactive/journal/reminder hooks, N-tier rolling memory,
atomic Markdown notes, durable chats, hybrid own-memory recall, unified
notes/doc/web retrieval, provider routing, cancellation, bridge/SSE, and the classic
Tauri surface.

**Observed runtime truth (not aspirational).**
- `.runtime/lk.json` currently selects Gemini and routes foreground/background
  generation roles to Gemini. This is the user-confirmed cloud-first MVP posture.
- The local Gemma GGUF, multimodal projector, and llama-server are installed, but
  zero-shot/random-turn compatibility and useful latency are not acceptance-tested.
- The stack was stopped during review. `memory/memory_index.db` contained zero
  nodes; `retrieval.db` contained 340 web chunks and zero `file://` document chunks.
- Audio capture completed through `parec`, but the diagnostic sample was effectively
  silent. Web search fell through DDG bot blocks; lower-level search/fetch worked,
  while the full diagnostic pipeline returned no cited result.
- The classic UI still has `localDraft` fabricated answers and localStorage reminder
  drafts despite real bridge/scheduler backends.
- The paper's frozen context snapshot, parallel facet result contract, merge
  arbitration, concrete privacy policy, and confirmed effectors are not live code.

**Live edges.**
- `--realized--> D-28` **load-bearing**: the reproducible cloud-first baseline now
  starts, backfills memory, exercises one real turn, and shuts down cleanly.
- `--realized--> D-29` **load-bearing**: observers are now model-independent and
  vision uses bounded recent-frame novelty for temporal boundaries.
- `--realized--> D-30` **load-bearing**: each run now shares one frozen,
  versioned rolling-context view using the existing dynamic budget.
- `--dependency--> D-37` **significant**: `cache_prompt:true` reuses a live
  llama.cpp prefix; durable KV slot save/restore and cache provenance are absent.
- `--realized--> D-31` **load-bearing**: retrieval now has labeled quality metrics,
  a live corpus, and explicit failure-path reporting.
- `--realized--> D-32` **load-bearing**: unplugged-user proactive and journal
  behavior now has deterministic retry and live end-to-end proof.
- `--dependency--> D-35` **significant**: classic UI transport works; false
  fallbacks, draft reminders, missing session controls, and incomplete capability
  truth remain.
- `--realized--> D-34` **load-bearing**: model proposals, one-use confirmation,
  allowlisted execution and audit now work end to end.
- `--constraint--> D-36` **load-bearing**: cloud-first is allowed for MVP, but every
  core turn must remain random-turn compatible with local llama.cpp.
- `--realized--> D-33` **load-bearing**: cloud/web/media/notification boundaries now
  have explicit policy, redaction, hashed audit, and confirmation defaults.
- `--dependency--> D-38` **load-bearing**: offline green tests cannot prove a running
  end-to-end MVP; the terminal acceptance harness must exercise the live system.

**Assumptions baked in.** The cloud-first posture is temporary and explicit, not a
relaxation of local compatibility. Existing offline tests remain regression gates,
not proof of autonomous behavior. No feature is "done" from wiring alone.

## D-28 — Reproducible cloud-first runtime smoke (2026-06-18)
**Implemented and live-verified.** `make mvp-smoke` now starts the existing bridge
runtime, verifies Gemini health, writer ownership, cognitive tick, autonomous journal,
and startup memory backfill, submits one real typed turn, verifies the user/assistant
messages were persisted and indexed, then stops only the service it started.

The live pass used `gemini-3.1-flash-lite-preview`; memory grew from 100 to 102 nodes.
The first pass exposed a concrete lifecycle bug: bridge/app children inherited
`desktopctl.sh`'s lifecycle-lock descriptor, preventing later stop commands. Both
child launch sites now close descriptor 9 before exec. The repeated smoke passed
startup, turn, indexing, and clean shutdown.

**Verification.** `make check`; `python3 services/lk/tests/test_launcher.py`;
`make mvp-smoke`; `git diff --check`.

**Live edges.**
- `--dependency--> D-29` **load-bearing**: sensors were changed and diagnosed
  against the reproducible running process.
- `--dependency--> D-31` **load-bearing**: retrieval stress used the populated index
  and healthy configured backend.
- `--dependency--> D-32` **load-bearing**: unattended behavior was verified against
  the stable startup/lifecycle baseline.
- `--dependency--> D-35` **significant**: UI truth consumes stable runtime and
  memory/autonomy health.
- `--dependency--> D-36` **load-bearing**: the same smoke shape is rerun against
  llama.cpp without provider-specific orchestration.
- `--dependency--> D-33` **significant**: policy enforcement used the concrete
  cloud-first runtime boundary.
- `--dependency--> D-38` **load-bearing**: terminal acceptance reuses this startup,
  typed-turn, persistence, and shutdown lane.

**Assumptions baked in.** N-34 validates the service runtime, not popup behavior;
classic UI behavior is recorded in D-35. A pre-existing healthy bridge is preserved rather
than stopped by the smoke command.

## D-29 — Model-independent MVP sensor boundary (2026-06-18)
**Implemented and verified.** Vision and audio observers now start from user/config
intent without consulting the response model's image/audio input capabilities.
Capture, OCR, RMS silence gating, transcription, transcript deduplication, context
writes, and proactive triggering remain model-independent. Media attachments stay
capability-gated when a turn is built.

Vision now compares each frame with a fixed six-frame recent-state window. Returning
to a recent state is low novelty; a foreground title change clears the window and
marks a temporal boundary. Work and memory are bounded, with no model call. Existing
vision/audio gates still decide whether a slice reaches optional model extraction.

**Verification.** Sensor stress covers lifecycle independence, retained attachment
gates, first/repeated/revisited frames, bounded history, spool delivery, proactive
timing, and shutdown. `make check` and `make mvp-smoke` pass; the live smoke grew
memory from 102 to 104 nodes and stopped cleanly.

`[revised: unattended acceptance]` The exact-title self-window filter now excludes
the LAWRENCE popup and terminal without incorrectly excluding a VS Code workspace
whose title begins with `LAWRENCE (Workspace)`. A real two-minute no-turn run then
advanced context from 639→1161 characters, indexed memory from 123→125 nodes, and
appended two atomic sensor-log entries with no queued-job growth.

`[revised: audio replay gap]` Active voice mode now accumulates meaningful
four-second transcript windows and submits one combined utterance only after a
silent boundary. Passive context still receives each meaningful chunk; the stress
replay proves two speech windows produce one turn, not two.

**Live edges.**
- `--dependency--> D-30` **load-bearing**: frozen context consumes existing
  distilled context records without a new sensor-object hierarchy.
- `--dependency--> N-39` **load-bearing**: autonomous work now receives environmental
  triggers independent of the selected LLM.
- `--dependency--> D-38` **load-bearing**: terminal acceptance proves real target-
  host capture, including non-silent audio.

**Assumptions baked in.** Fixed heuristic/statistical gates are sufficient for MVP.
Learned edge models and richer region histories wait for measured misses. Audio still
uses bounded recording windows; D-38 includes deterministic utterance replay.

## D-30 — Frozen versioned context boundary (2026-06-18)
**Implemented and verified.** `freeze_context()` captures one immutable
`ContextSnapshot(version, text)` for a user turn or proactive run. It retries when
context changes during the read, so all passes share the same rolling-memory text.
Turn logs record `context_version` for audit.

This reuses `ContextStore.tail_for_model()` and its dynamic L1/L2/L3 budget, sticky
summaries, and raw-detail trimming. Retrieved evidence was already gathered once
into a fixed list per run; no second budget system or facet framework was added.

**Verification.** A focused test forces a version change during the first read and
proves the retry returns the stable second version. `make check` and
`make mvp-smoke` pass; live memory grew from 104 to 106 nodes.

**Live edges.**
- `--dependency--> N-39` **load-bearing**: autonomous reasoning now evaluates one
  stable context version.
- `--dependency--> D-34` **load-bearing**: action proposals cite the logged
  context version that justified them.
- `--dependency--> D-37` **significant**: stable context identity keys local KV
  checkpoints.
- `--dependency--> D-38` **load-bearing**: acceptance verifies context-version
  provenance across typed and autonomous runs.

**Assumptions baked in.** The existing character budget remains the MVP token-budget
proxy. Complete prompts are not persisted; durable source records remain canonical.

## D-31 — Retrieval quality baseline and live-corpus stress (2026-06-18)
**Implemented and verified.** A small labeled production-engine corpus now measures
recall@5, MRR, citation continuity, source diversity, duplicate rate, and category
isolation. It passes recall@5 1.00 and MRR 1.00. The current PLAN and original
LAWRENCE paper were ingested into the real document index (164 new local chunks).

Two measured defects were fixed:
- `note://` rows could enter the web arm because every non-`file://` URL was treated
  as web. Web now accepts HTTP(S) only; docs accept `file://` only.
- SQLite FTS interpreted natural-language multi-facet queries as all-terms AND,
  dropping relevant category-specific rows. Queries now use a bounded token union
  and BM25 ranking, matching the existing LIKE fallback's recall behavior.

`make retrieval-smoke` exercises live Gemini planning over own memory, the current
PLAN, the original paper, cached web, and a cold-web provider call. The repeated
live result was recall@8 1.00, MRR 0.88, three source categories, and 5.53s maximum
lane time. Cold web correctly reported DDG bot blocks and missing Brave/SearXNG
configuration instead of silently returning no evidence.

**Perplexity baseline.** LAWRENCE now covers the observable first-party Search API
contract relevant to this MVP: ranked structured results, multi-query retrieval,
source/category filtering, extracted text, and consistent citations. Iterative
sufficiency remains LAWRENCE orchestration rather than a claim about proprietary
Perplexity internals. Reference:
`https://docs.perplexity.ai/docs/search/quickstart`.

**Verification.** `make check`; `make mvp-smoke`; `make retrieval-smoke`;
`git diff --check`.

**Live edges.**
- `--dependency--> N-39` **load-bearing**: proactive findings can now use measured,
  category-clean retrieval with explicit degraded states.
- `--dependency--> D-38` **load-bearing**: terminal acceptance reuses the labeled and
  live retrieval lanes.

**Assumptions baked in.** Cached/local retrieval is MVP-ready. Fresh public web
search remains degraded until a reliable provider is configured; autonomy must
surface that state and may continue on own-memory/docs/cached evidence.

## D-32 — Unattended proactive and journal cycle (2026-06-18)
**Implemented and live-verified.** Proactive and journal cooldowns now commit only
after meaningful work succeeds. A busy/dropped/failed attempt remains immediately
retryable while each path remains single-flight. `run_proactive()` returns a simple
completion boolean; no generalized autonomy state machine or queue was added.

`make autonomy-smoke` drives a high-significance perception event through the real
cognitive tick with no user turn. Gemini surfaces a cited finding, the context store
persists it, and the memory index records it. The same temporary unattended cycle
then writes and indexes a first-person journal entry from the accumulated context.

**Verification.** Deterministic tests prove failed proactive and journal attempts do
not consume cooldown, successful attempts do, immediate retries work, and duplicates/
stale findings remain suppressed. Live result:
`AUTONOMY SMOKE: PASS (...; journal=Troubleshooting my broken search tools)`.
`make check` and `make mvp-smoke` pass; live memory grew 108→110.

**Live edges.**
- `--dependency--> D-35` **significant**: the classic UI exposes real finding,
  journal and degraded-provider state.
- `--dependency--> D-38` **load-bearing**: terminal acceptance reuses unattended
  proactive/journal replay plus a longer target-host soak.

**Assumptions baked in.** One bounded in-flight job is sufficient for MVP; no
autonomous queue is needed until measured event loss demands one. Quality controls
surface frequency rather than a quota. Quiet hours remain N-43 policy.

## D-33 — Privacy and trust-boundary enforcement (2026-06-18)
**Implemented and live-verified.** One `PolicyState` governs remote model text, raw
cloud media, web queries, notifications and external actions. Cloud text is
redacted; ambient raw media is removed; explicit user attachments may pass; web
queries are redacted, path-free and bounded; notifications honor disable/quiet
hours; unknown operations deny; external actions require explicit confirmation.

Every decision appends only timestamp, operation, allow/deny, reason and SHA-256 to
`.runtime/policy.jsonl`. No payload, media, query, prompt or secret field is stored.
Bridge health exposes the active policy summary.

**Verification.** Pure tests cover secret/home-path redaction, cloud-media admission,
web denial, external-action confirmation and unknown-operation denial. Full live
Gemini MVP, retrieval and autonomy smokes pass under policy. The live audit contained
27 records across cloud text/media and web, with no raw payload fields.

**Live edges.**
- `--dependency--> D-34` **load-bearing**: agency execution has one confirmation
  and audit authority.
- `--dependency--> D-35` **significant**: UI displays policy and confirmation
  state honestly.
- `--dependency--> D-38` **load-bearing**: terminal acceptance tests denial,
  confirmation and audit evidence.

**Assumptions baked in.** Redaction is intentionally narrow: configured secret
values, common API-key forms and home-directory prefixes. Rich DLP waits for measured
leaks. Policy is process-wide; per-trigger overrides are unnecessary for MVP.

## D-34 — Confirmed allowlisted agency (2026-06-18)
**Implemented and live-verified.** The response schema can propose three reversible
operations: `task.add`, `reminder.add`, and `artifact.write`. A proposal has no side
effect. `Agency` validates the allowlist, records context version/risk, issues a
one-use confirmation token, and executes only after explicit confirmation through
D-33 policy. Arbitrary shell, URL launch and unregistered operations are absent.

The bridge exposes `GET/POST /actions`; model proposals return through
`controls.actionProposals`. Execution appends a durable local action event and a
hash-only policy decision. Artifact names are basename-confined and Markdown-only;
writes are atomic and capped.

**Verification.** Unit tests cover wrong token denial, no pre-confirmation mutation,
one-use confirmation, task mutation, rejected reminder and path-safe artifact write.
`make agency-smoke` proves Gemini proposal→pending→confirmation→artifact and rejects
token reuse.

**Live edges.**
- `--dependency--> D-35` **load-bearing**: classic UI renders proposals and sends
  confirm/reject decisions.
- `--dependency--> D-38` **load-bearing**: terminal acceptance requires a visible
  confirmed state change and its audit trail.

**Assumptions baked in.** All MVP effectors require confirmation despite being
reversible. Voice confirmation and arbitrary commands remain intentionally absent.
Pending proposals are process-local; the append-only audit remains durable.

## D-35 — Truthful classic MVP surface (2026-06-18)
**Implemented and verified `[revised: N-40 complete]`.** The classic UI no longer
fabricates a response when the bridge is unavailable. Reminders now list, add and
delete through the durable `/reminders` backend; chat sessions list, switch and
create through `/chats`; policy state is visible in telemetry; and model-proposed
actions render their operation, risk and context version before a typed
confirm/reject decision is sent to `/actions`.

Confirmation tokens are not persisted in browser session state. A restored pending
proposal therefore renders as expired instead of presenting a nonfunctional Confirm
button. Existing streaming, source cards, cancellation and the 80-message render cap
remain intact.

**Verification.** `npm run test:features` exercises 95 turns and passes reminder
durability, chat switching/creation, policy visibility and action confirmation.
`services/lk/tests/stress_ui.py`, JavaScript syntax checks, `cargo check`, and
`git diff --check` pass.

**Live edges.**
- `--dependency--> D-38` **load-bearing**: terminal acceptance exercises this
  truthful UI against the live runtime, not only the deterministic DOM harness.

**Assumptions baked in.** The existing classic layout is sufficient for MVP; no
redesign, archive workflow or UI-specific reminder cache is required. The bridge is
authoritative for state.

## D-36 — Random-turn local llama.cpp compatibility (2026-06-19)
**Implemented and live-verified.** The bundled Gemma 4 GGUF now runs the same model
gateway contracts as cloud mode with no orchestration branch outside the model
boundary. Local server startup explicitly disables reasoning when `LK_THINKING` is
off; this prevents hidden thought generation from consuming the structured response
budget.

`make local-smoke` validates analysis, retrieval planning, sensor extraction,
proactive reasoning, journal drafting, live cooperative cancellation, and a
deterministic random turn boundary. The random turn preserves a typed
`artifact.write` proposal. Correctness passes; measured CPU latency is p50 31.79s,
p95 98.64s, max 131.96s.

**Live edges.**
- `--dependency--> D-37` **load-bearing**: the exact bundled server/model contract
  defines compatible KV persistence.
- `--dependency--> D-38` **load-bearing**: terminal acceptance consumes this local
  replacement proof; latency optimization remains post-MVP work.

**Assumptions baked in.** Correctness precedes useful latency. The cloud-first MVP
remains the default while local CPU optimization is deferred and measured separately.

## D-37 — Profile-keyed local KV checkpoint lifecycle (2026-06-19)
**Implemented and live-verified.** Managed llama.cpp startup enables a private
`.runtime/kv/` slot-save directory, restores the newest compatible profile-keyed
slot after health, and saves slot 0 before shutdown. The filename identity includes
the model, projector, llama-server binary, context size, KV type, flash-attention
mode and Jinja mode. Missing or rejected checkpoints cold-start; an incompatible
file is deleted rather than trusted.

The bundled llama.cpp rejected all slot actions whenever a multimodal projector was
loaded, including text-only slots. The local runtime patch narrows that restriction:
slots containing media chunks remain rejected, while text-only slot state can save
and restore. `make kv-smoke` restored 17 prior tokens across a full server restart;
the continued 33-token prompt evaluated only its 16-token suffix. The checkpoint is
566,080 bytes.

**Live edges.**
- `--dependency--> D-38` **significant**: terminal acceptance retains the
  warm-restart report and verify cold fallback remains safe.

**Assumptions baked in.** KV is derivative acceleration, never canonical memory.
Only text prefix state is persisted; raw media KV remains unsupported and is
explicitly denied.

## D-38 — Running end-to-end MVP acceptance (2026-06-19)
**Accepted `[revised: N-44 complete]`.** The SOUL-level loop now runs as one system:
independent vision perception writes objective context, extraction/indexing makes it
durable, the cognitive tick can retrieve and surface findings without a user turn,
the rolling first-person journal writes on its context/time trigger, typed turns use
cited memory/document/web evidence, and allowlisted effects remain proposal-only
until explicit confirmation.

**Terminal evidence.**
- `make mvp-smoke`: cloud-first cold start, populated memory, cited grounded turn,
  durable chat/index write, memory 146→149, clean shutdown.
- `make retrieval-smoke`: recall@8 1.00, MRR 0.75, three source categories, max
  4.96s; cold web reports explicit degradation when no configured provider works.
- `make autonomy-smoke` and `make agency-smoke`: no-turn finding+journal indexing,
  confirmed artifact write, and no pre-confirmation mutation/token reuse.
- Real unattended hour: 345 health checks, zero queued/running job buildup,
  context 1161→2502 characters, memory 129→135 nodes, five new atomic context-log
  entries, and a new 1,368-byte autonomous journal.
- Sensor replay: six-frame visual novelty/window boundaries, exact self-window
  filtering, model-independent lifecycle, and two audio speech windows accumulated
  into one utterance after silence.
- `make local-smoke`: seven local contracts including cancellation, random-turn
  context and agency; p50 31.79s, p95 98.64s, max 131.96s.
- `make kv-smoke`: 17-token warm restart, 16-token suffix evaluation, 566,080-byte
  profile-keyed checkpoint.
- `make check`, desktop feature/runtime contracts, Rust `cargo check`, and
  `git diff --check` pass. Ports 8190/8765/8766 and managed processes are clean.

**Settled boundary.** This node is the MVP sink and has no outgoing execution edge.
Post-MVP work may improve latency, fresh-web provider availability, microphone
hardware validation, UI polish and Windows-native packaging, but those do not
replace or invalidate the accepted orchestration/memory/privacy/agency loop.

**Assumptions baked in.** Cloud Gemini remains the practical default. Fresh cold-web
search is capability-reported and degrades explicitly without Brave/SearXNG access.
The microphone pipeline is replay-tested; this host's live input remained silent, so
non-silent hardware validation is an operational follow-up, not fabricated evidence.

---

## Live-stub index (every D-node's outflow, for audit) `[revised: F2 — added D-04→N-20, D-09→N-16]`
D-01→N-02,N-18 · D-02→N-06 · D-03→N-07 · D-04→N-07,N-11,N-20 · D-05→N-02,N-08 ·
D-06→N-07,N-21 · D-07→N-28 · D-08→N-08,N-02,N-11 · D-09→N-27,N-05,N-22,N-16 ·
D-10→N-17,N-15 · D-11→N-10 · D-12→N-14 · D-13→N-07,N-02 · **D-14→N-02 (conflict)** ·
D-15→N-28,N-18..N-23 · D-16→N-04 · D-17→N-01 (✓ built=D-20),N-21 · D-18→N-06 ·
D-19→N-03,N-05,N-12,N-13 · **D-20→N-02 (vector arm),N-06,N-07,N-08** ·
**D-21→N-28 (✓ closed),N-32 (new: local turn latency),N-09 (✓ closed=D-23)/N-11** ·
**D-22→N-33 (sensor decoupling: step 1 done),N-02 (✓ closed=D-24)/N-06 (core=D-25)/N-07** ·
**D-23→N-10 (Track A),N-11 (palette),N-12/N-13/N-14/N-15 (folded UI nodes)** ·
**D-24→N-06 (core=D-25),N-07,N-05 (✓ realized=D-26),N-03/N-04 (folded=D-26),N-08/N-10/N-11 (G/P signal feeds)** ·
**D-25→N-06 (vision-demote/transcript half remains),N-05 (✓ realized=D-26),N-07** ·
**D-26→N-05 (✓ realized),N-03/N-04 (folded as categories),N-06 (recall now a cited category),N-07 (findings ride notes+doc+web),N-32 (latency lever),N-12/N-16 (consume the engine later)** ·
**D-27→D-28,D-29,D-30,D-31,D-32,D-33,D-34,D-35,D-36,D-37,D-38** ·
**D-28→D-29,D-31,D-32,D-33,D-35,D-36,D-38 (live MVP baseline)** ·
**D-29→D-30,D-32,D-38 (model-independent sensor boundary)** ·
**D-30→D-37,D-32,D-34,D-38 (frozen context boundary)** ·
**D-31→D-32,D-38 (measured retrieval boundary)** ·
**D-32→D-35,D-38 (unattended autonomy boundary)** ·
**D-33→D-34,D-35,D-38 (privacy and confirmation boundary)** ·
**D-34→D-35,D-38 (confirmed agency boundary)** ·
**D-35→D-38 (truthful human interaction boundary)** ·
**D-36→D-37,D-38 (local replacement boundary)** ·
**D-37→D-38 (warm-restart boundary)** · **D-38 terminal MVP sink**.

*D-38 is intentionally the only zero-outflow D-node: it is the settled MVP
acceptance sink. Other historical product backlog nodes remain outside this MVP
execution partition.*
