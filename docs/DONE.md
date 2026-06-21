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
>
> **Deployment stress overlay (2026-06-19):** historical completion is preserved,
> but D-28…D-42 are not treated as deployment-current until PLAN N-59…N-62 pass.
> Their existing smoke evidence proves a working path; the new gate adds sustained
> load, repeated lifecycle transitions, live sensor endurance, and Windows-host
> installation stress. This is a revalidation edge, not a rollback of implemented work.

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
> **NOT re-run this session** (needs running bridge + network + Gemini key) ·
> ⏳ implemented, but deployment stress revalidation is open in N-59…N-62 · ➖ superseded
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
| D-28 | cloud-first smoke | `make mvp-smoke`: start→cited turn→index→stop | ⏳ N-59/N-61 |
| D-29 | model-indep sensors | observers start from config, not model modality | ⏳ N-60 |
| D-30 | frozen context | immutable versioned `ContextSnapshot` per run | ⏳ N-59 |
| D-31 | retrieval quality | labeled corpus recall@5/MRR + live corpus | ⏳ N-59 |
| D-32 | unattended autonomy | proactive/journal fire; cooldown-on-success | ⏳ N-59/N-60 |
| D-33 | privacy boundary | redact/gate/audit (hash-only); confirm effectors | ⏳ N-59 |
| D-34 | confirmed agency | allowlist + one-use token; atomic artifact write | ⏳ N-59 |
| D-35 | truthful classic UI | no fabricated answers; real reminders/chats/actions | ⏳ N-61 |
| D-36 | local llama.cpp compat | random-turn parity; p50 31.8s/p95 98.6s CPU | ⏳ N-59 |
| D-37 | local KV checkpoint | profile-keyed text-only slot save/restore | ⏳ N-59/N-61 |
| D-38 | running e2e MVP accept | SOUL loop runs as one system (aggregated terminal evidence) | ⏳ N-62 |
| D-39 | voice/runtime repair | compile-only rebuild + segmented voice + 10s pending gate | 🔴 REGRESSED → N-63 (rebuild still restart-popups; VAD -45 starves capture; inline whisper stalls; voice-render half D-40/41/42 OK) |
| D-40 | bottom telemetry | truthful subsystem state + token/reset + trajectory | ⏳ N-61 |
| D-41 | chat viewport/lifecycle | stable scroll + clear/save/archive/restore | ⏳ N-61 |
| D-42 | current-first interpretation | current evidence governs; history supplies trajectory | ⏳ N-59/N-62 |

**Net (2026-06-19).** D-01…D-42 remain the implementation record. Component gates
and prior live smokes show the paths exist, but deployment-sensitive nodes are ⏳
until N-59 core load, N-60 live sensor endurance, N-61 desktop/Windows-host stress,
and N-62 convergence acceptance pass against the same commit. Runtime posture is
**cloud-first (Gemini)**; local llama.cpp compatibility remains mandatory. No local
embed GGUF is installed, so the vector arm degrades to lexical+graph locally.
**Correction (2026-06-19):** D-39 (voice/runtime) is **🔴 regressed** — its rebuild +
audio-capture claims do not match the running code (rebuild still restart-popups; VAD
default -45 starves WSLg capture; inline whisper stalls). Re-opened as **N-63**, which
now gates N-60. D-40/D-41/D-42 (telemetry/chat/grounding) are unaffected.

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
- `[D-29] --{partial-completion}--> [N-45]`
  Weight: load-bearing
  Meaning: D-29 proves model-independent observer lifecycle and bounded event delivery;
  N-45 generalizes this into independent instances of one modality-agnostic,
  asynchronous, continuously pipelined cascade from acquisition through semantic
  refinement and final emission.
  Break condition: Coupling sensor acquisition to model response, blocking acquisition
  on refinement, or erasing modality-native segment/time identity violates N-45.

**Assumptions baked in.** Fixed heuristic/statistical gates are sufficient for MVP.
Learned edge models and richer region histories wait for measured misses. Audio still
uses bounded recording windows; D-38 includes deterministic utterance replay.

**N-45 clarification addendum (2026-06-20).** D-29 does **not** implement the planned
cascade beyond its minimal observer/spool substrate. The future abstraction is not a
single serial pipeline: every modality runs an independent, parallel instance of the
same modality-agnostic realtime cascade; pixels remain the primary screen signal with
asynchronous system/tool metadata layered onto them; stages 1–5 target the hot realtime
path; longer same-modality context, selective specialists and cross-modal/contextual
arbitration progressively refine stable segment/time identities before emission.

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

## D-39 — Live voice/runtime repair (2026-06-19)
> **🔴 REGRESSED 2026-06-19 (post-Codex audio fix) → re-opened as PLAN §M.5 / N-63.**
> A code read contradicts the "live-verified" claims below: (1) `cmd_rebuild` still ends
> with `_desktopctl("restart-popup")` — NOT compile-only; (2) `obs/audio.py` defaults the
> VAD gate to `-45 dB`, which the file's own notes say rejects real WSLg-mic speech (`-55`
> needed) → capture rarely opens an utterance, so voice/transcription/proactive read as
> "none working"; (3) transcription runs inline in `_capture_loop` and stalls capture /
> overflows the ~2 s PCM pipe; (4) gain-normalization dropped to dead code; (5) a short
> read discards the open utterance; (6) the green `stress_sensors §F` mocks the threshold,
> decode, AND gate, hiding all of it. **The chat-render/telemetry/grounding halves
> (→ D-40/D-41/D-42) are unaffected and remain done.** Remediation contract = N-63.
> Legacy "implemented/verified" text is kept below as the (unmet) intended contract.

**Implemented and live-verified.** `lk rebuild` now only compiles; it starts, stops,
or restarts nothing. Runtime config enables passive audio at boot. The live bridge
reports model, vision, audio, tick, and journal healthy; `parec` is running against
WSLg PulseAudio. Voice-listen is user-controlled and uses one VAD-segmented utterance
path with partial/final UI updates and a silence-timeout proceed/dismiss gate. The
decision window is configured and clamped to at least 10 seconds.

**Verification.** Two real release rebuilds preserved popup and bridge PIDs.
An explicit restart then loaded the new binary/config. Sensor/autonomy tests and
the desktop interaction harness pass.

**Assumptions baked in.** Live capture is operational, but transcription quality
still depends on actual microphone signal level and speech during use.

**Live edges.**
- `[D-39] --{constraint}--> [N-45]`
  Weight: significant
  Meaning: The tactical faster-whisper contract must remain replaceable by streaming ASR.
  Break condition: An incompatible ASR interface requires bridge and UI voice rewrites.
- `[D-39] --{dependency}--> [N-55]`
  Weight: incidental
  Meaning: Reliable global summon improves access to the repaired runtime.
  Break condition: Removing the popup-control socket changes N-55's attachment point.

## D-40 — Bottom telemetry status and trajectory (2026-06-19)
**Implemented.** Each bottom metric now owns its success/warning/failure color.
The strip adds an approximate session token counter with inline reset and a compact
`user|proactive › stage · ctx usage` trajectory.

**Assumptions baked in.** Token use is a transparent UI estimate from submitted and
generated text, not provider-billed usage.

**Live edges.**
- `[D-40] --{partial-completion}--> [N-49]`
  Weight: significant
  Meaning: Truthful compact telemetry is implemented; broader UI hierarchy remains.
  Break condition: Replacing the bottom strip must retain equivalent health truth.

## D-41 — Stable chat viewport and chat lifecycle (2026-06-19)
**Implemented.** Streaming follows the feed only when the user is already near its
bottom; invoking a query no longer overrides a manually positioned scroll. History
now exposes Clear/new, Save, Archive, and Restore using the existing durable chat
store. Archived chats remain restorable and exports are MDX.

**Verification.** The DOM harness proves a manually positioned feed does not move
when a query starts, chat save/archive/restore/new routes work, and new chat clears
the visible feed. Chat CRUD and UI contract suites pass.

**Assumptions baked in.** Archive is the safe default deletion path; hard deletion
remains backend/CLI-only. “Save” exports MDX.

**Live edges.**
- `[D-41] --{partial-completion}--> [N-49]`
  Weight: significant
  Meaning: Scroll stability and chat lifecycle are complete pieces of the larger UI track.
  Break condition: A UI redesign must preserve feed position and durable chat controls.

## D-42 — Current-first model interpretation (2026-06-19)
**Implemented.** Context storage, headers, ordering, memory, logs, journal, and
retrieved evidence are unchanged. Model instructions now treat the current request,
newest active-chat turns, and recent perception as authoritative; older material
clarifies long-run trajectory and cannot override newer evidence.

**Verification.** The UI contract suite checks the interpretation rule is present,
and the unchanged `_ChatContext.tail_for_model()` composition preserves context shape.

**Assumptions baked in.** This is an interpretation policy, not a retrieval filter.
Older context remains available when relevant or explicitly requested.

**Live edges.**
- `[D-42] --{constraint}--> [N-48]`
  Weight: load-bearing
  Meaning: Future grounding must preserve current-over-historical precedence.
  Break condition: Letting stale memory override current state regresses D-42.

---

## D-43 — Durable-memory formation: P_dist promotion + S_link auto-linking (2026-06-19) — N-71, §P
**Soul gap closed.** The soul (paper Eq.3/Eq.4, Alg.2) requires finished turns to be
*scored* for durable promotion and, when promoted, written as a **linked** Zettelkasten
note. The live turn only wrote the rolling ContextStore + the retrieval index and **never**
promoted a turn to a durable note; links were manual `[[id]]` only; the note taxonomy had
collapsed to `turn`/`finding`. §P.1 graded this **ABSENT (P_dist, S_link)** + **DEGENERATE
(taxonomy)**.

