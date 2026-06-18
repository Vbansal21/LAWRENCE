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
**D-26→N-05 (✓ realized),N-03/N-04 (folded as categories),N-06 (recall now a cited category),N-07 (findings ride notes+doc+web),N-32 (latency lever),N-12/N-16 (consume the engine later)**.

*(No D-node is a sink with zero outflow — every done item has a live follow-up, as
expected mid-stream. N-09/N-19/N-24/N-25/N-26/N-29/N-30 are genuinely independent of
the tracked done-graph; N-09/N-26 lean on existing **app.js / host scaffolding** that
predates this tracker and is not itself a D-node — see PLAN.md §H audit F1.)*