**Implemented.** New `ctx/promote.py` (stdlib, **model-free**, never raises):
- `pdist()` — soul Eq.3 priority `αn·N + αs·S + αu·U + αt·T + αa·A` over signals the turn
  already produced (novelty vs recent notes, the model's confidence, user emphasis /
  `remember`, tag-thread overlap, tasks/actions). Promote on `≥τ` **OR** explicit pin **OR**
  confirmed action (the soul's exact rule).
- `slink()` — soul Eq.4 `λ1·cos + λ2·Jaccard + λ3·R_time + λ4·R_thread`; the cos term is a
  lexical cosine (model-free stand-in, **honestly labelled** — no embedding claimed).
- `promote_turn()` — DistillAndLink (Alg.2): bounded candidate read, score, keep links
  `>τ_link`, write `context_log` / `task_note` / `knowledge_note` with auto-links.
- Wired best-effort into `run_turn` **after** the answer is surfaced (`memory.notes`
  property added); `LK_DISTILL_OFF` / `LK_DISTILL_TAU` / `LK_DISTILL_LINK_TAU` knobs.

**Verification.** `tests/test_promote.py` (added to `make test`): small-talk → not promoted;
`remember` → `knowledge_note`; tasks → `task_note`; a related follow-up **auto-links** back
to the earlier note via S_link; P_dist/S_link monotonicity. Import-check (26 modules) + the
touched-module regression set (notes, memory-index, retrieval-engine, context-snapshot,
refine, stress-memory) all green.

**Scope / honesty.** Conservative by default (won't make the vault an event dump — the
soul's explicit warning). Findings-promotion (proactive path) and embedding-based cos are
deliberate follow-ups, not claimed here. This does **not** touch the turn's serial/parallel
structure — N-70 (parallel-facet runtime) is **deferred to the next MVP iteration** per
user (2026-06-19).

**Live edges.**
- `[D-43] --{feeds}--> [N-02]`
  Weight: significant
  Meaning: Auto-links populate retrieval's (conformant but edge-starved) graph arm G.
  Break condition: If promotion stops writing links, the graph arm degrades to manual-only.
- `[D-43] --{realizes}--> [soul §VIII/§X]`
  Weight: load-bearing
  Meaning: Durable memory + linking is the soul's "strongest architectural commitment."
  Break condition: Disabling promotion returns durable memory to manual-only.

---

## D-44 — Proactive loop verified end-to-end + instrumented (2026-06-19) — N-07, §P
**Verified (the actual question).** §P graded the proactive loop PARTIAL because "it may
never fire" (the 2026-06-17 worry). Tracing the live wiring resolves it: the single
throttled convergence `kernel.invoke.run_proactive` is attached to **four** drivers —
`VisionObserver`, `AudioObserver` (unless audio-query mode), the `CognitiveTick.act_fn`
(`lambda events: on_proactive("tick", …)`, started), and the `SpoolReader` — all via the
one `_make_proactive_trigger` callback (`cli.py`). It **is** wired end-to-end
(driver → run_proactive → `present_fn` → UI card + OS notify); the silence is **by design**
(600 s `proactive_interval` + droppable `PRI_PROACTIVE` + significance tier ≥ 2), not a break.

**Instrumented (the real gap).** You could not previously tell *at runtime* whether the
autonomous loop was firing or merely throttled/dropped. Added thread-safe process-global
counters in `run_proactive` (`calls / warmed / surfaced / stale / dup / skipped / error`)
+ a public `proactive_stats()` accessor (covers **all** drivers, CLI and bridge, since they
share the one convergence) + a `/status` line (`_proactive_fired_summary`).

**Verification.** `tests/test_proactive_dedup.py` extended: its 7 scripted `run_proactive`
calls assert the counters (≥3 surfaced, ≥2 dup, ≥1 stale, ≥1 busy-skip). Import-check (26
modules) + regressions (offline, edge, autonomy, tick, stress-sensors, stress-ui) all green.

**Honesty.** This does NOT change firing behavior or the 600 s throttle (kept — the soul asks
for *low-frequency* contextual suggestions); it makes firing observable so the throttle can
later be tuned with evidence. The serial turn (N-70) remains deferred per user.

**Live edges.**
- `[D-44] --{observability}--> [N-62]`
  Weight: significant
  Meaning: Deployment acceptance can now verify the autonomous loop actually fired.
  Break condition: If counters stop tracking outcomes, "is it firing?" is unanswerable again.
- `[D-44] --{realizes}--> [soul §VII]`
  Weight: load-bearing
  Meaning: An autonomous loop with no user/event is core to watcher-assistant (not chatbot).
  Break condition: A dead/never-fired proactive loop regresses LAWRENCE to a reactive chatbot.

---

## D-45 — Serving levers measured; native>WSL confirmed; N-65 still open (2026-06-20) — N-65
**⚠ N-65 TARGET NOT YET REPRODUCED — and I over-concluded TWICE; corrected here.** First wrote
this as a clean "done"; then benchmarked and over-corrected again. The honest, humbler record:

**Host:** **Snapdragon X Elite (Oryon, 12 cores), ARM64**, Windows-on-ARM + WSL2. Model =
**Gemma-3n-E4B**: `model params = 7.52 B` *total* but **~4B EFFECTIVE** (Per-Layer Embeddings /
MatFormer — user corrected me; the decode hot path is ~4B), so **≥15 tok/s IS plausible** and my
"too big for CPU" conclusion was wrong. The plan's x86 levers (AVX/AMX) are N/A on ARM.

**Verified working:**
- **Cross-turn KV prefix reuse — REAL.** `--cache-reuse` (env `LK_CACHE_REUSE`=256) +
  `cache_prompt:true`: turn 2 with a shared ~1.2K prefix re-evaluated only `prompt_n=10`,
  reused `cache_n=1217`. Also `--keep` via `LK_KEEP`. FA + KV-q4_0 + slot save/restore present.
- **Native Windows ARM64 ≫ WSL.** Same model, llama-bench tg, peak: **WSL 7.4 → native ~10 tok/s
  (+~37%)**, and WSL's hard thread-cliff (10–12t → 2.4–2.7) is ABSENT natively. WSL virtualization
  was a real tax. (Native run = official prebuilt `llama-b9733-bin-win-cpu-arm64`, model on C:\.)

**Where I was wrong on threads (corrected):** I changed the default 9 → "all cores" → cap-8 from a
sweep, but the sweep ran **on BATTERY**, where Snapdragon throttling makes tok/s wildly noisy
(±4–5): native 7/8/9/10/11t = 7.67/9.42/8.06/6.10/6.57 — **8 and 9 statistically identical.** No
basis to override the user's deliberate **9**. **Reverted: `_default_threads()` = 9 (capped by
core count); `LK_THREADS` overrides.** Power state (AC vs battery) matters far more than ±1 thread.

**Still open (NOT disproven):** measured peak ~10 tok/s, but **on battery + a generic (non-Oryon)
prebuilt**. The two remaining CPU levers to reach ≥15: (1) **AC power** (battery throttles hard),
(2) a **from-source `-mcpu=native` Oryon build**. The from-source build is BLOCKED: clang is
present (C:\LLVM) but the **MSVC CRT (`libcmt.lib`) is missing** (no VS/Build Tools; not admin) —
needs a VS Build Tools install. **Decision path (user 2026-06-20):** build natively for Windows;
once ≥12 tok/s verified → add NPU/GPU + speculative decoding with **Gemma-3n-E2B as the draft**.
**Edges.** `[D-45] --{partially-addresses}--> [N-65]` (open) · `--{verified}--> [prefix-reuse;
native≫WSL]` · `--{corrected}--> [own thread overreach → back to 9]` · `--{feeds}--> [N-62]`.

---

## D-46 — Voice/runtime regression remediation + Windows-host capture workaround (2026-06-20) — N-63
**Implemented** ([obs/audio.py](../services/lk/obs/audio.py)):
- **VAD floor −45 → −55** (the silence bug): the streaming capture `vad_db` now defaults to
  `SILENCE_DB` (−55, the documented WSLg-working value) as the single source of truth;
  `LK_AUDIO_VAD_DB` still overrides. At −45 the per-frame gate rarely fired → silent loop.
- **Transcription moved OFF the capture thread**: a bounded decode-worker queue (`_decode_worker`,
  `_submit`) drains PCM jobs so `proc.stdout` is read continuously — no pipe overflow / dropped
  audio / blocked loop. Inline fallback when the worker isn't running keeps unit-driving intact.
- **Short read finalizes the open utterance** before the outer loop reopens (no tail loss).
- **Gain path resolved**: `_normalize_gain` is now a real opt-in (`LK_AUDIO_GAIN=1`) applied in
  `_transcribe_buf` on VAD-confirmed audio — no more comment-only "feature."
- **Windows-host capture workaround** (the WSLg RDP virtual-mic root cause): opt-in
  `LK_AUDIO_WIN_CAPTURE=1` drives a Windows-side `ffmpeg.exe` (`-f dshow`) over WSL interop,
  reading the REAL Windows mic as s16le PCM — bypassing PulseAudio/WSLg. Self-disables when no
  Windows ffmpeg is found (`LK_FFMPEG_WIN` / PATH / common C:\ paths) → falls back to the WSLg
  recorders. Device auto-detected or `LK_AUDIO_WIN_DEVICE`. Additive + degrades (I4).
- `cmd_rebuild` was **already** compile-only (root cause #1 fixed in a prior pass; stress §F confirms).
**Verification.** New **non-mocked** [test_voice_decode.py](../services/lk/tests/test_voice_decode.py)
exercises the REAL energy gate (silence < −55 < tone), real segmentation (one tone burst → one
utterance), the bounded gain, and the Windows-workaround graceful-degrade — replacing §F's fully
mocked confidence. `make test` green. **Pending live:** real-mic verification on the Windows host
(needs hardware + an ffmpeg.exe under C:\; a `tests/fixtures/utterance.wav` enables the real-decode smoke).
**Edges.** `[D-46] --{reopens/closes}--> [D-39]` load-bearing · `--{unblocks}--> [N-60]`
load-bearing (live voice endurance can now actually fire) · `--{constraint-honored}--> [N-45]`
significant (worker/observer seam stays swappable for SenseVoice×sherpa-onnx).

---

## D-47 — Comprehensive autonomous journal: per-entry research (2026-06-20) — N-46 (§L.2, now MVP)
**Implemented** ([kernel/journal.py](../services/lk/kernel/journal.py)). Replaced the throttled,
web-only, single-120-char-seed `_maybe_web_context` with `_gather_research` — comprehensive,
multi-seed, multi-source, cost-bounded per-entry retrieval (the soul's "journal MUST be comprehensive"):
- **Multi-seed** (`_research_seeds`): the explicit `> **Next:**` open thread + trailing body +
  live tail, deduped and capped (`LK_JOURNAL_MAX_QUERIES`, default 3) — not one truncated seed.
- **Own durable memory folded in by default** (local-first, cheap): `memory.recall` over every
  seed → `[MEMORY CONTEXT]`. The episodic spine can now reference past entries/notes on its threads.
- **Web/doc over the unified engine** (notes+doc+web, N-02/N-05): gated by `LK_JOURNAL_WEB` and
  min-gap-throttled (`LK_JOURNAL_WEB_MIN_GAP`) → `[RESEARCH CONTEXT]` — the external-cost arm stays
  opt-in for all-day cost discipline. Master kill switch `LK_JOURNAL_RESEARCH=0`.
**Verification.** [test_journal.py](../services/lk/tests/test_journal.py) §G: multi-seed extraction,
memory-default-on, web-gated, retrieve-called-once, throttle-blocks-rapid-re-entry, kill-switch.
`make test` green. **Deferred (post-MVP, the open trade):** a model call to *choose* the per-entry
queries (currently heuristic from open threads); routing through the N-47 Perplexity-grade engine.
**Edges.** `[D-47] --{extends}--> [D-05/WS-J]` load-bearing · `--{consumes}--> [D-24/D-26]`
(unified retrieval + MemoryIndex) significant · `--{realizes}--> [soul §L.2 / journal as episodic spine]`.

---

## D-48 — Chat branching/edit data model: a DAG over the append-only log (2026-06-20) — N-75 (P5-lite), Phase-1
**Implemented** ([ctx/chats.py](../services/lk/ctx/chats.py)). The structural foundation for Phase-1
chat branching/edit (user check-in 2026-06-20). `ChatStore` was append-only and **flat** (one linear
`messages.jsonl`); regeneration/edit/branch need alternatives. Added a **DAG layered over the immutable
event log** — the log is still never mutated (preserves I1 single-writer + durability):
- **Additive per-record fields** (`parent`, `kind ∈ {turn,regen,edit,branch-seed}`, `edit_of`, `diff`) +
  a **`head.json`** path cursor (`{parent_id→child_id}`, `""`=root slot). Walking `head` from the root =
  the active conversation. `append_message(parent=_AUTO)` auto-chains to the active leaf, so the existing
  two-call turn (`user`,`assistant`) keeps producing a clean linear backbone with **zero caller change**.
- **Ops (pure storage; model turn stays in the bridge):** `add_variant` (regenerate = sibling, becomes
  active), `edit_message` (append `edit` sibling carrying a real `difflib` unified diff; original never
  mutated), `set_head` (variant switch, no append), `fork_chat` (branch-off = new chat seeded with the
  active-path prefix), `tree`/`path_messages`/`parent_of`/`get_by_id` (traversal + minimap feed).
- **Back-compat:** legacy pre-DAG transcripts (no `parent`/`head.json`) resolve an **implicit seq-1
  linear backbone** → they walk + export unchanged; a new append onto a legacy chat chains to its leaf.
**Verification.** NEW [test_chats_dag.py](../services/lk/tests/test_chats_dag.py) (real, no mocks):
regen siblings + latest-active, head-switch (no append), edit→unified-diff (+ no mutation), fork prefix
copy, tree exposes variants/path/head, legacy linear walk + chain-on-append. Existing
[test_chats.py](../services/lk/tests/test_chats.py) (stable ids/order/export back-compat) still green.
**Live edges (open → N-75 remainder):** bridge endpoints `/regenerate`(+op descriptor)·`/edit`·`/head`·
`/branch`·`/tree`· no-response submit (`→ ui_bridge.py`); classic UI (head-path render + variant switcher
+ minimap + inline diff + regen ops §3a + no-response mode); launcher VCS viewer. Multi-parent in-edges
already supported = the reserved seam for **N-77** (Phase-2 synthesis).
**Edges.** `[D-48] --{extends}--> [D-05/WS-U ChatStore]` load-bearing · `--{enables}--> [N-75 bridge+UI]`
load-bearing · `--{reserves-seam}--> [N-77 synthesis]` significant · `--{feeds}--> [P6 NoteStore graph]` incidental.

---

## D-49 — Chat branching/edit/no-response: bridge + classic UI + launcher VCS (2026-06-20) — N-75 (§3a), Phase-1
**Implemented** on the D-48 DAG. The three branch kinds + §3a regen ops + edit/diff + no-response,
wired store↔bridge↔UI and **offline-gated** (live visual verify still needs a Tauri rebuild).
- **Bridge** ([ui_bridge.py](../apps/desktop/scripts/ui_bridge.py)) — ADD-only routes (I5):
  `POST /chats/{id}/regenerate` (op descriptor `{op,guidance?,preset?,n?,section?}` — informed ·
  stricter-grounding · preset[longer/shorter/formal/academic/casual/humanize/extend-N/compress-N] ·
  selective/explain = in-place section **edit+diff**), `…/messages/{mid}/edit`, `…/head` (variant
  switch), `…/branch` (kind-2 fork→active), `GET …/tree` (minimap), `…/note` (no-response → durable
  transcript + `ctx.append` to logs/journal + recall, **no model turn**). `turn()`'s transcript write
  refactored to `_persist_turn` (turn vs regen-variant vs in-place-edit). Presets default in-code,
  launcher-overridable via `{presetText}`.
- **Classic UI** ([variants/classic/app.js](../apps/desktop/web/variants/classic/app.js) + index.html +
  styles.css) — durable transcript ids threaded from the turn onto bubbles; per-message **Regenerate ▾**
  (op menu) · **Edit** · **Branch from here**; **‹k/n› variant switcher** (browses regenerations, persists
  via `/head`); **inline toggleable diff**; **Ctrl/Cmd+Enter = no-response note**; a **branch/variant
  minimap** (Map button → `/tree`, click a node to switch the active path). All transport via `lib/bridge.js`.
- **Launcher** ([launcher/chat_vcs.py](../services/lk/launcher/chat_vcs.py) + qt_tabs KnowledgeTab) —
  read-only **Chat history / VCS** panel: variant/edit history + stored diffs, ●on-path/○off-path. The
  launcher only *reads* memory (I1 intact); explicitly **not git / not chat-as-repo**.
**Verification.** [test_chat_ops_bridge.py](../services/lk/tests/test_chat_ops_bridge.py) drives every
handler against a live ChatStore (regen shaping+persist, edit→diff, head-switch, fork, tree, no-response
skips the model); [test_launcher.py](../services/lk/tests/test_launcher.py) §F drives the VCS provider
(no Qt) + the Qt window builds every tab offscreen; [stress_ui.py](../services/lk/tests/stress_ui.py) §J
asserts store↔bridge↔UI wiring + transport isolation; `node --check` clean. **`make check` green.**
**Live edges (open):** live UI visual verification (cargo rebuild + WSLg); section-scoped selective/explain
currently regenerate the WHOLE response with a section-focused directive (true partial-region patch =
later); **N-77** synthesis (Phase-2) rides the reserved multi-parent seam.
**Edges.** `[D-49] --{builds-on}--> [D-48]` load-bearing · `--{extends}--> [D-23 seam, D-26 citations]`
significant · `--{enables}--> [N-77, N-72-full]` significant · `--{gated-by}--> [N-67 integrity]` significant.

---

## D-50 — N-75 cut-corner hardening (uncommitted-UI audit) (2026-06-20) — N-75, Phase-1
**Audit of the uncommitted D-48/D-49 work** before moving on found five real shortcuts; all fixed in
[variants/classic/app.js](../apps/desktop/web/variants/classic/app.js) (+ styles.css) and re-gated.
- **A — `window.prompt` removed.** Edit + informed-regen guidance used `window.prompt`, unreliable/blocked
  inside the Tauri (webkit2gtk) webview → would silently no-op = a fake control under the N-67 gate. Replaced
  with **`promptInline`**: a real in-composer input bar (single-line/textarea/number), Enter=OK
  (Ctrl/Cmd+Enter multiline), Esc=cancel, returns a Promise.
- **D — §3a ops surfaced.** The bridge already supported `selective`/`explain`/`extend`/`compress`, but the UI
  `REGEN_OPS` exposed none of them (§3a was over-claimed as done). Added them: **selective/explain operate on a
  real text selection** (`selectionchange` capture scoped to the message body via `selectionWithin`);
  **extend/compress take an N** via `promptInline`.
- **C — branch/switch now reach the live feed.** `loadChat` only filled the history *preview*; branch-off and
  variant-switch left the feed showing the OLD conversation. New **`loadChatIntoFeed`** renders a stored chat's
  active path into the feed (durable ids + chatId + diff + sibling-count variant nav from `/tree`); branch,
  the ‹k/n› switcher, the minimap node-click, and `loadChat` all route through it.
- **B — no-response note never drops.** `submitNote` bailed ("No active chat") when the session hadn't run a
  turn. Now adopts the kernel's active chat (`/health.activeChat`, already exposed) and **creates one if truly
  none exists**, so the note always reaches logs + journal.
- **E — latent variant-init bug.** `regenerateMessage` could seed variant-0 with the *new* text; now captures
  `prevText` before overwrite so the original stays browsable.
**Verification.** [stress_ui.py](../services/lk/tests/stress_ui.py) §J extended — asserts no `window.prompt`,
`promptInline` present, selective/explain/extend/compress reachable, real selection capture, feed-load on
branch/switch, and note-never-drops. `node --check` clean; **`make check` green (40 suites).** Still open:
the live visual verify (cargo rebuild + WSLg) and true partial-region section patching (whole-response regen
with a section-focused directive remains the Phase-1 form).
**Edges.** `[D-50] --{hardens}--> [D-49]` load-bearing · `--{gated-by}--> [N-67 integrity]` significant.

---

## D-51 — N-67 integrity audit, pass-1: control-surface sweep + proactive gate (2026-06-20) — N-67, Phase-1
**§K.0.1 #1 (integrity).** Enumerated the full classic-variant control surface (toggles: audio, video,
voice-listen, retrieval, deep-search, proactive; buttons: attach file/url, refresh-context, chat new/save/
archive, history open/refresh, minimap, tasks add/remember/clear/check/remove, reminders add/remove,
settings/advanced/drawer panels, stop/cancel, action confirm/reject, token-reset) and traced each to its
backend path. **Integrity matrix verdict: every control REAL except one.**
- **`proactive-toggle` was OVER-CLAIMED → fixed.** It only wrote `config.proactive` into the per-turn config;
  the kernel's unprompted-findings loop (`_maybe_proactive`, sensor-driven) ignored it, so "proactive off"
  still surfaced findings. Added a real consent gate: `DesktopBridge.proactive_enabled` (default on, env
  `LK_PROACTIVE`), checked at the top of `_maybe_proactive`; `set_observer` now accepts
  `observer="proactive"`; the UI toggle + `startDefaultObservers` push the state via the existing `/observer`
  endpoint (ADD-only, I5). [ui_bridge.py](../apps/desktop/scripts/ui_bridge.py) +
  [app.js](../apps/desktop/web/variants/classic/app.js).
- Confirmed REAL (spot-traced): tasks_command handles add/remove/done/reopen/clear+scope/remember;
  reminders add (POST) + remove (DELETE /reminders/{id} → reminder_delete); observers vision/audio start/stop
  real observer threads; cancel = DELETE /jobs/{id} (cooperative, D-37); chat ops = D-48/49/50.
**Verification.** [test_autonomy.py](../services/lk/tests/test_autonomy.py) extended — flips
`proactive_enabled` off and asserts the loop does NOT call `run_proactive`; [stress_ui.py](../services/lk/tests/stress_ui.py)
asserts the UI→`/observer`→loop-gate wiring. **`make check` green (40 suites).**
**Open (N-67 remainder):** qualitative "elegant/non-obstructive/well-integrated" pass + explicit re-grade of
D-35/D-39(voice)/D-40(telemetry)/D-41(lifecycle).
**Edges.** `[D-51] --{operationalizes}--> [§K.0.1 #1]` load-bearing · `--{extends}--> [N-10]` significant ·
`--{re-grades}--> [D-35/D-39/D-40/D-41]` significant · `--{continues}--> [D-50 cut-corner audit]` significant.

---

## D-52 — Windows host process-bloat / leak fix + shared [debug] logger (2026-06-20) — host hygiene
**Symptom (user):** after a run, the Windows host accrued **100+ `aspnet_compiler.exe` + many `powershell.exe`
+ `msiexec` (Windows Installer)**. **Root cause (two .NET-spawning paths, ungated):**
1. **Per-notification** — [notify.py](../services/lk/notify.py) + the duplicate [cli.py](../services/lk/cli.py)
   `_notify` each spawned a fresh `powershell.exe` running `Add-Type -AssemblyName System.Windows.Forms`
   (loads WinForms → .NET JIT/NGEN compiler chain = `aspnet_compiler.exe`; assembly self-repair = `msiexec`).
   No throttle/dedupe/cap; the unthrottled proactive loop (pre-D-51) fired bursts of them.
2. **Per vision poll (~10s)** — [obs/regions.py](../services/lk/obs/regions.py) `_powershell_windows` spawned a
   WinForms-loading + inline-`Add-Type` powershell **every poll** while vision was on — a steady compiler drip.
**Fix.**
- `notify.py` is now the single choke point: **dedupe** (identical title/body within 120s) · **throttle**
  (≥4s global spacing) · **cap** (≤3 live balloons, reaped each call so it's truthful) — all env-tunable, all
  counted. `cli._notify` now **delegates** to it (duplicate ungated spawner deleted).
- `screen_windows()` gained a **TTL cache** (`LK_WINDOWS_CACHE_TTL`, default 30s, `force=` bypass) so the
  vision loop reuses the window layout instead of re-spawning powershell each tick. No process leak: balloon
  Popens are reaped; the last ≤3 self-exit in ~1s.
- New [debuglog.py](../services/lk/debuglog.py): one stdlib `[debug]` mechanism for all services (off by
  default `LK_DEBUG`; structured lines + always-on truthful counters via `bump`/`snapshot` for /metrics+tests).
**Typed test contract** — [test_notify.py](../services/lk/tests/test_notify.py) (wired into `make check`):
`notify(title,body)` → returns True **iff** a balloon spawned; **FIRES** on first/after-throttle/under-cap/
not-recently-seen; **must NOT** spawn on identical-within-dedupe · within-throttle · at-cap. `screen_windows()`
→ **probes** on first/after-TTL/`force=True`; **must NOT** probe within TTL (returns cache). All asserted.
**`make check` green (41 suites).**
**Open / not addressed here (plan, not code):** a deeper host-hygiene pass for the other powershell callers
(hotkey relaunch churn, `ctl.py`/`obs` probes) → tracked as **N-78 (host-process hygiene)**; full `debuglog`
rollout across bridge/kernel/observers/schedule → **N-79**.
**Edges.** `[D-52] --{unblocks}--> [N-61 desktop/host stress]` significant · `--{amplified-by}--> [proactive
N-07]` significant · `--{seeds}--> [N-79 debug-logging]` load-bearing.

---

## D-53 — Atomic service registry: the subsystem partition as gate-guarded code (2026-06-20) — N-66 (ATOMIC), pass-1
**What.** N-66's "Method: output a service inventory" made **executable and enforced**, not a doc. New
[services/lk/services.py](../services/lk/services.py) declares the **14 subsystems (S1–S14)** — mirroring
[docs/diagrams/README.md](../docs/diagrams/README.md) — each as a node with: **one objective** (single
sentence), the **modules it owns**, its **public contract** (`module:symbol`), typed **couplings** to other
nodes (nature from the diagram legend vocabulary), and the **invariant it preserves** (I1/I3/LOCAL-FIRST/…).
This is the near-term half of N-66: *atomize now behind the in-process calls* so the boundary is explicit,
disjoint, and stays that way; N-64 lifts each node to n8n later without re-deriving seams.
**Why it's real, not decorative.** [test_services.py](../services/lk/tests/test_services.py) (wired into
`make check`) enforces the partition every build:
- **disjoint + TOTAL cover** — every engine `.py` under `services/lk` (47 modules) is owned by **exactly one**
  node; a new/moved module that claims no owner **fails the build** (drift guard). Small reasoned `EXEMPT` set
  (the registry itself, `lock.py`/`debuglog.py` shared infra, `launcher/`, tests, `__init__`).
- **one objective per node** (single sentence — atomicity), **contract symbols resolve** in the owning module
  (catches a renamed entrypoint), **exactly one memory writer** (S5) which **must** declare I1, **model-seam**
  couplings must target S7, **single-writer** couplings must target the writer.
**Artifact.** [docs/SERVICE_INVENTORY.md](../docs/SERVICE_INVENTORY.md) is generated from the registry
(`python3 -m lk.services`); never hand-edited.
**Typed test contract.** INPUT = the declared registry + the live module tree. OUTPUT = pass iff 14 nodes,
one objective each, disjoint+total ownership, contracts resolve, exactly one I1 writer. FAIL = drift (unowned
/double-owned module), renamed contract symbol, compound objective.
**Open (N-66 remainder).** Per-subsystem *internal* extraction (breaking the few remaining direct cross-store
writes behind each node's contract) is iterative and gate-guarded; the partition + drift gate land first.
**`make check` green (44 suites).**
**Edges.** `[D-53] --{enables}--> [N-64 n8n substrate]` load-bearing · `--{shapes}--> [N-65/N-67/N-68]`
significant · `--{operationalizes}--> [§K.0.1 #2 ATOMIC]` load-bearing · `--{mirrors}--> [N-68 diagrams]`.

---

## D-54 — Turn-stage cache + per-stage timing: the N-32 pipeline substrate (2026-06-20) — N-32 (LOCAL-PERF), pass-1
**What.** N-32 menu items **(c) cache stage outputs by input identity** and **(d/e) the pre-preparation seam**,
plus the per-stage **instrumentation** the plan flagged as the open prerequisite. New
[kernel/turncache.py](../services/lk/kernel/turncache.py): a **bounded LRU + TTL, thread-safe, content-addressed**
cache with `memoize(stage, parts, producer)` and a `stage_timer(stage)` context manager — pure stdlib (I4),
counters via the D-52 `[debug]` logger.
**Wired into `run_turn`** ([kernel/invoke.py](../services/lk/kernel/invoke.py)): retrieval (both the engine
`gather` path and the legacy `retrieve` path) is memoized by **(query, frozen-context text, deep)**, and the
response/retrieve stages are timed. A cache **miss runs exactly as today** (behavior-preserving); an identical
(query+context) within the TTL **reuses the bundle** instead of re-running the engine. It does **not** make the
model faster (that is N-65 serving) — it removes *repeated* work (rapid identical queries, proactive re-probe,
expansion reuse).
**Observability.** The bridge status payload gains a **`turn`** block (`_turn_metrics`):
`stagesMs` (cumulative ms per stage) + `cache` (hit/miss/evict/expire) + `cacheConfig` — so "where does a turn
spend time" and "did the cache help" are inspectable without a profiler. Env: `LK_TURNCACHE` (off-switch),
`LK_TURNCACHE_TTL` (300s), `LK_TURNCACHE_MAX` (128).
**Typed test contract** — [test_turncache.py](../services/lk/tests/test_turncache.py) (wired into `make check`):
*memoize* — runs producer **once** per (key, TTL window); **hit** = same stage+parts within TTL under the cap;
**miss** = first call · expired · distinct parts · LRU-evicted · disabled · producer raised (failures never
cached, degrade). *run_turn level* — two byte-identical-context turns with the same query → engine `gather`
called **once** (the reuse win); a distinct query re-gathers.
**Open (N-32 remainder, needs live profiling).** True stage **parallelism / pipelining** across turns and
**predictive prefetch during idle** are the next iteration — they need a live `dot`-profile of the real
per-stage DAG (the `turn.stagesMs` counters now make that measurable). Marked `[~]`.
**`make check` green (44 suites).**
**Edges.** `[D-54] --{concretizes}--> [N-32]` load-bearing · `--{pairs}--> [D-55 N-22 watchdog]` significant ·
`--{built-on}--> [D-52 debuglog]` load-bearing · `--{anticipates}--> [N-70 parallel-facet runtime]` significant
· `--{serves}--> [§K.0.1 #3 USABLE-LOCAL]`.

---

## D-55 — Turn-wide deadline / watchdog across the multi-stage pipeline (2026-06-20) — N-22 (A4)
**What.** D-09 bounds each *model call* with a wall-clock deadline; N-22 extends that to the **whole turn**.
New `TurnConfig.turn_deadline_s` (default **None = off**, no behavior change) composes a single turn-wide
deadline into the existing `should_stop` watchdog at turn start — so every stage that already honors
`should_stop` (retrieval + response + expansion) is now covered by one ceiling, raising `TurnCancelled`
without touching each call site.
**Typed test contract** — extended [test_cancel.py](../services/lk/tests/test_cancel.py): a past deadline
**aborts the turn via `TurnCancelled`** even when the caller's `should_stop` never fires; the aborted turn
**writes nothing** to rolling memory; with the default (no deadline) a turn **still completes**.
**`make check` green (44 suites).**
**Edges.** `[D-55] --{extends}--> [D-09 deadlines]` load-bearing · `--{pairs}--> [D-54 N-32]` significant ·
`--{serves}--> [§K.0.1 #3 USABLE-LOCAL]` (never hang the turn).

---

## D-56 — Bridge concurrency hardening: observer-lifecycle race fixed + conflict harness (2026-06-20) — N-67/reliability
**Defect (real, found by pathway audit).** The bridge runs under `ThreadingHTTPServer` (one thread per
request), but `_set_vision`/`_set_audio` used **check-then-act with no lock** (`if self.vision: return;
self.vision = VisionObserver(); .start()`). Two UI actions within K ms — "vision on" double-clicked, or "audio
on" (set_observer) racing "voice on" (set_voice_listen, which used a *different* lock) — could interleave and
**leak a running observer** (`self.vision=None` while an observer keeps capturing → the exact bloat class of
[D-52]). The proactive trigger had the same check-then-set double-spawn race on `_proactive_busy`.
**Fix.**
- One **`_observer_lock` (RLock)** serializes ALL sensor+voice lifecycle transitions (set_observer vision/
  audio/proactive + set_voice_listen, which replaced its narrow `_voice_lock`).
- A **separate `_proactive_lock`** guards the proactive busy-flag check-then-claim and its reset — kept
  distinct from the lifecycle lock so a sensor `stop()/join()` (which can wake the observer thread mid
  `_on_context_event → _maybe_proactive`) **can never deadlock** against a concurrent toggle.
- Result matches the **journal's** already-correct single-flight pattern ([kernel/journal.py](../services/lk/kernel/journal.py) `fire()`); proactive was the laggard, now aligned.
**Typed test contract** — [test_bridge_races.py](../services/lk/tests/test_bridge_races.py) (in `make check`):
fake observers keep a global start/stop ledger; under a 60-thread on/off **storm** the invariant
**live == (1 if bridge thinks on else 0)** holds (no leak) for vision (A), audio across *both* control paths
(B), redundant on/off is idempotent & reports `changed` truthfully (C), and concurrent events spawn proactive
**at most once** (D). Directly answers "press X then W within K seconds — does it hold?": **now yes.**
**`make check` green (47 suites).**
**Edges.** `[D-56] --{operationalizes}--> [§K.0.1 #1 INTEGRITY]` load-bearing · `--{prevents}--> [D-52 host
bloat class]` significant · `--{aligns-with}--> [journal single-flight]` significant · `--{feeds}--> [N-61
desktop stress]`.

---

## D-57 — CI/CD pipeline + backup retention (2026-06-20) — compliance / reliability
**CI/CD.** New [.github/workflows/ci.yml](../.github/workflows/ci.yml): an **offline-gate** job
(`make lint` + `make test-fast` + `make check`) on a Python **3.11/3.12 matrix** (no model/server/network —
the kernel keeps heavy deps lazy, I4), concurrency-cancel on re-push, plus a **diagram-lint** job that
installs Graphviz and runs `mmd2svg.py build` (the N-68 geometry gate). Every push/PR to master now runs the
same gate developers run locally.
**Backup retention (reliability).** `memops.backup()` previously wrote zips into `.runtime/memory-backups`
**forever** — every `clear()`/manual backup grew the tree until the disk fills (itself a crash cause). Added
`prune_backups(keep=LK_BACKUP_KEEP, default 10)` called after each `backup()`; `KEEP=0` = explicit unbounded.
**Typed test** — [test_backup.py](../services/lk/tests/test_backup.py) (in `make check`): backup() yields a
zip; the dir never exceeds KEEP (newest kept); explicit prune trims to N; KEEP=0 disables. Paths redirected to
a temp tree so real memory/ is untouched.
**Edges.** `[D-57] --{serves}--> [compliance/CI]` · `--{hardens}--> [crash/recovery]` significant ·
`--{runs}--> [make check + N-68 lint]`.

---

## D-58 — UI declutter pass-1: flatten nested drawer chrome (2026-06-20) — N-10
**Problem (user: "the UI is too cluttered in the way it presents itself").** The options drawer rendered as
**boxes-inside-a-box**: each of 6 sections (Context/Runtime/Journal/Reminders/History/Files) had its own
border + fill *inside* the already-bordered, blurred drawer — doubling the visual chrome.
**Change (CSS-only, [styles.css](../apps/desktop/web/styles.css), ALL control IDs unchanged → integrity
preserved).** Flattened `.drawer-section` (no border/fill), demoted `.drawer-title` to a light uppercase
label, grouped by whitespace + roomier gaps/padding, and gave the (now lighter) drawer more max-height so it
breathes instead of scroll-cramping. Reversible; no JS/markup change.
**Status.** `[~]` — **LIVE-VERIFY pending** (sandbox can't render the Tauri webview; needs `cargo build
--release` + WSLg relaunch to confirm the visual). The N-10 deep pass (information hierarchy across the whole
surface, the §Q.9 P1 renderer, N-72 frames) remains the larger refinement.
**Edges.** `[D-58] --{advances}--> [N-10 canonical UI]` · `--{gated-by}--> [N-67 integrity]` (no control
removed) · `--{precedes}--> [N-72 shared-space]`.

---

## D-74 — N-81 B9c: organization — tags / folders / sort / bulk (2026-06-21) — N-81
Catalog **#7 organization**: chat-level **tags**, **folders/collections**, selectable **sort**, and **bulk ops**
over a multi-selection. Pure stdlib, ADD-only endpoints (I5), single writer (I1), graceful degrade (I4). Projects
(#11) still LAST.
- **Store** ([chats.py](../services/lk/ctx/chats.py)): tags are a normalised meta list (`set_tags`/`add_tag`/`remove_tag`,
  case-insensitive de-dupe keeping first-seen casing; `all_tags()` = facet+counts). Folders are a flat label
  (`set_folder`, blank ⇒ unfile; `all_folders()` facet). `list_chats(folder=, tag=, sort=)` filters (folder `"none"`
  ⇒ the unfiled set; tag is case-insensitive) and `_sort(rows, sort=)` adds **recency|created|title|messages** keys —
  **pinned always floats first** regardless of key. Tagging/foldering are org actions → they do **NOT** bump
  `updated`. `bulk(ids, op, value=)` loops the existing single-chat ops (trash|restore|archive|unarchive|pin|unpin|
  tag|untag|folder) → `{op, ok[], failed[]}`; unknown op raises `ValueError` (per-chat exceptions degrade to failed).
- **Bridge** ([ui_bridge.py](../apps/desktop/scripts/ui_bridge.py)): `chat_tags` (set/add/remove), `chat_folder`,
  `chat_bulk` (validates op + non-empty ids → 400). `chats_index(params)` now threads `?folder=&tag=&sort=` and
  emits `tags`/`folders` facet lists alongside `items`/`trash`. Routes: `POST /chats/bulk`, `POST /chats/{id}/tags`,
  `POST /chats/{id}/folder`, `GET /chats/tags`, `GET /chats/folders`. ADD-only.
- **CLI** ([ctl.py](../services/lk/ctl.py)): `lk chats tag/untag/tags`, `folder/folders`, `bulk <op> <id…> [--value v]`
  (file-level like pin/trash — **same LK_MEM_DIR gotcha**; never run mutating ops against the real store).
- **UI** (classic [app.js](../apps/desktop/web/variants/classic/app.js) + [styles.css](../apps/desktop/web/styles.css)):
  org control bar (sort `<select>` + folder/tag filter dropdowns fed by facets), per-chat tag/folder chips (click →
  filter), 🏷/🗀 row actions (prompt-driven edit), a leading select checkbox per row, and a bulk-action bar that
  appears when ≥1 chat is selected (Pin/Unpin/Archive/Tag…/Folder…/Delete/Clear). Filters/sort re-fetch via the
  index query params. Selection state survives refresh (prunes vanished ids); bulk keeps only the `failed` ids selected.
- **Tests:** test_chats_dag §M (+24), test_chat_ops_bridge (+18: tags set/add/remove/400/404, folder set/clear/404,
  index facets+folder/tag/sort filters, bulk ok/per-id/empty-400/badop-400/trash), stress_ui (+7 store↔bridge↔UI↔CLI
  contract). **`scripts/check.sh` = CHECK: PASS** (47 suites; retrieval-engine flake did not recur), `node --check` OK.
- **Live-verify (needs a WSLg rebuild):** sort dropdown reorders; folder/tag dropdowns + chip clicks filter; 🏷/🗀
  prompts edit; checkboxes + bulk bar apply across selection; pinned still floats under every sort.
- **Edges:** Projects (#11) will reuse folders as its collection substrate (load-bearing → #11). Tag/folder node-id
  space is chat-level meta (no NoteStore-id collision risk, unlike B5's message ids).

## D-73 — N-81 B9a/B9b: recall integration — promote → note + weighted relevance (2026-06-21) — N-81
Catalog **#6 recall integration**: promote a message into durable memory, and make link/delete *re-weight* recall
(the "link=+, delete=−" decision, [[lawrence-autonomous-spine-decision]]). Local-first, stdlib-only, no model.
- **B9a — promote message → durable note.** Bridge `chat_promote(chat_id, request)` ([ui_bridge.py](../apps/desktop/scripts/ui_bridge.py)) —
  resolves the message id via `_link_node`, reads it (`get_by_id`), and `NoteStore.write_note("excerpt", …,
  source="promote:<mid>", tags=[…,"promoted","chat-excerpt"])`. An optional `note` annotation is **prepended** to the
  body. The back-edge is written `add_edge(note_id, mid, kind="link")` — **deliberately `link`, not `summary`** — so
  the source message ALSO earns the +G weighted-relevance boost (the "link=+" half of #6: promoting a point is an
  explicit signal it matters). NO model turn. Validation: 400 (no messageId) · 404 (unknown message) · 422 (empty).
  The note auto-indexes into recall via the existing `_index_note` hook (db + MemoryIndex). Route: POST
  `/chats/{id}/promote`. UI: a **Promote → note** message-op (`promoteMessage` → optional annotation prompt →
  `/chats/{id}/promote`). CLI: `lk chats promote <chatId> <msgId> [note…]` — bridge when the kernel is up (single-writer
  I1), else file-level via a direct `NoteStore`.
- **B9b — weighted relevance, the delete=−P half (the gap).** The S_ret machinery already existed in
  [retrieval/memory.py](../services/lk/retrieval/memory.py) (`mark_deleted`/`clear_deleted` = −P; `_linked_nodes` reading `kind="link"` edges = +G via
  `LINK_BOOST`), but `mark_deleted`/`clear_deleted` were **never called outside a test** — trashing/deleting a chat did
  NOT remove it from recall. The +G half was already live (B3 `create_link` defaults `kind="link"` → `_linked_nodes`
  picks it up). New bridge helper `_recall_suppress(chat_id, *, deleted)` toggles the penalty for the chat node + every
  message id (collected **before** a hard delete, since the messages then vanish; I4 best-effort — no-op if the memory
  lacks `mark_deleted`). Wired into `chat_trash`/`chat_purge`/`chat_delete`/`chat_empty_trash` (deleted=True) and
  `chat_restore` (deleted=False, reversibly lifts it). A suppressed node is **excluded** from `recall()` (not merely
  down-weighted), so a trashed chat stops surfacing until restored.
- **Tests.** `test_chat_ops_bridge.py` +14 (chat_promote ok/kind/body/tags/back-edge-is-link/+G-set/annotation/400/404/422;
  delete-penalty trash→suppress, restore→clear, purge-before-vanish, hard-delete, I4 degrade — via a `_MemRec`
  recording fake). `stress_ui.py` +4 (promote store↔bridge↔UI↔CLI contract; `_recall_suppress` mark/clear + ≥4 call
  sites). `node --check` clean; `scripts/check.sh = CHECK: PASS` (retrieval-engine flake did not recur this run).
- **Gotcha.** The promote back-edge uses `kind="link"` ON PURPOSE so it counts in `_linked_nodes`; a `kind="promote"`
  would have been invisible to the boost. Delete-penalty ids must be collected **before** purge/hard-delete.
- **Live-verify (needs ONE WSLg rebuild).** Promote → note op shows the annotation prompt + success metric;
  trashed chats drop out of recall and reappear on restore.
**Edges.** `[D-73] --{implements}--> [N-81 #6 recall integration]` · `--{realises}--> [autonomous-spine link=+/delete=−]` ·
`--{reuses}--> [N-02 MemoryIndex S_ret]` · `--{builds-on}--> [WS-U NoteStore edges]` · `--{precedes}--> [B9c organization #7]`.

---

## D-72 — N-81 B7/B8: semantic search + pins/bookmarks (2026-06-21) — N-81
**B7 — semantic search** (catalog #2 "semantic", build-order "reuse retrieval FTS") + **B8 — pins/bookmarks** (catalog
#1 pin/favorite + #2 bookmarks/pins + #5 pinned-snippets). Local-first, stdlib-only, no embed model needed for MVP.
- **B7 store ([chats.py](../services/lk/ctx/chats.py)).** `semantic_search(query, *, chat_id, include_archived, include_trashed, limit)` —
  gathers the scoped messages (full event log, so non-active variants match too), builds an **ephemeral `:memory:`
  FTS5** table (`tokenize='porter unicode61'`), BM25-ranks, maps rows back to message metadata + `_hit_snippet`, and
  returns `score`-ranked hits (`ranked:true`). Porter stemming makes it tolerant of word-order/morphology — distinct
  from B2's exact substring/regex (`search`). **No second persistent writer** (per-query in-memory build → I1 intact,
  no index staleness; chat corpora are small). **Graceful degrade (I4):** `sqlite3.OperationalError` (no FTS5) →
  falls back to lexical `search()` tagged `ranked:false`. `_fts_query` mirrors `retrieval.db._fts_query`. Embedding/
  `MemoryIndex` vector recall is a **documented seam** (embed role gated/local-first), not wired for MVP.
- **B8 store.** **Chat pin/favorite:** `pin_chat(chat_id, pinned=True)` sets/clears a `pinned` meta flag; `_sort`
  now keys on `(pinned, updated)` desc so pinned chats float to the top of every listing; pinning does NOT bump
  `updated` (org action, not edit). **Message bookmarks:** atomic `bookmarks.json` registry (`_read/_write_bookmarks`
  temp+replace); `add_bookmark(chat_id, msg_id, note='')` (idempotent per (chatId,messageId) — re-bookmark updates the
  note; returns None for a missing message so nothing dangles; stores a `preview` + optional `note` = a pinned
  snippet), `remove_bookmark`, `list_bookmarks(chat_id=None)`. Hard-delete/purge inline-cleans a chat's bookmarks
  (within the held lock via the non-locking helpers — `_lock` is non-reentrant).
- **Bridge ([ui_bridge.py](../apps/desktop/scripts/ui_bridge.py)).** `chat_semantic_search` (GET `/semantic?q&scope`) · `chat_pin` (POST `/chats/{id}/pin`
  `{pinned}`) · `chat_bookmarks` (GET `/chats/bookmarks?chat=`) · `chat_add_bookmark` (POST `/chats/bookmarks`) ·
  `chat_remove_bookmark` (POST `/chats/bookmarks/remove`). Route guards: GET `/chats/bookmarks` before generic
  `chat_get`; POST `/chats/bookmarks[/remove]` before generic `/chats/`. ADD-only (I5).
- **UI ([app.js](../apps/desktop/web/variants/classic/app.js)/[panel.html](../apps/desktop/web/panel.html)).** **Semantic** search toggle (mutually exclusive with regex; hits `/semantic`,
  shows the score); per-chat-row **★ pin star** (re-sorts to top); per-message **★ Bookmark** op; a **Bookmarks** view
  toggle in the history toolbar (lists bookmarks, jump-to / ✕-remove). All writes flow through the bridge transport.
- **CLI ([ctl.py](../services/lk/ctl.py)).** NEW `lk chats search <q> [--semantic] [--regex] [--chat <id>]` (also **closes the B2 CLI
  parity gap** — there was no search subcommand) · `pin <id> [--off]` · `bookmark <chatId> <msgId> [note…]` ·
  `unbookmark <chatId> <msgId>` · `bookmarks [chatId]`. search/bookmarks-list are read-only (safe even with kernel up);
  pin/bookmark are file-level (matching trash/rename precedent).
- **Tests.** chats_dag §L (+20: ranked hits, score, porter-vs-substring, scope, pin float/flag/no-updated-bump,
  bookmark idempotency/note/missing/scope/remove/dangling-cleanup); bridge (+13: semantic ok/rank/scope/empty, pin
  on/off/404, bookmark add/list/scope/400/404/remove); stress_ui (+6 contract). `scripts/check.sh = CHECK: PASS`
  (one retrieval-quality flake on first run — stochastic fusion sampling, unrelated; green on re-run), `make lint`, `node --check` clean.
- **⚠ Gotcha.** Same `LK_MEM_DIR`-ignored hazard as D-71 — pin/bookmark MUTATE, so never run them against the real
  store in smoke tests; search/bookmarks-list are read-only and safe.
- **LIVE-VERIFY (needs WSLg rebuild):** semantic toggle ranks results; ★ pins a chat to the top; ★ Bookmark + Bookmarks
  view jump/remove a message.

**Edges.** `[D-72] --{executes}--> [N-81 §Q.13 #1 pin · #2 semantic+bookmarks · #5 pinned-snippets]` ·
`--{reuses}--> [N-02 retrieval FTS5/BM25 pattern]` (semantic) · `--{builds-on}--> [N-75 DAG]` (message ids as bookmark
targets) · `--{extends}--> [D-67 B2 search]` (semantic = ranked sibling of lexical) · `--{gated-by}--> [I1, I4, I5]`.

---

## D-71 — N-81 B6: full backup / restore + merge-conflict resolution (2026-06-21) — N-81
**B6 — persistence/backup** (user catalog #4: backup-all + import + restore w/ merge-conflict resolution). A complete,
**lossless** snapshot that round-trips, distinct from the lossy active-path MDX export.
- **Store ([chats.py](../services/lk/ctx/chats.py)).** `backup_all()` → `{version, kind:"lawrence-chat-backup", exported, active, count,
  chats:[{meta, messages (full event log), head}]}`. `restore_bundle(bundle, on_conflict=skip|rename|merge)`:
  a **new** chat id is imported **verbatim** (ids/parents/head preserved, via `_install_chat` atomic temp+replace);
  on a colliding id — **skip** (keep existing), **rename** (`_remap_ids` re-ids the incoming copy, conflict-free),
  or **merge** (`_merge_into`: union the logs — identical-by-id+text deduped; new-by-content appended with parents/
  edit_of remapped as **browsable sibling variants** with `set_head=False` so the active path is untouched;
  same-id/different-text = a **conflict**, BOTH kept). Returns `{imported, skipped, renamed, merged:[{id,added,conflicts}]}`.
- **Merge bug fixed.** Conflict/dedup detection runs against an **immutable snapshot of the original** messages —
  a freshly-merged node reuses the `<chatId>:<seq>` id space, so checking a live map let an incoming id spuriously
  collide with a just-merged node (over-counted conflicts).
- **Bridge ([ui_bridge.py](../apps/desktop/scripts/ui_bridge.py)).** `chat_backup` (GET `/chats/backup`) + `chat_restore_bundle` (POST `/chats/restore`,
  accepts `{bundle, onConflict}` or a bare bundle; lands the UI on a valid active chat after a bulk import). ADD-only (I5).
- **UI ([app.js](../apps/desktop/web/variants/classic/app.js)/[panel.html](../apps/desktop/web/panel.html)).** **Backup all** downloads a JSON bundle; **Restore…** = file picker → confirm (merge) /
  cancel (rename). Results surfaced in the below-input status line.
- **CLI ([ctl.py](../services/lk/ctl.py)).** `lk chats backup [path]` (read-only, file-level even with the kernel up) + `lk chats import
  <path> [--skip|--rename|--merge]` (a WRITE → through the bridge when the kernel is up for single-writer I1, else file-level).
- **Tests.** chats_dag §K (+25: backup shape, verbatim import, skip no-dup, rename re-id+internal-consistency, merge
  dedup/conflict/non-destructive, guards); bridge (+13: backup/restore/skip/rename/merge/bare-bundle/404s); stress_ui
  (+4 contract). All gates green (`scripts/check.sh = CHECK: PASS`, `make lint`, `node --check`).
- **⚠ Gotcha (recorded).** `ChatStore` ignores `LK_MEM_DIR` (hardcoded `REPO_ROOT/memory`) — smoke-test the store with
  `ChatStore(mem_dir=tmp)`; never run mutating `lk chats …` against the real store (it edits live data).
- **LIVE-VERIFY (needs WSLg rebuild):** Backup all downloads a file; Restore… imports it; merge vs rename confirm dialog.

**Edges.** `[D-71] --{executes}--> [N-81 §Q.13 #4]` · `--{builds-on}--> [N-75 DAG]` (append-only log + head + variants) ·
`--{reuses}--> [D-69/D-70 store+bridge+CLI+UI seams]` · `--{gated-by}--> [I1 single-writer, I5 ADD-not-rename]`.

---

## D-70 — N-81 B5: summarize → context (note + inline recap + cross-chat anchor) (2026-06-21) — N-81
**B5 — summarize→context** (user catalog #12/#13; **first MODEL-touching chat-mgmt batch**). Summarize a chat into a
compact block and route it; sink = **BOTH** (durable note + inline recap) plus an optional cross-chat anchored insert.
- **Model seam — no-persist turn ([ui_bridge.py](../apps/desktop/scripts/ui_bridge.py)).** `summarize_chat` builds a turn over the chat's
  active-path text (`_build_summary_turn`: `_SUMMARY_PROMPT`, retrieval forced off, optional `guidance`) tagged
  `_noPersist`. `turn()` now honors `_noPersist` → captures the answer but writes **nothing** to the transcript; the
  active-chat pointer is saved and **restored** in a `finally`, so summarizing chat A while viewing chat B never flips
  the active chat or leaks a phantom turn. (Sync core — mirrors `regenerate()`; async deferred.)
- **#12 BOTH sinks.** (a) `notes.write_note('summary', …)` → a durable NoteStore note, `add_edge(note, chat, kind='summary')`
  auto-linking it back to the source chat (B3 edge); (b) an inline `kind='summary'` message appended to the source chat,
  plus a note↔inline-message edge and a best-effort recall upsert.
- **#13 cross-chat anchored insert ([ctx/chats.py](../services/lk/ctx/chats.py)).** New `insert_after(chat, anchor, …)`: anchor is a leaf →
  the block extends that path inline; anchor is mid-path → it is recorded as a **non-destructive sibling branch**
  (browsable via the variant switcher) so the existing conversation is never disrupted. Backed by a new
  `append_message(set_head=…)` guard (don't repoint head when False). Append-only / DAG-faithful (I1).
- **Route.** `POST /chats/{id}/summarize {guidance?, target?:{chatId,msgId}}` (ADD-only, I5).
- **UI ([app.js](../apps/desktop/web/variants/classic/app.js) + [styles.css](../apps/desktop/web/styles.css)).** Per-chat **Summarize** chip (`data-summarize-chat`) →
  `openSummarizePicker`: a two-stage ephemeral panel (optional focus input + "Summarize → note + inline", then "insert
  into another chat" → that chat's messages as anchor buttons). `summarizeChat` POSTs, reports the sink + insertion
  point, reloads the source chat if on screen.
- **CLI parity ([ctl.py](../services/lk/ctl.py)).** `lk chats summarize <id> [--into <chatId> <msgId>] [guidance…]` (+ a new `_post_json`
  helper) — POSTs to the running bridge since summarization needs the model; degrades with a clear message if the
  bridge is down.
- **LOCAL-FIRST.** Runs through the same kernel turn path as any chat (local model); no cloud default.
- **Latent cross-subsystem note.** NoteStore + ChatStore both mint ids from `%Y%m%d-%H%M%S` → a note created the same
  second as a chat can collide, making the bare note↔chat edge a self-loop (rejected). B5 always also links the note to
  the inline summary message (`chatId:seq`, collision-free), so chat connectivity holds; the bare-id space deserves a
  real fix later (tracked in PLAN §Q.13 item #5).
- **Gates (offline, green).** [test_chats_dag.py](../services/lk/tests/test_chats_dag.py) §J +12 (insert_after leaf-inline vs mid-path branch,
  parent/tree/meta, set_head guard), [test_chat_ops_bridge.py](../services/lk/tests/test_chat_ops_bridge.py) +17 (no-persist contract, retrieval-off + guidance
  shaping, #12a note+edge, #12b inline, #13 anchored insert, active-chat-not-flipped, no-LEAK, 404/400 guards),
  [stress_ui.py](../services/lk/tests/stress_ui.py) +8 (store/bridge/UI/CLI + CSS), **full `scripts/check.sh` = CHECK: PASS**, `node --check`, `make lint`.
**Status.** `[~]` — store/bridge/CLI exercised real with a fake turn (the only un-exercised path is the live model
producing the summary text). **LIVE-VERIFY pending** (rebuild): Summarize chip → note appears + inline recap in the
source + (with a target) a block at the chosen anchor in another chat; active chat unchanged; `lk chats summarize`.
**Edges.** `[D-70] --{executes}--> [N-81 §Q.13 B5 (#12/#13)]` · `--{builds-on}--> [N-75 DAG]` (insert_after/head) ·
`--{reuses}--> [B3 NoteStore edges]` (auto-link) · `--{reuses}--> [the kernel turn path]` (no-persist) ·
`--{honors}--> [I1 single-writer / I5 add-only / LOCAL-FIRST / GUI==CLI]` · `--{continues-as}--> [N-81 backup+merge]`.

---

## D-69 — N-81 B4: temporary chats (adjustable auto-expire timer) (2026-06-21) — N-81
**B4 — temporary chats** (user catalog #7: "temporary chats with adjustable timer"). A chat can carry a TTL; when
it elapses it is **moved to the trash** (reversible — the existing B1 trash lifecycle then governs final purge), so a
temp chat never silently destroys data.
- **Store ([ctx/chats.py](../services/lk/ctx/chats.py)).** Additive, back-compatible meta fields `ephemeral` / `ttl_minutes` /
  `expires_at` (absent ⇒ a normal permanent chat). `create_chat(title, *, ttl_minutes=None)` (>0 ⇒ ephemeral with a
  future `expires_at`); `set_ttl(chat_id, minutes)` — `>0` (re-)arms the timer **from now** (the "adjustable" part),
  `None`/`<=0` clears it back to permanent; `sweep_expired()` — lazy, lock-guarded; trashes every past-due ephemeral
  chat (sets `trashed`/`trashed_at`, clears the active pointer if it expired), writes the registry only when something
  expired, returns the swept ids. Wired into `ensure_default()` so expiry is retired on access (no background thread —
  stdlib core + graceful degrade, I4). `timedelta` added to imports.
- **Bridge ([ui_bridge.py](../apps/desktop/scripts/ui_bridge.py)).** `chat_create` accepts `ttlMinutes`/`ttl_minutes`; new `chat_set_ttl` +
  route `POST /chats/{id}/ttl {minutes}`; `chats_index` calls `sweep_expired()` first so every UI refresh retires
  expired temp chats into the trash payload it already returns.
- **UI ([app.js](../apps/desktop/web/variants/classic/app.js) + [styles.css](../apps/desktop/web/styles.css)).** Per-chat **⏱** control (`data-ttl-chat` → `chatTtlOp` →
  `promptInline` minutes → `POST /chats/{id}/ttl`; blank/0 = permanent) in each history row; `ttlRemaining(item)`
  shows a live "Nm left / expiring…" countdown badge in the title; temporary rows get an amber left-edge + a lit ⏱
  chip. (Make any chat temporary, including a fresh one — covers create+adjust+clear.)
- **CLI parity ([ctl.py](../services/lk/ctl.py)) — GUI==CLI invariant.** `lk chats new [--ttl <min>] [title…]`, `lk chats ttl <id>
  <min|off>`, `lk chats sweep`; plus **B1 parity** (previously GUI-only): `lk chats trash <id>` / `restore <id>` /
  `purge <id|--all>`. Usage strings + docstring updated.
- **Gates (offline, green).** [test_chats_dag.py](../services/lk/tests/test_chats_dag.py) §I +14 (ttl create/set/clear, sweep leaves live alone,
  back-dated expiry → trash → restorable, active-pointer clear, unknown→None), [test_chat_ops_bridge.py](../services/lk/tests/test_chat_ops_bridge.py) +7
  (chat_create ttl, set_ttl arm/clear/404, chats_index sweep→trash), [stress_ui.py](../services/lk/tests/stress_ui.py) +5 (store/bridge/UI/CLI),
  **full `scripts/check.sh` = CHECK: PASS**, `node --check`, py syntax.
**Status.** `[~]` — store/bridge/CLI exercised real (no rebuild needed). **LIVE-VERIFY pending** (rebuild): ⏱ sets a
timer + countdown badge shows; an expired chat appears in the trash on the next refresh; CLI `lk chats ttl/sweep`.
**Refinement deferred:** a *sliding* (activity-reset) window — currently expiry is a fixed point, user-adjustable.
**Edges.** `[D-69] --{executes}--> [N-81 §Q.13 B4]` · `--{reuses}--> [B1 trash lifecycle]` (expiry → trash → purge) ·
`--{honors}--> [I4 stdlib-core/graceful-degrade]` (lazy sweep, no thread) · `--{honors}--> [GUI==CLI parity]` ·
`--{continues-as}--> [N-81 B5 summarize→context]`.

---

## D-68 — N-81 B3: link-at-message + backlinks (2026-06-21) — N-81
**B3 — per-message cross-references in the kernel note graph.** User's first batch included "Link + delete/trash
+ restore" and "Link at response level"; this adds linking + backlinks **at the message level** (query OR response).
- **Store (reused, no change).** Links live as **NoteStore edges** ([ctx/notes.py](../services/lk/ctx/notes.py)) — `add_edge`
  (bidirectional, idempotent, self-loops/empties rejected), `edges_for` (annotates each edge `dir=out|in` + `peer`),
  `neighborhood` (out/in peers + edges, plus note `links`/`backlinks` when the node is itself a note). A message node
  is the id `"<chatId>:<seq>"`; a note node is the note id — so messages and notes link uniformly.
- **Bridge (reused, no change).** `create_link({src,dst,kind})` + `_link_node` (normalises a `{chatId,msgId|seq}`
  message / `{noteId}` note / raw id → a graph node) via `POST /links`; `links_for(chatId,msgId)` via
  `GET /links/{chatId}/{msgId}` returns the neighborhood. B3 wired the **UI** to the endpoints that already existed.
- **UI ([app.js](../apps/desktop/web/variants/classic/app.js) + [styles.css](../apps/desktop/web/styles.css)).** Per-message **Link…** (`data-chat-op="link"`) opens an ephemeral
  `openLinkPicker` (pick another chat from the history list, or type a note id / `chatId:seq`) → `createMessageLink`
  → `POST /links`. **Links** toggle (`data-chat-op="links-toggle"`) lazily fetches `GET /links/…` (`toggleLinks` →
  `refreshMessageLinks`) and renders an inline panel (`renderLinks`): outgoing `→` / incoming `←` peers + note
  backlinks, each a clickable `data-link-peer` row → `openLinkPeer` (message → open chat + scroll; whole-chat → open
  chat; note → status). `linkLabel` prettifies node ids to chat-title·#seq; `linkCount` shows the count once loaded.
  Per-message controls are JS-rendered by `render()` (shared by index.html + panel.html) → **no static HTML change**.
  Pickers never stack (`openRegenPicker`/`openLinkPicker` clear `.regen-picker, .link-picker`).
- **Gates (offline, green).** [test_chat_ops_bridge.py](../services/lk/tests/test_chat_ops_bridge.py) +9 (create_link normalise/idempotent/self-loop/missing-dst,
  message↔chat + message↔note edges, `links_for` out/in directions + reverse backlink; fake gained a real
  `NoteStore` + bound `_link_node`), [stress_ui.py](../services/lk/tests/stress_ui.py) +5 (store/bridge/UI/transport/panel), **full
  `scripts/check.sh` = CHECK: PASS**, `node --check`.
**Status.** `[~]` — **LIVE-VERIFY pending** (rebuild): Link… picker links a message to a chat/note; Links toggle
shows out/in/backlink rows; clicking a peer navigates. Backend exercised real (no rebuild needed for the store/bridge).
**Edges.** `[D-68] --{executes}--> [N-81 §Q.13 B3]` · `--{reuses}--> [WS-U NoteStore edges]` ·
`--{builds-on}--> [N-75 DAG message ids]` · `--{continues-as}--> [N-81 B4 temporary chats]`.

---

## D-67 — N-81 B2: chat search (in-chat + global, scope-restrictable) + CI determinism fix (2026-06-21) — N-81 / CI
**B2 — search across chats.** User picked search as a first batch; "general working, not limited to one scope,
but scope restrictable at use time."
- **Store ([ctx/chats.py](../services/lk/ctx/chats.py)).** `search(query, *, regex=False, chat_id=None, include_archived=True,
  include_trashed=False, limit=200)` over the **whole append-only log** (finds matches in non-active variants too);
  case-insensitive substring or **regex** (bad regex → `[]`, never raises); `chat_id` = the use-time scope
  restriction; trashed excluded by default; hits carry chatId/title/messageId/role/ts + a `_hit_snippet` context window.
- **Bridge ([ui_bridge.py](../apps/desktop/scripts/ui_bridge.py)).** `chat_search(params)` + `GET /search?q=&scope=&regex=` (scope = `all` |
  `current` | a chatId); `parse_qs` added to imports.
- **UI ([app.js](../apps/desktop/web/variants/classic/app.js) + [panel.html](../apps/desktop/web/panel.html) + [styles.css](../apps/desktop/web/styles.css)).** History-panel search bar (debounced input, **All chats / This
  chat** scope toggle, **regex** toggle, Clear); results take over the history list with a summary + per-hit
  snippet; clicking a hit `openSearchHit` → loads that chat + scrolls to the message if on the active path.
  (One UI delivers both "find in current chat" and "across all chats" via the scope toggle; semantic + bookmarks
  remain later batches.)

**CI determinism fix (user: "previous CI 2 failed, 1 passed").** Root cause of the 2 failing **offline-gate**
cells (diagram-lint was the "1 passed"): `.gitignore` `memory/chats/*.*` uses a `*.*` glob that **misses the
extensionless `memory/chats/active`**, so that runtime pointer was **tracked** while its `index.json` + chat dirs
were ignored → a fresh CI checkout had a stale `active` with no backing state. Fix: ignore `memory/chats/active`
(+ `memory/**/active`) explicitly and `git rm --cached` it (file kept on disk). A fresh checkout now starts with a
clean `memory/chats/`; `active_chat()` already returns None on a missing pointer → `ensure_default` makes a scratch.

**Gates (offline, green).** [test_chats_dag.py](../services/lk/tests/test_chats_dag.py) +11 (search text/regex/scope/case/trash-exclusion),
[test_chat_ops_bridge.py](../services/lk/tests/test_chat_ops_bridge.py) +5 (scope all/current/byId, regex, empty), [stress_ui.py](../services/lk/tests/stress_ui.py) +4 (store/bridge/UI),
**full `scripts/check.sh` = CHECK: PASS** (mirrors CI offline-gate), `node --check`. Local py3.12 only (3.11 cell
not reproducible here; no 3.12-only syntax used).
**Status.** `[~]` — **LIVE-VERIFY pending** (rebuild): search bar finds across/within chats; scope + regex toggles
work; clicking a hit opens the chat. **CI:** committing this work (incl. the .gitignore fix) should turn the
offline-gate green; if a cell still fails, the Actions log will pinpoint it.
**Edges.** `[D-67] --{executes}--> [N-81 §Q.13 B2]` · `--{fixes}--> [CI offline-gate determinism]` ·
`--{reuses}--> [ChatStore log]` · `--{continues-as}--> [N-81 B3 link-at-message]` · later: semantic search (reuse
[retrieval/db.py](../services/lk/retrieval/db.py) FTS) + bookmarks.

---

## D-66 — N-81 B1: chat trash bin (soft-delete → restore → purge) (2026-06-21) — N-81
**Context.** First batch of N-81 (Chat Management, PLAN §Q.13). User: "Trash bin + delete chats" + "even the
entire chat should be restore-able." Previously "delete" was conflated with "archive" (`delete_chat(hard=False)`
just set `archived`); there was no reversible trash with a purge step.
**Store ([ctx/chats.py](../services/lk/ctx/chats.py)).** New **distinct `trashed` state** (+ `trashed_at`), separate from `archived`:
`trash_chat` (soft-delete, clears active pointer), `purge_chat` (permanent hard-delete), `purge_trashed
(older_than_days?)` (empty bin / auto-purge timer hook), `list_trash`; `restore_chat` now clears **both**
archived + trashed; `list_chats(include_archived, include_trashed)` excludes trashed by default; `ensure_default`
skips trashed.
**Bridge ([ui_bridge.py](../apps/desktop/scripts/ui_bridge.py)).** `chat_trash` / `chat_purge` / `chat_empty_trash` (ADD-only, I5); `chats_index` now
returns a separate `"trash"` list; routes `POST /chats/{id}/trash`, `/purge`, and `/chats/trash/empty`.
**UI ([app.js](../apps/desktop/web/variants/classic/app.js) + [panel.html](../apps/desktop/web/panel.html) + [styles.css](../apps/desktop/web/styles.css)).** History panel: per-chat **Delete** (→trash), a **Trash** toggle
view listing trashed chats with **Restore** + **Delete forever** (confirmed), and **Empty trash** (confirmed);
`chatTrashOp()` drives trash/restore/purge; `refreshHistory` reads `chats.trash`; danger-styled chips.
**Gates (offline, green).** [test_chats_dag.py](../services/lk/tests/test_chats_dag.py) +15 (trash distinct from archive, restore clears both, purge
removes dir, empty-bin), [test_chat_ops_bridge.py](../services/lk/tests/test_chat_ops_bridge.py) +6 (bridge methods + index split + 404), [stress_ui.py](../services/lk/tests/stress_ui.py) +4
(store/bridge/UI wiring), `node --check`, py parse.
**Status.** `[~]` — **LIVE-VERIFY pending** (next rebuild): Delete moves a chat to Trash; Trash view shows it;
Restore brings it back; Delete-forever / Empty-trash purge; active chat reassigns when its chat is trashed.
**Edges.** `[D-66] --{executes}--> [N-81 §Q.13 B1]` · `--{extends}--> [ChatStore archive/restore]` ·
`--{continues-as}--> [N-81 B2 search]` (in-chat + global) `--{then}--> [B3 link-at-message]`.

---

## D-65 — N-80 feedback-1: live-rebuild regressions + sensor/ops fixes (2026-06-21) — N-80 / N-67 / N-10
**Context.** First real WSLg rebuild of the N-80 work. User testing surfaced a regression I introduced plus two
real bugs and several refinement asks (screenshots).

**A1 — config window had NO drag handle (regression from 0A).** 0A hid the floating `.drag-zone` in panel mode
(it was covering panel-head buttons), but `#settings` is the one panel with **no `.panel-head`**, so the config
sidecar lost its only drag surface ("hidden in a magic spot top-left"). **Fix:** added a real `.panel-head`
(title "Config" + ✕) to `#settings` in [index.html](../apps/desktop/web/index.html) + [panel.html](../apps/desktop/web/panel.html); CSS `.settings > .panel-head { grid-column: 1/-1 }`
so it spans the grid; wired `#settings-head-close` → `closeSettingsTray(true)`. (`#advanced-panel` already had one.)

**B1 — the 3rd sensor thumb showed retrieval text as "Audio transcript".** The transcript thumb sourced
`pipeline.transcript || state.metrics.transcript`, which carry the turn/retrieval status line
(`[retrieval] UI-forced single-pass: N sources…`). **Fix ([app.js](../apps/desktop/web/variants/classic/app.js)):** `audioTranscriptText` now rejects any
bracketed status + retrieval/ui-forced/single-pass chatter; the thumb prefers genuine `state.voiceTranscript`
(each candidate filtered). Sensor thumbnails also got a useful **hover tip** (`title = "<sensor> — <latest
context>"`) — partial #7.

**B2 — chat-ops "inactive / can't do them" (a real bug + a perception fix).** Real bug: `streamAssistant`'s
fast path updated the finished message's body/meta via direct DOM surgery but **never called `render()`**, so a
just-completed assistant message had **no msg-ops buttons** (Regenerate/Custom/Edit/Branch) until some later
render — exactly "the chat ops don't work." **Fix:** `streamAssistant` now does one full `render()` at turn-end.
Perception: `.op-btn` was `color: var(--muted)` (read as disabled) → brighter label + clearer border + hover/active.

**C1 — branch map flashes on the right at startup then dismisses.** Diagnosed as NOT a main-window code bug:
[index.html](../apps/desktop/web/index.html) has **zero** `minimap-panel` refs (0C removed it) and no startup code opens a panel. It is a
**leftover `panel-minimap` sidecar window from the pre-rebuild process** being torn down — cleared by
`lk reset` / `lk restart --force` (kills tracked+untracked popups). No code change; operational.

**Gates (offline, green).** [stress_ui.py](../services/lk/tests/stress_ui.py) +5 feedback checks (config header in both files; transcript rejects
retrieval; sensor hover tips; turn-end render of ops; op-btn active styling), `node --check`. Full suite ALL-PASS.
**Status.** `[~]` — **LIVE-VERIFY pending** (next rebuild): config window drags + closes; transcript thumb no
longer shows retrieval; msg-ops appear immediately after a turn and respond; `lk reset` clears the startup flash.
**Still open (folded into PLAN §Q.12 step-5/6, NOT yet built):** link/load/restore at the **message** level (#8);
**distinct** web-call vs retrieval vs transcription sensors (#7); option-drawer "blocky/blocking" redesign (N-10);
config/sampling window polish ("outdated/difficult to adjust"). "14 options inactive for this backend" meta is the
honest WS-K capability marker (local backend lacks those decoding knobs) — wording to be softened in step-5.
**Edges.** `[D-65] --{fixes-regression-of}--> [D-61 0A]` · `--{fixes-live}--> [N-75]` · `--{operationalizes}-->
[N-67]` · `--{advances}--> [N-10]` · `--{feeds}--> [N-80 step-5]` (link-at-message + distinct sensors + drawer).

---

## D-64 — N-80 step-4: branch map → node/edge GRAPH with scrollable hover detail (2026-06-21) — N-80 / N-75 / N-10
**Problem (user, with screenshot).** The branch map rendered as an **indented text tree** (`map-node` boxes with
`margin-left: depth*14px`) — "must NOT be literal messages with indented subsequent messages; it MUST be a
graph-node-edge"; nodes should show a summary by default and a longer **scrollable** detail on hover.
**Fix.** `renderMinimap` ([app.js](../apps/desktop/web/variants/classic/app.js)) now emits a **node→edge graph**: a nested `<ul><li>` whose CSS
([styles.css](../apps/desktop/web/styles.css) `.map-graph`) draws classic org-chart connector edges (parent→child, directed top-down) with
sibling **variants branching side-by-side**. Each `.map-node` is a compact box: a role chip (You/LK), a default
one-line **summary**, a `n/m kind` variant badge, role-coloring, and active-path highlight. **Hover** reveals
`.map-tip` — a **scrollable** (`max-height:160px; overflow:auto`) detail panel that stays open while the pointer
is inside it; the minimap click handler **ignores clicks inside `.map-tip`** so reading/scrolling never triggers
a switch. Clicking a node still head-selects + reloads (sidecar emits `chat-path-changed`). Pure DOM/CSS, no D3.
Backend: [ctx/chats.py](../services/lk/ctx/chats.py) `tree()` nodes gained `summary` (new `_node_summary()` — first meaningful line,
heading/bullet-stripped, capped) + `detail` (≤600 chars); `snippet`/`kind`/`parent` retained for back-compat.
**Gates (offline, green).** [test_chats_dag.py](../services/lk/tests/test_chats_dag.py) +1 (nodes carry summary+detail), [stress_ui.py](../services/lk/tests/stress_ui.py) +5 step-4
(graph not indented text; summary default + scrollable tip; click-switches-but-tip-doesn't; CSS connectors+tip;
tree() summary/detail), [test_chat_ops_bridge.py](../services/lk/tests/test_chat_ops_bridge.py) still green (chat_tree unaffected), `node --check`, `chats.py` parses.
**Status.** `[~]` — **LIVE-VERIFY pending** (WSLg rebuild): map shows boxes+edges (not indented text); node hover
shows a scrollable detail; clicking a variant switches the path; the sidecar map reflects switches in the feed.
**Edges.** `[D-64] --{executes}--> [N-80 §Q.12 step-4]` · `--{fixes-live}--> [N-75 branch map]` ·
`--{builds-on}--> [D-60]` (sidecar window) · `--{advances}--> [N-10]` · `--{continues-as}--> [N-80 step-5]`
(chat-ops discoverability +delete/link, then sensor hover tooltips).

---

## D-63 — N-80 step-3: regenerate UX — single button + ephemeral no-residue picker (2026-06-21) — N-80 / N-75 / N-10
**Problem (user, "the worst possible UIUX").** Every assistant message rendered an always-open 12-item
"Regenerate ▾" dropdown (`op-menu`/`op-dropdown`) — it hogged the message surface and was a poor picker.
**Fix ([app.js](../apps/desktop/web/variants/classic/app.js) + [styles.css](../apps/desktop/web/styles.css)).** `renderMessageControls` now emits exactly two controls on an assistant
message: a **"Regenerate"** button (one-click neutral re-roll — op `regen`, the backend's plain "Regenerate your
previous response", no guidance prompt) and a **"Custom ▾"** trigger. "Custom" opens `openRegenPicker()` — an
**ephemeral** row of all §3a ops inserted just above the composer (reusing the `.inline-prompt` pattern) that
**removes itself with no residue** (Escape or Cancel dismiss; a chosen op runs then closes). `regenerateMessage`
was refactored from `(message, opIndex)` to `(message, spec)`; `DEFAULT_REGEN` is the plain re-roll spec. The
text selection for selective/explain survives the picker via the existing `lastSelection` (captured on
`selectionchange`). Dead `.op-menu`/`.op-dropdown`/`.op-item` CSS removed; no leftover `regen-menu`/`opIndex`
refs. Chose the in-chat ephemeral prompt over a separate Tauri popup window — lighter, no extra window/capability.
**Gates (offline, green).** [stress_ui.py](../services/lk/tests/stress_ui.py) +4 step-3 checks (single button + custom trigger, NO always-open
dropdown; ephemeral self-removing picker; every §3a op reachable; one-click = neutral re-roll), `node --check`,
no dangling dropdown refs. Full suite ALL-PASS.
**Status.** `[~]` — **LIVE-VERIFY pending** (WSLg rebuild): the message surface is uncluttered; "Custom ▾" opens
the picker; picking an op regenerates; Cancel/Escape leaves no residue; selective/explain still read the selection.
**Edges.** `[D-63] --{executes}--> [N-80 §Q.12 step-3]` · `--{advances}--> [N-10 canonical UI]` (declutter) ·
`--{builds-on}--> [D-62]` (regenerateMessage async) · `--{continues-as}--> [N-80 step-4]` (branch-map = graph
node→edge + hover tooltips, separate window).

---

## D-62 — N-80 step-2 (N-75 live correctness): async regen + empty-guard + stuck-streaming watchdog (2026-06-21) — N-80 / N-75
**Context.** Step-2 of N-80 (PLAN §Q.12). The N-75 chat features were built (D-48/49/50) but the live webview
showed 4 interrelated bugs the user hit while testing. Root insight: they all stem from ONE lifecycle flaw —
`regenerate()` ran the model **synchronously** while its streaming deltas spawned a **separate live-draft bubble
that was never handed off** (the orphan), so the UI froze, showed a stuck cursor read as "(empty response)", left
the pill on "Streaming", and only settled variant state after a manual reload.

**#4 — regen was UI-blocking → async job (the keystone fix).** [ui_bridge.py](../apps/desktop/scripts/ui_bridge.py): split `regenerate()` into a
shared `_build_regen_turn()` (validates 400/404 + shapes the directive + `_regen` tag) and `_enrich_regen_result()`
(op echo + diff/editOf). New `regenerate_async()` **enqueues a turn job** (`enqueue_turn`); `_run_turn_job` runs
`self.turn` (which honors `_regen` via `_persist_turn`) then enriches the stored result. HTTP `/chats/{id}/regenerate`
→ `regenerate_async`; the **sync `regenerate()` stays** for tests + fallback. UI [app.js](../apps/desktop/web/variants/classic/app.js): `regenerateMessage`
enqueues → `waitForBridgeJob(...,{noPending:true})` (new opt: poll to completion, don't detach to a "Still Running"
bubble) → cancellable via `activeJobId` (Escape/Stop). `pollRemoteJobs` **skips `source==="regenerate"`** jobs so
the result lands on the variant, never as a fresh bubble.

**#5 — "(empty response)" → in-place stream + empty-guard.** `onDelta` now streams regen tokens **into the target
message in place** (`state.regenTargetUiId`/`regenBuffer`) instead of a stray draft; `finishLiveDraft()` runs on
every exit; if the regen returns empty text the previous variant is kept (message never blanked, honest meta).

**#6 — stuck "streaming" → self-heal watchdog.** `healStuckStream()` on the 3s health tick: when nothing is in
flight it resets a busy pill to Idle and settles an orphaned live-draft that's been silent ≥6s (guarded so it
never cuts off a live remote/voice stream).

**#3 — variant nav ‹n/m›.** Was a downstream symptom of #4/#5: with async regen pushing the variant + `render()`
immediately and switches going through `loadChatIntoFeed` (sibling groups rebuilt from `tree.nodes`; verified every
record carries an explicit `parent` so path/tree keys match), the switcher updates live + survives switch-back.

**Gates (offline, green).** [test_chat_ops_bridge.py](../services/lk/tests/test_chat_ops_bridge.py) (added `_build_regen_turn`/`_enrich_regen_result` to the
fake binding; op/diff/editOf asserts pass), [test_chats_dag.py](../services/lk/tests/test_chats_dag.py), [stress_ui.py](../services/lk/tests/stress_ui.py) (+7 step-2 checks: async route,
enriched job result, sync fallback, UI poll/cancel, empty-guard, in-place stream + poller skip, watchdog),
`node --check` all web JS, `ui_bridge.py` parses.
**Status.** `[~]` — **LIVE-VERIFY pending** (WSLg rebuild): (1) regenerate no longer freezes the UI; (2) the
response updates in place with no stray "(empty response)" bubble; (3) ‹n/m› appears immediately and survives
switching back/forth; (4) the pill returns to Idle after a turn; (5) Escape cancels an in-flight regen.
**Edges.** `[D-62] --{executes}--> [N-80 §Q.12 step-2]` · `--{fixes-live}--> [N-75]` (regen/variant/streaming) ·
`--{builds-on}--> [D-61]` (systemic) + `[D-48/49/50]` (N-75 build) · `--{reuses}--> [/turn/async job machinery]` ·
`--{continues-as}--> [N-80 step-3]` (regenerate-UX redesign: single button + custom popup, no residue).

---

## D-61 — N-80 step-1 (systemic): drag-region click-fix (0A) + panel-host extraction (0C) (2026-06-21) — N-80 / N-67 / N-10
**Context.** First execution step of N-80 (PLAN §Q.12). The user's 2026-06-21 testing exposed two systemic
defects that made everything else hard to test honestly: "top-bar / panel buttons (create-new, ✕) blocked by
drag" and "options shifted outside the window still bloat the main window by remaining hidden."

**0A — panel header buttons "blocked by drag" — REAL root cause found.** Read Tauri **2.11.2**
[`drag.js`](../../.cargo/registry) `isDragRegion`: clickable elements (BUTTON/A/INPUT…) **already short-circuit**
drag, so a button *inside* a drag region is NOT eaten — the prior "generic WebKitGTK quirk" diagnosis was wrong.
Actual culprit: in a sidecar/panel window the MAIN [`.drag-zone`](../apps/desktop/web/styles.css) div was restyled to
`left:0;right:0;height:40px;z-index:3` and **floated over the top 40px of the panel — on top of the panel-head's
✕ + action buttons**, so every click hit the invisible drag overlay → window-drag, click swallowed.
**Fix (drag preserved, version-correct, NO JS interceptor):**
- [styles.css](../apps/desktop/web/styles.css): `.panel-window .drag-zone { display:none }` (the panel-head is the drag surface in panel mode).
- [index.html](../apps/desktop/web/index.html): all panel headers → `data-tauri-drag-region="deep"` (whole header drags; clickable children short-circuit).
- [app.js](../apps/desktop/web/variants/classic/app.js): removed the now-redundant per-minimap `removeAttribute` hack from D-60; kept Esc-to-close.

**0C — main-DOM declutter (partial, honest).** New [panel.html](../apps/desktop/web/panel.html) = the sidecar **panel host**
(structural mirror of index.html so the shared app.js loads unchanged either window); `open_panel` now loads
`panel.html?panel=X` ([main.rs](../apps/desktop/src-tauri/src/main.rs)). **The four pure-UI panels (tasks/reminders/history/minimap) are
deleted from [index.html](../apps/desktop/web/index.html)** — they were already null-safe in app.js (render fns guard `if(el)`; the 3
in-window fallbacks now bail when the panel is absent). **#settings + #advanced-panel deliberately KEPT in
index.html** — `configSnapshot()` reads ~40 of their live control values **every turn** and module-load
listeners hard-ref them; they can only leave once config moves off the DOM (Phase-6 config-state refactor →
folds 0C fully). settings/advanced are duplicated in both files until then (cross-ref comments in each).

**Gates (offline, green).** [stress_ui.py](../services/lk/tests/stress_ui.py) +7 checks (0A drag-zone hidden + deep headers; 0C panel.html
has the 4 panels, index.html doesn't, settings/advanced in both, open_panel→panel.html, null-safe fallbacks);
`node --check` app.js; HTML well-formedness of index.html + panel.html (zero residual-open tags). Full UI
contract stress suite still ALL-PASS. Rust open_panel change = a one-line string swap in an existing `format!`.
**Status.** `[~]` — **LIVE-VERIFY pending** (needs the user's WSLg rebuild): (1) `cargo build --release` clean;
(2) panel ✕ + Clear/new/Save/Archive/Clear-done now click; (3) panel headers still drag on empty area;
(4) main-window inspect shows the 4 panels gone; (5) settings/advanced sidecars (now panel.html) still
round-trip config to a turn via the localStorage CONFIG_KEY sync.
**Edges.** `[D-61] --{executes}--> [N-80 §Q.12 step-1]` · `--{operationalizes}--> [N-67 integrity]` ·
`--{builds-on}--> [D-60]` (sidecar mechanism + build-embed fingerprint) · `--{advances}--> [N-10 canonical UI]`
(declutter) · `--{defers-to}--> [N-80 step-6 / item-13]` (config-state refactor frees settings+advanced → full
0C DRY) · `--{continues-as}--> [N-80 step-2]` (N-75 live correctness: streaming→variant-nav→empty-response→async).

---

## D-60 — Branch map: full-window overlay → side-flanking sidecar window (2026-06-21) — N-75 / N-10
**Problem (user, with screenshot: "The UI is being hogged by some overlay - branch map").** The N-75 minimap
("BRANCH MAP") rendered as an in-window overlay — `.minimap-panel { position:absolute; inset:0; z-index:40 }` —
so opening it covered the **entire** chat (the main UI bled through the semi-transparent backdrop). User wants
it pulled OUT into a separate window: side-flanking, default-closed, opened on button click, outside the main
window.
**Change (reuses the existing sidecar mechanism — same path as Settings/Journal/History panels).**
- **Rust** [main.rs](../apps/desktop/src-tauri/src/main.rs): added `"minimap" => ("panel-minimap",
  "LAWRENCE Branch Map", 360×520)` to `panel_spec` and `"minimap"` to `close_panels` (so it docks beside the
  main window via `sidecar_position` and closes with the rest on dismiss).
- **Capabilities** [default.json](../apps/desktop/src-tauri/capabilities/default.json): added `panel-minimap`
  to the window-permission list (per the Tauri-capabilities rule — a new window label gets no perms otherwise).
- **CSS** [styles.css](../apps/desktop/web/styles.css): `.panel-window .minimap-panel` joins the panel group
  → `position:relative; inset:auto; z-index:auto; height:100vh` (overlay form kept ONLY for the non-Tauri
  static-preview fallback, consistent with the sibling panels).
- **JS** [app.js](../apps/desktop/web/variants/classic/app.js): Map button now `openSidecarPanel("minimap")`
  (falls back to the in-window panel only when Tauri is absent); `openMinimap` resolves the active chat from
  `/chats` (fresh sidecar state); `initPanelMode` renders the map for `PANEL_MODE === "minimap"`; node-clicks
  in the sidecar switch the head server-side then **emit `chat-path-changed`** so the main window reloads the
  feed (main listens via the event bus); added `closeMinimapPanel` mirroring the siblings.
**Tests.** [stress_ui.py](../services/lk/tests/stress_ui.py): +5 checks — Map opens the sidecar (not overlay),
Rust panel_spec/close_panels know `panel-minimap`, capabilities grant it, the panel drops its overlay
z-index/inset in panel mode, and the path-switch syncs the feed via the event bus. **All UI contract checks
PASS.** `node --check` on the variant passes.
**FOLLOW-UP (2026-06-21, user: "No difference visible … resetted, cleaned, rebuild" + "the cross at top right
does not work").** Diagnosed with evidence (binary forensics), not guesses:
1. **ROOT CAUSE of "rebuild shows no change" = Tauri stale-frontend embed.** `tauri_build::build()` only emits
   `cargo:rerun-if-changed` for `tauri.conf.json` + `capabilities` — **never for `web/`**. `generate_context!`
   embeds `../web` via `include_bytes!` of content-hashed files during `main.rs` compile; a web-only edit
   doesn't change `main.rs`'s inputs ⇒ no recompile ⇒ **stale UI ships**. (Proof: decompressed the staged
   brotli assets — the binary's embedded `app.js` matched my NEW file 4/4 chunks ONLY because that build also
   recompiled `main.rs`/capabilities; a web-only rebuild would NOT have.) **Fixed in [build.rs](../apps/desktop/
   src-tauri/build.rs):** walk `../web`, emit `rerun-if-changed` per file, fold a content hash into
   `cargo:rustc-env=LK_WEB_FINGERPRINT`; `main.rs` reads `const _: &str = env!("LK_WEB_FINGERPRINT")` so any web
   change forces a recompile + fresh embed. Added `build.rs` to `desktopctl.sh needs_build`. (build.rs syntax
   verified via standalone `rustc --edition 2021`.)
2. **In-window fallback no longer hogs.** Under WSLg the separate window may not appear (multi-window webview
   limits); the fallback `.minimap-panel` was still a full `inset:0` overlay. Re-styled to a **right-side dock**
   (`right:0; left:auto; width:min(360px,78%)`) so it flanks the chat. Separate sidecar window stays primary
   (correct for the native-Windows target).
3. **The ✕ now works.** A close button inside a `data-tauri-drag-region` header loses its click to window-drag
   under WebKitGTK. Strip the drag-region from the header in overlay mode (kept in the separate-window mode,
   which needs it) + **Esc-to-close** as backup.
stress_ui.py +2 checks (right-dock not inset:0; close robustness). All gates green.
**Status.** `[~]` — **LIVE-VERIFY pending**: rebuild (now guaranteed fresh) + relaunch. Open question for the
user: do Settings/History open as SEPARATE windows or in-window overlays? (tells us if multi-window works under
their WSLg; the dock fallback covers both either way).
**Edges.** `[D-60] --{fixes-overlay-of}--> [N-75 branch map/minimap]` · `--{advances}--> [N-10 canonical UI]`
(declutter — chat no longer hogged) · `--{gated-by}--> [N-67 integrity]` (control preserved, just relocated) ·
`--{reuses}--> [D-? sidecar panels]` (open_panel/sidecar_position) · `--{unblocks}--> [ALL future web edits]`
(stale-embed class of bug eliminated) · `--{continues-as}--> [N-80 UI-FIX-PASS, PLAN §Q.12]` (2026-06-21
testing session backlog: drag-click fix, panel-host extraction, branch-map graph redesign, regenerate-UX,
variant-nav/streaming bugs, sensor tooltips, chat-ops discoverability, launcher CRUD, appearance/window settings).

---

## D-59 — The actual bloat source: warm powershell host kills the per-poll Add-Type storm (2026-06-20) — N-78
**User: "still too many bloat process zombies."** D-52 fixed the notification + window-layout powershell
paths but **missed the highest-frequency one.** Re-audit found it:
- **`vision.py:capture_foreground`** is the **PRIMARY ~10s watch path** ([_tick](../services/lk/obs/vision.py)
  line 521 calls it every poll) and it ran **`Add-Type @"...inline C# class..."@` every single call** — that
  invokes the **C# compiler (`aspnet_compiler.exe`) + assembly self-repair (`msiexec`) on every poll**, the
  worst offender of all. `capture_fullres` and `_powershell_capture` had the same per-call `Add-Type`.
  **D-52 never touched any of these** (it only fixed `regions.screen_windows` window-layout + `notify`).
**Fix — a persistent powershell host** ([obs/winhost.py](../services/lk/obs/winhost.py)). ONE long-lived
`powershell.exe` reads commands from stdin in a loop; the WinForms/GDI assemblies + the P/Invoke class
(`LkN`) + the capture **functions** (`LkScaled`/`LkFullres`/`LkForeground`/`LkWindows`) are `Add-Type`'d
**exactly once** at startup. Each ~10s poll is then just a function call to the already-warm runtime — **one
host process for the whole session instead of one (compiler-spawning) process per poll.** Robustness:
single-flight lock · self-heal (respawn on death, kill+recover on timeout) · degrades to `(False,"")` (callers
fall back) · `atexit` + `VisionObserver.stop()` reap it · **`LK_WINHOST=0`** safety valve restores the legacy
per-call path. Routed: `vision._powershell_capture` / `capture_fullres` / `capture_foreground` +
`regions._powershell_windows`. (notify's balloon stays a bounded short-lived process — D-52 caps it, and it
must own its tray icon ~1s; not worth the host's render risk.)
**Typed test** — [test_winhost.py](../services/lk/tests/test_winhost.py) (in `make check`) with a FAKE
interpreter (offline, OS-independent): **25 commands → exactly 1 process spawned** (`starts==1` — the bloat
fix, proving no per-call spawn); ERR framing keeps the host alive; death (EOF) → respawn; wedged command →
timeout-kill + recover; missing interpreter → degrade. Plus `obs/winhost.py` added to the S1 service-registry
partition (test_services now 49 modules).
**`make check` green (49 suites).** Live-verify: confirm on the Windows host that, with vision on for an hour,
`powershell.exe`/`aspnet_compiler.exe`/`msiexec` counts stay flat (≈1) instead of climbing.
**Edges.** `[D-59] --{completes}--> [N-78 host hygiene]` load-bearing · `--{fixes}--> [D-52 missed path]`
load-bearing · `--{feeds}--> [N-61 desktop/host endurance]` significant · `--{uses}--> [D-52 debuglog]`.

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
**D-37→D-38 (warm-restart boundary)** · **D-38 terminal MVP sink** ·
**D-39→N-45,N-55,N-63 (🔴 regressed; N-63 remediates)** · **D-40→N-49** · **D-41→N-49** · **D-42→N-48**.

**Deployment revalidation overlay:** D-28,D-30…D-34,D-36,D-37→N-59 ·
D-29,D-32,**N-63 (gates)**→N-60 · D-28,D-35,D-37,D-40,D-41→N-61 ·
D-38,D-39,D-40,D-41,D-42,N-59,N-60,N-61→N-62.

*D-38 remains the historical MVP implementation sink, but N-62 is now the
deployment-current acceptance sink. D-39/D-40/D-41/D-42 retain their post-MVP
edges and also feed deployment revalidation; no completed node is silently
treated as production-current.*
