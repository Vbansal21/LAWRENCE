# Autonomy Scorecard & Roadmap

> Living doc. The question it answers: **what separates LAWRENCE from a fancy
> chat interface with sensors bolted on, and how far across that gap are we?**
> Separate from `IMPLEMENTATION_PLAN.md` (task-level) and `AUDIT.md` (is-it-real).
> This is the *conceptual* tracker **and** the granular, testable execution plan
> that multiple models/people work from. North star, litmus, gap, then the plan.
>
> Last updated: 2026-06-14.

---

## 0. North star

A local-first assistant that **perceives continuously, remembers durably, decides
on its own when to act, and acts** — one LLM *augmented* by orchestration into
something JARVIS/FRIDAY-shaped. The orchestration is the product; the model is a
swappable organ. The user should be able to **just reach for it** — ask, or get an
artifact (file/code/explainer/notebook) — without manually feeding it everything,
while it quietly contemplates what they're *missing*.

## 1. The litmus: reactive chat vs. autonomous agent

A chat interface — even one wired to a screen and a microphone — is **reactive**:
nothing happens until the user prompts it. Autonomy is the set of properties that
let the system *originate* behaviour. Eight of them:

| # | Property | Reactive chat | Autonomous agent |
|---|----------|---------------|------------------|
| P1 | **Perception** | attaches a screenshot when asked | always watching, distilling unprompted |
| P2 | **Cognitive tick** | acts only on input | a heartbeat runs even with no user & no event |
| P3 | **Self-triggering** | user must ask | decides *itself* when something matters |
| P4 | **Calibration** | every event = a ping (noise) | graded: ignore / note / study, on a learned threshold |
| P5 | **Durable memory** | a context window | accreting, compressing, *addressable* memory across sessions |
| P6 | **Temporal agency** | no sense of time | schedules, reminds, follows up, fires on its own |
| P7 | **Self-directed reasoning** | answers the question asked | studies what it judges important, unasked; emits artifacts |
| P8 | **Effectors / agency** | emits text | *does things* — tools, actions, artifacts |

**The one-line test:** *unplug the user for an hour — does the system do anything
useful?* Today: almost nothing. That is the gap.

---

## 1b. The Protagonist Principle — the model is replaceable

The LLM is the **protagonist** (the actor that reasons), but it must also be the
**most easily swapped and least trusted** part. The orchestration — perception,
memory, the tick, scheduling, effectors — is the durable system; the model is an
organ you can transplant (local llama.cpp ↔ Gemini ↔ Claude ↔ next year's model)
without rewiring anything around it. Two obligations follow:

- **Swappable.** All inference goes through one role-tagged seam: `call_model(role,
  schema, priority)` (`kernel/invoke.py`). Provider logic lives only in `model.py`
  (invariant I3); per-role thread-local routing + named providers + presets make
  "a different brain for extraction vs. answering" config, not code. **✅ asset.**
- **Robust *around* it (don't trust the organ).** Stay useful when the model is
  slow, down, weak, or returns garbage. Already: schema decoding degrades
  `json_schema → json_object+schema → plain`; malformed output counted/handled
  (`note_fallback_parse`); local fallback on a healthy server; token cap bounds CPU
  runaways; priority gate serialises the single local slot. **✅ keep as a hard rule.**

**Constraint on every task below:** each cognitive policy must (a) call the model
**only** through the role seam with a lean schema, and (b) have a **degraded path**
for when the model is absent/slow/weak — perception & memory still capture, the
tick still ticks, scheduled intents still fire; only the *reasoning* defers, never
the *system*. Autonomy must not make LAWRENCE depend on one particular brain.

---

## 2. Where we are (honest scorecard)

Legend: ✅ solid · 🟡 partial / naive · ⛔ missing · evidence in `code:line`.

### Substrate — strong
- ✅ **Replaceable protagonist (§1b).** One role-tagged seam, provider logic in
  `model.py`, schema/parse/fallback resilience. A real asset to *protect*.
- ✅ **Durable memory (P5, core).** L1/L2/L3 rolling store + model compaction
  cascade, dynamic budget, daily event log, MDX journal. `ctx/store.py`, `admin.py`.
- ✅ **Reactive turn.** analysis → retrieval → response, streaming, schema JSON.
- ✅ **Perception capture (P1, half).** Vision foreground OCR + audio parec/whisper
  observers run continuously. `obs/vision.py`, `obs/audio.py`.
- ✅ **Control plane.** Launcher (GUI+TUI), presets, secrets, memory mgmt,
  lifecycle mutex + force-reset, rebuild. *Operational, not cognitive, autonomy.*

### Cognitive spine — mostly missing
- ⛔ **Cognitive tick (P2).** No heartbeat. With no user and no sensor spike, the
  system is inert. *Missing spine — everything else hangs off it.*
- 🟡 **Self-triggering (P3).** One reflex, **event-driven only**
  (`ui_bridge.py:349 _maybe_proactive`, throttled 600s `:153`); never self-initiated.
- ✅ **Perception → memory (P1).** Done (B1): a droppable, context-free
  `call_model(role="extract")` distils each sensor slice to a clean entry before
  it enters memory, grades significance (incl. *what the user's missing*), and
  buffers it for the tick. Funnels through the store's single `append()`
  chokepoint (`ctx/extract.py`); degraded-safe (model down → raw kept).
- ⛔ **Calibration (P4).** Proactive trigger is **binary**, not graded; no mean±σ.
- ⛔ **Temporal agency (P6).** **No scheduler/reminder backend at all**; journaling
  only on `/exit`. Cannot remind, defer, or act at a time.
- ⛔ **Self-directed reasoning + artifacts (P7).** Deep-study unbuilt; `context_pack`
  endpoint **dead** (`ui_bridge.py:905`, 0 UI calls). Never studies/produces unasked.
- ⛔ **Effectors / agency (P8).** Output is chat + a notification. It can *say*, not *do*.

### Memory shape — the new gaps you flagged
- ✅ **Abstracted tiers.** Done (M1): `ctx/store.py` is driven by a `Layer`
  list + `DEFAULT_LAYERS`; `memory.layers` in `lk.json` picks any N levels with
  per-level budget/ratio/cap/header/promote-target. Default reproduces the old
  3-tier behaviour (golden regression in `tests/test_memory_tiers.py`).
- ✅ **Per-tier compaction policy.** Done (M2): the store passes the source
  `Layer` to `compact_fn`; `run_compaction` routes on `layer.compact_role` and
  sizes to `compact_target_tokens` — a deep tier can compact on a different/
  cheaper/longer-context model purely via routing config (`compact-l1/-l2/-l3`
  roles added). Degraded path: model fails → layer still trims (tested).
- ✅ **Atomic zettelkasten log.** Done (M3): `ctx/notes.py` `NoteStore` writes one
  append-only, addressable Markdown note per significant event (id + frontmatter +
  tags + `[[id]]` links + derived backlinks + `index.jsonl`); keyword search; an
  optional `index_fn` feeds bodies to the retrieval FTS. B1 mints a note above a
  significance floor. `lk notes list|show|search`; `memops` counts them and spares
  them from `clear-all`. Distinct from rolling (compressing) and journal (narrative).
- ⛔ **Artifact generation.** No code/file/explainer/**Jupyter-notebook** output;
  only the journal + a dead context-pack. (→ WS-A.)

**Verdict:** LAWRENCE today is **instrumented, well-remembered chat with one
reflex**. Substrate ≈ 80%; cognitive spine ≈ 15%; memory is solid but *rigid*;
artifacts ≈ 0. The control-plane work makes it *operable*, not yet *autonomous*.

---

## 3. Execution plan (granular, testable, multi-contributor)

Read **§4 Contributor protocol first** — it defines Definition-of-Done, the
invariants every task must hold, and how to self-verify. Each task is sized to be
picked up independently. **Dependencies are explicit; respect them.** Status keys:
`[ ]` open · `[~]` in progress · `[x]` done. Keep the worklog (§6) updated.

Keystone ordering: **WS-P (perception→memory) feeds WS-M (memory shape) and the
WS-C tick; the tick drives WS-T and WS-A.** Build the spine, then hang organs.

### WS-M — Memory: abstracted tiers, per-tier policy, zettelkasten

> Goal: memory becomes **configurable, policy-driven, and addressable** without
> breaking the current 3-tier default. The default config must reproduce today's
> behaviour byte-for-byte-ish (regression-tested).

**M1 — Abstract the rolling store to N configurable layers**  `[x]`
- Depends on: nothing. Outcome: `ctx/store.py` driven by a `layers` list, not
  hardcoded `_l1/_l2/_l3`.
- Steps:
  1. Define a `Layer` dataclass: `name, file, char_budget, compact_ratio,
     summary_cap, compact_role, promote_to (next name | None=drop), header`.
  2. Build `self.layers: list[Layer]` from config `memory.layers` in `lk.json`
     (via `config.py`), falling back to a **DEFAULT_LAYERS** constant that encodes
     today's L1(raw)/L2(10k)/L3(4k,drop) exactly.
  3. Replace `append`, `_trigger_compact`, `_compact_l1/_compact_l2`,
     `tail_for_model`, `clear_*`, `show_layer`, `_layer_file`, `export` with
     generic loops over `self.layers` (cascade: when layer i > budget, compact
     oldest `compact_ratio` into one entry appended to `promote_to`; cascade up).
  4. Bottom layer = raw events; top layer with `promote_to=None` = archive-drop.
  5. Keep the dynamic working-budget logic; `tail_for_model` walks layers
     top(summaries)→bottom(raw) with each layer's `header`.
- Tests (add to `tests/test_offline.py` + a new `tests/test_memory_tiers.py`):
  - Default config produces the same layer files/sizes/headers as the pre-refactor
    store for a fixed event sequence (golden test).
  - A 5-layer config cascades correctly (inject N events → assert each layer
    obeys its budget and promotion). A 1-layer config never promotes.
  - `make check` stays green.
- Self-check / alignment: **the default-config regression test is the contract** —
  if it changes behaviour, you broke it. Respect I1 (single writer) — all mutation
  under `self._lock`. No provider logic here (I3).

**M2 — Per-tier compaction policy (length / cleaned focus / delegated model)**  `[x]`
- Depends on: M1, and the role seam (§1b). Outcome: each layer compacts with its
  own budget, prompt focus, and **model role** (so deep layers can use a
  stronger/cheaper/longer-context model via routing).
- Steps:
  1. Extend `compact_fn` to `compact_fn(text, layer: Layer)` and thread `Layer`
     through `_compact_l*`. The kernel's `run_compaction` (in `kernel/`) maps
     `layer.compact_role` → `call_model(role=layer.compact_role, schema=…,
     max_tokens=layer.compact_target_tokens)`.
  2. Add roles `compact-l1`, `compact-l2`, … to `config.BACKGROUND_ROLES` +
     `ALL_ROLES` so they're routable/presettable. Default route = same as `compact`.
  3. Compaction prompt receives **only the cleaned slice** (already true) and a
     per-level target length; deeper levels → terser, longer model budget allowed.
  4. "Number of levels informs target length": derive each layer's target from its
     depth/budget so a 6-level config self-scales summary lengths.
- Tests: per-layer role resolves through routing (mock `call_model`, assert the
  role passed); target length honoured (summary ≤ cap). Degraded path: model
  returns "" → layer still trims (no unbounded growth) — assert.
- Self-check: **never leave a layer unbounded** even on model failure (current
  invariant). Verify the degraded path test passes with the model stubbed to fail.

**M3 — Zettelkasten: atomic, addressable notes per significant event**  `[x]`
- Depends on: WS-P/B1 (extraction emits the "significant event" + clean text).
  Outcome: each significant event becomes an **atomic note** — own id, frontmatter,
  tags, links — distinct from rolling (compressing), journal (narrative), and the
  daily stream log.
- Steps:
  1. New module `ctx/notes.py`: `write_note(kind, text, source, tags, links) ->
     note_id`. File `memory/notes/<YYYYMMDD-HHMMSS-slug>.md` with YAML frontmatter
     (`id, ts, kind, tags, links, source`) + body.
  2. Maintain `memory/notes/index.jsonl` (append id+meta) and **backlinks**: when a
     note links `[[other-id]]`, record the reverse edge in the index.
  3. Wire the extraction layer (B1) to call `write_note` for events above the
     significance floor; link a note to the rolling entry / journal day it informed.
  4. Make notes **retrievable**: index note bodies into the existing FTS5
     (`retrieval/db.py`) so queries and proactive realize can surface them.
  5. CLI/GUI parity: `lk notes [list|show <id>|search <q>]`; a Notes view later.
  6. `memops.py`: add a `notes` category (back up; clear is opt-in, never in
     `clear-all` by default — atomic notes are user-valuable like the vault).
- Tests (`tests/test_notes.py`): write→read round-trip; `[[link]]` creates a
  backlink both directions; a note is found via FTS search; `memops.stats()` counts
  notes; `clear-all` does **not** delete notes.
- Self-check: notes are **append-only and addressable** — never rewrite an existing
  id. Keep the three memory kinds distinct (don't fold notes into rolling/journal).

### WS-P — Perception → clean memory  (feeds WS-M & the tick)

**B1 — Extraction layer (V3.T3)**  `[x]`
- Depends on: nothing (uses the role seam). Outcome: on large info-gain in a sensor
  slice, **one cheap routed `call_model(role="extract")`** with **no rolling
  context** distils it to a clean entry → `append()` + `write_note()` (M3). Ends
  per-chunk turns.
- Steps: add `ctx/extract.py` `extract(slice) -> {clean, significance, tags}`
  (lean schema `kernel/schemas.py`); gate via `ctx/gate.py` info-gain; call from the
  observer/spool path, not the turn path; priority = lowest (droppable).
- Tests: high-gain slice → one extract call + one clean entry; low-gain → none
  (assert no call); model down → raw slice still logged (degraded path).
- Self-check: extraction must **not** carry rolling context (I: clean focus) and
  must be droppable under the priority gate (never blocks a user turn).

**B2 — Audio → context (V3.T4)**  `[ ]`  · Depends on: B1.
- Accumulate utterances; model-classify intent (+ wake word + PTT); feed the
  extractor, **not** a turn per chunk (kills the "tiny wrong chunk → model call"
  bug). Tests: chunk stream → 0 turns, 1 extract on a complete utterance; wake word
  routes to a turn; degraded path → transcript still logged.

**B3 — No stale-image attach (V3.T7)**  `[ ]`  · Depends on: nothing.
- Never auto-attach a screenshot older than N seconds to a turn. Test: stale image
  is dropped; fresh image attaches.

### WS-C — The cognitive tick (THE SPINE)

**C1 — Heartbeat loop**  `[x]`  · Depends on: B1 (something to consume).
- Outcome: one daemon tick (`kernel/tick.py` `CognitiveTick`, adaptive cadence) that,
  each beat, with **no user**: fires due intents (WS-T hook, no model) → drains the
  extractor → on an idle beat makes ZERO model calls and backs the cadence off
  (running an idle reflection hook every `idle_every` empty beats, C3 hook) → on an
  active beat takes **at most one** droppable action via `act_fn` on the most
  significant event ≥ `LK_TICK_FLOOR`. All collaborators injected; `enabled()`=`LK_TICK`.
  Started + stopped by the bridge and the REPL; `act_fn` drives the already-throttled,
  priority-gated `run_proactive` pathway so it yields to turns and never blocks one.
- Tests (`tests/test_tick.py`, all green): idle beat → 0 model calls + back-off;
  high-significance → exactly one action on the top event + cadence snap-back;
  sub-floor → no action; **degraded path** — a raising `act_fn`/`drain_fn` is
  swallowed (self-heals next beat); due intents fire without a model; idle hook
  cadence; `LK_TICK=0` disables every beat; clean `start()/stop()`.
- Self-check: the tick is **interruptible and idempotent** per beat (`beat()` is
  public + side-effect-bounded); a missed/failed beat self-heals next beat; the tick
  never holds the writer lock (I1) — all writes go through `ctx`/`run_proactive`.

**C2 — Graded significance (V3.T5)**  `[x]`  · Depends on: C1.
- The model already scores significance (grammar-enforced JSON) *including the
  gap-reasoning* — B1's `EXTRACT` prompt asks "what the user may be **missing**".
  C2 turns that scalar into an **action tier** via a running mean±k·σ band
  (`ctx/significance.py` `Grader`, Welford, O(1)): `< note floor / sub-mean` →
  **LOG** (clean entry only); `note floor … mean+kσ` → **NOTE** (mint M3 note);
  `> mean+kσ` → **STUDY** (the tick surfaces). Wired: `Extractor` grades each
  slice, attaches `tier`, and mints a note on `tier ≥ NOTE`; the tick surfaces on
  `tier ≥ STUDY` (`LK_TICK_ACT_TIER`), falling back to the significance floor for
  ungraded events. Thresholds config-driven in `lk.json`→env (`LK_SIG_WARMUP`,
  `LK_SIG_K`, `LK_NOTE_FLOOR`, `LK_SIG_ACT_FLOOR`) with conservative defaults.
- Tests (`tests/test_significance.py`, green): three synthetic events land in the
  three tiers; tier→action map is total; thresholds config-driven; running mean/σ
  updates; **degraded path** — None/garbage score → LOG; conservative — adaptive
  thresholds clamp to ≥ the floors so a calm stream can't lower the bar (no spam);
  Extractor gates notes on the tier. Plus a C1↔C2 seam test in `test_tick.py`.
- Self-check: **conservative by default** — during warm-up and whenever unsure the
  band defers to fixed floors and the tick stays quiet; pure math = always-available
  degraded path (no model dependency in the grader itself).

**C3 — Periodic reflection / journaling**  `[ ]`  · Depends on: C1.
- Journaling + threshold recalibration become tick policies (idle/daily), not just
  `/exit`. Test: an idle-day tick writes/extends the journal once (not per beat).

### WS-T — Temporal agency & goals

**D1 — Scheduler + reminders backend**  `[ ]`  · Depends on: C1.
- Real store (`memory/schedule.jsonl` or SQLite) + the tick fires due items
  (desktop notify + SSE surface). **Wire or replace** the hollow `localStorage`
  reminders panel to this. Goal/intent persistence that resurfaces on its own.
  CLI/GUI/TUI parity: `lk remind add "…" --at …`, `lk remind list`.
- Tests (`tests/test_schedule.py`): add→due→fires once (not repeatedly); persists
  across restart; past-due on startup fires once; timezone correct.
- Self-check: an intent fires **exactly once** unless recurring; survive restart
  (durable). No double-fire under the tick.

**D2 — Deferred refinement (the "slow loop")**  `[ ]`  · Depends on: C1, D1.
- Low-priority follow-ups the tick picks up when idle. Test: a deferred item is
  processed only while idle and is dropped/raised correctly under load.

### WS-A — Artifacts (the "just reach for it" surface)

> Goal: the user (or the model, when it spots a gap) can produce a **file / code /
> explainer / Jupyter notebook (plots + equations) / deep-study** with strict
> citations, without manually assembling context.

**A1 — Artifact engine core**  `[ ]`  · Depends on: §1b seam; retrieval.
- New `artifacts/engine.py`: `make(spec) -> path` where `spec = {kind, prompt,
  sources?, dest?}`. Pulls dense retrieval + relevant notes (M3) as grounding,
  calls `call_model(role="study", schema=…)`, writes to `memory/vault/<slug>/`.
  Strict citations + a provenance footer (sources, model, ts).
- Tests (`tests/test_artifacts.py`): `kind=md` produces a file with a citations
  block; sources are real (no fabricated refs in the fixture). Degraded path: model
  down → returns a clear error, writes nothing partial.
- Self-check: **never** emit an artifact with fabricated citations; every claim ties
  to a retrieved source or is marked unsourced.

**A2 — Code / file artifacts**  `[ ]`  · Depends on: A1.
- `kind=code` (lang-aware, runnable file) and `kind=mdx`. Test: code artifact
  parses (py_compile for python) / lints; mdx has valid shape (`_has_mdx_shape`).

**A3 — Jupyter notebook artifacts (plots + equations)**  `[ ]`  · Depends on: A1.
- `kind=notebook`: build a real `.ipynb` (nbformat JSON — markdown cells with LaTeX
  `$$…$$`, code cells using matplotlib). Optionally execute headless to embed
  outputs (degraded: skip execution if jupyter absent — write an unexecuted nb).
- Tests: emitted `.ipynb` is valid JSON + nbformat-loadable; has ≥1 markdown(eq)
  and ≥1 code(plot) cell; executes if `nbconvert` present, else still valid.
- Self-check: notebook must open in Jupyter (validate nbformat). No execution = OK,
  but the file must still be valid and labelled "not executed".

**A4 — Deep-study export (V3.T8) folds context-pack**  `[ ]`  · Depends on: A1, M3.
- "Context of context": dense retrieval + where-to-study pointers → MD/MDX in
  `memory/vault/`. Replace the dead `context_pack` path. Explicit command/button
  **and** model-proposes-when-deep (via C2). Test: produces an MD with pointers +
  citations; the old `/context-pack` route is removed or redirected.

**A5 — Model-proposes-artifact (gap contemplation)**  `[ ]`  · Depends on: C2, A1.
- When C2's gap-reasoning judges the user is missing something an artifact would
  solve, the tick surfaces a **proposal** ("want a notebook deriving X?") via SSE —
  one tap to generate. Test: a high-gap fixture yields a proposal event; accepting
  it calls the engine; declining logs and doesn't nag.
- Self-check: proposals are **rate-limited and dismissible** — contemplation, not
  pestering. Honour the conservative default.

**A-UI / A-CLI parity:** every artifact kind reachable as `lk make <kind> "<prompt>"`
**and** a GUI/popup button **and** TUI entry. (Cross-cutting invariant.)

### WS-X — Effectors / true agency  🔭 (raises ceiling to "JARVIS")
**F1 — Guarded tool/action layer**  `[ ]` — schema-constrained, permissioned,
logged effectors so it can *do* (open/run/write/fetch/notify), not only speak.
*Largest new surface — design doc + threat model before any build.*
**F2 — Self-model**  `[ ]` — track proactive hit/miss, auto-tune thresholds (C2),
record uncertainty.

### Phase A — Control plane ✅ DONE (2026-06-14)
Launcher gateway, CLI/GUI/TUI parity, memory management, lifecycle mutex +
force-reset, rebuild. *Makes the system operable and recoverable.*

### Phase G — Polish & ship  `[ ]`
TTS / voice output; local-fallback hardening; the small popup parity cleanup
(ingest/PTT buttons, drop unsupported knobs, reminders decided by D1, README
`crates/` drift); then **commit/push** (handoff in `COMMIT_HANDOFF.md`, now also
needs the launcher/memops/lifecycle/notes/artifacts files added).

---

## 4. Contributor protocol (models **and** people)

Multiple models and people work this plan. To stay aligned and self-correct:

**Before you start a task**
1. Read this doc's §1b (protagonist) + the task's **Depends on** — don't start a
   task whose dependencies are `[ ]`.
2. Read the **invariants** (I1–I9 in `IMPLEMENTATION_PLAN.md`; here, the load-bearing
   ones): **I1** single memory writer (all mutation under the store/`writer.lock`);
   **I3** provider logic only in `model.py`; **I6** never touch `.code-workspace`/
   editor config; plus **§1b** (role seam + degraded path) and **CLI=GUI=TUI parity**.

**While building**
3. Touch the **fewest files**; match surrounding style; keep modules stdlib-light.
4. Every model call goes through `call_model(role, schema, priority)` with a **lean**
   schema and a **degraded path** if the model is absent/slow/weak.
5. Add the task's **tests** alongside the code; they must run under `make check`
   (offline, no model/server needed — stub the model).

**Definition of Done (self-verify before marking `[x]`)**
- [ ] `make check` is green (syntax + offline + edge + concurrency + your new test).
- [ ] The **degraded path** test passes (model stubbed to fail → system still safe).
- [ ] **Parity**: the capability is reachable from CLI **and** GUI **and** TUI.
- [ ] No new provider logic outside `model.py`; no writes to `memory/` outside the
      single-writer path; no edits to `.code-workspace`.
- [ ] Updated this doc: flip the task to `[x]`, add a line to §6 worklog with date +
      what changed + any follow-up `[ ]` discovered.

**Self-correction signals (if any are true, stop and fix before proceeding)**
- A test only passes with the model "up" → you lack a degraded path.
- You added an `if provider == …` outside `model.py` → move it (I3).
- Memory tier behaviour changed under the **default** config → you broke the M1
  regression contract.
- A capability exists in the GUI but not the CLI (or vice-versa) → parity debt.

---

## 5. Definition of "autonomous" (acceptance)

We can stop calling it a chat interface when, with **the user idle**:
1. It distils what it sees/hears into clean memory + atomic notes unasked. *(B1/M3)*
2. A tick runs continuously and is cheap when nothing matters. *(C1)*
3. It acts **only** when its own graded judgment says to — signal, not noise. *(C2)*
4. It reminds / follows up / fires scheduled intents on its own. *(D1)*
5. It produces a studied artifact (md/code/notebook) when warranted — and can
   **propose** one when it spots a gap the user is missing. *(A4/A5)*
6. *(stretch)* It takes a real action through a guarded effector. *(F1)*

**Cross-cutting invariants:** every capability ships in **CLI + GUI + TUI**
simultaneously, behind the single-writer lock and the priority gate, with local
fallback — **and never makes the system depend on one particular model** (§1b).
Autonomy must never cost operability or safety.

---

## 6. Progress log
- **2026-06-14** — Phase A complete (control plane: launcher, parity, memory mgmt,
  lifecycle mutex + force-reset, rebuild). Autonomy doc created, then expanded into
  the granular WS-M/P/C/T/A/X plan with tests, dependencies, and the contributor
  protocol. Confirmed by code read: memory tiers hardcoded to 3 (`ctx/store.py`);
  logs are flat streams (no zettelkasten); artifacts ≈ 0 (context-pack dead).
- **2026-06-14** — **WS-M/M1 + M2 done.** Rewrote `ctx/store.py` as an N-layer
  engine: a `Layer` dataclass + `DEFAULT_LAYERS` (reproduces the old l1/l2/l3
  byte-for-byte-ish) + config-driven `memory.layers` (`config.memory_layers()`),
  with a generic compaction cascade and legacy shims (`_l1/_l2/_l3`,
  `_l1_size…`, `l2_budget/l3_budget`) so `/set`, status and existing tests keep
  working. M2: the store passes the source `Layer` to `compact_fn`; `run_compaction`
  routes on `layer.compact_role` + `compact_target_tokens` (added `compact-l1/-l2/
  -l3` roles to `config`). New `tests/test_memory_tiers.py` (golden default,
  5-layer cascade obeys budgets, 1-layer never promotes, degraded path, malformed→
  default, M2 role passthrough) wired into `check.sh` + Makefile; **`make check`
  green**. Robustness fix: an archive layer never drops its *last* entry to a
  mis-small budget. Follow-up `[ ]`: a `lk`/GUI surface to view/edit the tier
  config (today it's lk.json-only); `/mem show|clear <name>` already generic.
- **2026-06-14** — **WS-P/B1 done (the keystone).** New `ctx/extract.py`
  `Extractor` (info-gain gate via `ctx/gate.extract_gate` + injected kernel call +
  a bounded buffer the tick will `drain()`); kernel `run_extract` (lean `EXTRACT`
  schema/prompt, **droppable** PRI_PROACTIVE, **no rolling context**); wired into
  `ContextStore.append` for sensor kinds only (never turns), **outside the lock**,
  injected once at each store site (cli + bridge). Config toggle `extract`
  (`LK_EXTRACT`, default on). Degraded path: model down/skip → raw slice kept.
  New `tests/test_extract.py` (high-gain→1 call+clean, near-dup→0 calls, model-
  down→raw, turns never extracted, disable flag, B1→M3 note bridge) wired in.
- **2026-06-14** — **WS-M/M3 done — the memory-shape trio (M1+M2+M3) is complete.**
  New `ctx/notes.py` `NoteStore`: atomic append-only Markdown notes (id + YAML
  frontmatter + tags + `[[id]]` links + derived backlinks), `index.jsonl` as the
  metadata source of truth, offline keyword `search`, and an injected `index_fn`
  that best-effort feeds note bodies to the retrieval FTS (`db.upsert("note://…")`).
  B1's `Extractor` mints a note when significance ≥ `LK_NOTE_FLOOR` (0.6). Parity:
  `lk notes list|show <id>|search <q>` (front-door), launcher TUI entry, help text;
  `memops` gains a `notes` category — counted + backed up but **never** in
  `clear-all` (opt-in `clear-notes` only), like the vault. New `tests/test_notes.py`
  (round-trip, bidirectional links, search, FTS hook, append-only ids, memops
  spares notes from clear-all) wired into `check.sh` + Makefile; **`make check`
  green** (18 import modules). Follow-ups `[ ]`: REPL `/notes` + a GUI Notes view
  (front-door `lk notes` already reachable from the launcher). **Next: WS-C/C1 —
  the cognitive tick** (the spine; consumes `Extractor.drain()` + due intents).
- **2026-06-14** — **Planning pass for WS-R (reasoning loops) + WS-U (UI).** Read
  the concept docs (AGENT_HANDOFF §"fast loop / slow loop", PLAN_COVERAGE §"Slow
  Loop Ambition", README §"Raycast-style"). Confirmed the loops are **greenfield**
  in `services/lk/` (no `run_fast/run_slow/refine/elevate`). Added §7 (WS-R), §8
  (WS-U), §9 (master checklist) below with conceptual + pseudo-code tests so a
  post-compact session can build straight from them. No code yet this turn.
- **2026-06-14** — **WS-C/C1 the cognitive tick (THE SPINE) — done, `make check`
  green (9 suites, 19 import modules).** New `kernel/tick.py` `CognitiveTick`
  (daemon thread; injected `drain_fn`/`act_fn`/`due_fn`/`fire_fn`/`idle_fn`;
  adaptive cadence `interval→max_interval`; idle beats make ZERO model calls; one
  droppable action/beat ≥ `LK_TICK_FLOOR` on the most significant event;
  `enabled()`=`LK_TICK`). Exported via `kernel/__init__` (`CognitiveTick`,
  `tick_enabled`). Wired start/stop into **both** kernels: REPL (`cli.py`, bound
  `extractor`, `act_fn`→`on_proactive("tick", …)`, stop in `finally`) and bridge
  (`ui_bridge.py`, `self.extractor`/`self.tick`, `act_fn`→`_maybe_proactive`, stop
  in `main()` finally) — `act_fn` reuses each kernel's existing throttled +
  priority-gated proactive path, so the tick yields to turns and never double-fires.
  Renamed the stop Event `_stop`→`_stop_evt` (collided with `Thread._stop()`). New
  `tests/test_tick.py` (idle=0 calls + back-off; high-sig=1 action on top event +
  snap-back; sub-floor=0; raising act/drain swallowed; due intents fire; idle-hook
  cadence; `LK_TICK=0` off; clean start/stop) wired into `check.sh` + Makefile +
  `lk.kernel.tick` in test-fast. Follow-ups `[ ]`: C2 graded significance feeds the
  floor; C3 wire `idle_fn` to a real reflection/journal pass; WS-T `due_fn`/`fire_fn`
  once the scheduler exists. **Next: C2 graded significance → WS-R (R1/R2).**
- **2026-06-14** — **WS-C/C2 graded significance — done, `make check` green (10
  suites, 20 import modules).** New `ctx/significance.py` `Grader`: a running
  mean±k·σ band (Welford, O(1), zero history) maps the model's 0..1 score to an
  action tier LOG/NOTE/STUDY. Pure deterministic math → it *is* the degraded path
  for the significance policy (no model dependency). Wired: `Extractor` now grades
  every slice, attaches `tier`, and mints an M3 note on `tier ≥ NOTE` (replacing the
  flat `_note_floor`, now removed); the tick surfaces on `tier ≥ STUDY`
  (`LK_TICK_ACT_TIER`, default 2) and still falls back to the significance floor for
  ungraded events (keeps `test_tick.py` synthetic events valid). Conservative:
  cold-start (< `LK_SIG_WARMUP`) and adaptive thresholds both clamp to ≥ the fixed
  floors, so a calm stream can't lower the bar and spam. All knobs config-driven via
  `_ENV_MAP` (`tick`/`tick_floor`/`tick_act_tier`/`note_floor`/`sig_warmup`/`sig_k`/
  `sig_act_floor`) → GUI==CLI parity. New `tests/test_significance.py` + a C1↔C2
  seam test in `test_tick.py`, both wired into `check.sh`/Makefile;
  `lk.ctx.significance` in test-fast. Follow-ups `[ ]`: C3 wire `idle_fn` to a real
  reflection pass; surface the tiers in the GUI settings surface (U2b). **Next:
  WS-R — R1 fast/slow split → R2 elevation gate.**
- **2026-06-14** — **WS-R/R1 slow loop + R2 elevation gate — done, `make check`
  green (12 suites, 22 import modules).** R1 `kernel/refine.py`: `run_refine`
  (critique-then-rewrite on the new `refine` role + `REFINE` schema/prompt, depth 1,
  `PRI_REFINE`=1 — non-droppable, below a turn, added between TURN and COMPACT in
  `model.py`) returns `{refined, better, critique, confidence, delta}`; a `better`
  verdict with no text is coerced false; all failures → None (fast answer stands).
  `dispatch_refine` runs it in a daemon thread (fast never blocked), gated by
  `LK_SLOW_LOOP` (**default off ⇒ identical to today** — edge-suite regression), and
  only calls `on_refine` when the verdict clears R2. R2 `kernel/elevate.py`
  `Elevator`: one shared, thread-safe gate for BOTH refinements and tick findings —
  `better` & `Δconf≥LK_ELEVATE_DELTA` (0.15) & novel (per-turn fingerprint dedup,
  idempotent) & ≤`LK_ELEVATE_MAX_PER_MIN` (3, rolling minute via injectable clock).
  Wired: `run_turn` gains `on_refine`/`elevator` kwargs (lazy import → no
  refine↔invoke cycle); REPL surfaces via the live feed; bridge adds
  `_on_refine` + `ui.push_refined` SSE (`type:"refined"`, same turn-id → replace in
  place) + a shared `self.elevator`. Knobs in `_ENV_MAP`
  (`slow_loop`/`elevate_delta`/`elevate_max_per_min`); `refine` added to
  `BACKGROUND_ROLES` (routable to a stronger brain). New `tests/test_refine.py` +
  `tests/test_elevate.py` wired into `check.sh`/Makefile; `lk.kernel.refine`,
  `lk.kernel.elevate` in test-fast. Follow-ups `[ ]`: route the audio-turn path
  through `on_refine` too; render the refined event + finding cards in the UI (U4);
  optionally route `run_proactive` findings through the same `Elevator`. **Next:
  WS-U — Raycast UI refinement (U1 geometry → U2 non-intervening config surface →
  U3 de-bloat app.js), then U4 elevation rendering.** R3 realtime stays deferred.
- **2026-06-14** — **WS-U/U4 (partial) — render the R1 refinement in the GUI.** So
  the new `push_refined` SSE contract isn't dead: `app.js` gains `onRefined` (wired
  into the SSE dispatch next to `finding`/`response`) — it replaces the most recent
  settled assistant answer in place, badges it `refined ↑` + the critique, and tags
  the article `.message.refined` (subtle green left-border in `styles.css`).
  `node --check` green; full gate green (12 suites). Remaining U4: target by turn-id
  (not "last assistant") once U1/U3 land. The big WS-U pieces (U1 Tauri geometry,
  U2 config-surface migration, U3 app.js de-bloat) are next and want interactive
  visual iteration — best done with the desktop app running.

---

## 7. WS-R — Reasoning loops & elevation (fast / slow / surface)

> Intent (AGENT_HANDOFF): **fast loop = immediate usefulness; slow loop refines on
> the same turn later.** Cognition split: *alter-ego* = internal critique/refine,
> *main ego* = the surfaced answer (NOT a visible two-persona product). The
> **elevation mechanism** is the gate + channel by which slow/background output
> earns its way into the foreground — used by BOTH the per-turn slow refine AND
> the always-on tick (C1). Per §1b: every facet goes through the role seam and has
> a degraded path (slow fails → fast answer stands). Build on C1; respect the
> single local slot (priority gate already serialises it).

**R1 — Fast/slow turn split**  `[x]`  · Depends on: nothing (fast = today's `run_turn`).
> Done: `kernel/refine.py` `run_refine` (role `refine`, `PRI_REFINE`, schema/prompt
> `REFINE`, depth 1) + `dispatch_refine` (daemon thread → elevate → `on_refine`,
> off unless `LK_SLOW_LOOP`). Wired into `run_turn` (`on_refine`/`elevator` kwargs,
> no-op when off) + REPL feed + bridge `push_refined` SSE. `tests/test_refine.py`.
- Outcome: a turn returns the **fast** answer immediately (current path), and —
  behind config `slow_loop:on` — dispatches a **bounded** slow refine that may
  replace it. New `kernel/refine.py::run_refine(user_text, fast_answer, ctx,
  retrieval) -> {refined, better: bool, critique, confidence}` via
  `call_model(role="refine", schema=REFINE)` with MORE context/retrieval + a
  critique prompt. Role `refine` added to `BACKGROUND_ROLES` (routable to a
  stronger model — the alter-ego can be a different brain).
- Steps: (1) `schemas.REFINE` + `prompts.REFINE` (critique-then-rewrite, lean,
  `better` boolean first); (2) `run_refine` lowest non-droppable priority below a
  turn; (3) `run_turn` gains `slow_fn`/`on_refine` hooks — emits fast, then runs
  slow in a thread, then calls `on_refine` only if it elevates (R2); (4) config
  `slow_loop` (`LK_SLOW_LOOP`, default off until stable); bounded refine **depth = 1**
  for v0 (no recursion yet — that's the WS-T/D2 tree).
- Tests (`tests/test_refine.py`, model stubbed): pseudo →
  ```
  fast first:   run_turn(stub_fast, stub_slow) → fast surfaced before slow returns
  better→elevate: stub_slow{better:true,conf:0.9} → on_refine called once w/ refined
  not-better:   stub_slow{better:false}          → on_refine NOT called (fast stands)
  degraded:     stub_slow raises/empty           → fast stands, failure logged, no crash
  bounded:      refine depth never exceeds cfg.max_depth (==1)
  ```
- Self-check: the slow loop must **never block** the fast answer or a new turn;
  `slow_loop:off` ⇒ behaviour identical to today (regression).

**R2 — Elevation gate + surfacing channel**  `[x]`  · Depends on: R1; C1 (shared channel).
> Done: `kernel/elevate.py` `Elevator.elevate(item, *, turn_id, prior, emit)` —
> one gate for both refinements and findings: `better` & `Δconf≥LK_ELEVATE_DELTA`
> & novel (per-turn dedup) & ≤`LK_ELEVATE_MAX_PER_MIN` (rolling minute). Shared
> instance on the bridge + REPL; `ui.push_refined` SSE channel. `tests/test_elevate.py`.
- Outcome: ONE elevation path that both R1 (refined answer) and C1/run_proactive
  (findings) use to push into the live conversation. A refinement/finding is
  elevated only when it clears a bar: `better==true` AND `Δconfidence ≥ cfg.elevate_delta`
  (default 0.15) AND not a near-duplicate of what's already shown. Surfacing reuses
  the SSE connector (`ui.push_response(..., refined=True)` / `push_context_event`)
  so the UI updates the SAME turn in place (no new prompt). Rate-limited & dismissible
  (Protagonist Principle: contemplation, not pestering).
- Tests (`tests/test_elevate.py`): pseudo →
  ```
  gate passes: better & Δconf≥delta & novel  → elevate() emits one refined event
  gate blocks: Δconf<delta OR duplicate       → no event
  rate limit:  N elevations in window         → only ≤cfg.max_per_min surface
  shared path: a tick finding & a slow refine both route through elevate()
  ```
- Self-check: conservative default; an elevation is **idempotent** per turn-id
  (never double-surfaces the same refinement). No provider logic here (I3).

**R3 — Continuous realtime response while loops run**  `[ ]` 🔭 (**deferrable** — user OK'd)
- Outcome: the user can send turn B while turn A's slow loop runs; B's fast preempts
  (priority gate already does this), A's slow either completes and elevates against
  A's turn-id or is cancelled cleanly if stale (context-version guard, an existing
  invariant). The UI shows per-turn live status and streams partial tokens.
- Tests (pseudo): `B preempts A's slow (gate order turn>refine)`; `A's stale slow is
  dropped, not surfaced against B`; `two turns keep distinct turn-ids in the feed`.
- Self-check: **stale-result guard** — never surface A's refinement after the
  context moved on. Defer until R1+R2+C1 are stable.

## 8. WS-U — UI refinement (the Raycast surface)  `[ ]`

> Intent (README + memory `lawrence-desktop-ops`/`lawrence-target-architecture`):
> a **Tauri-native floating overlay** (NOT a web app), **Raycast-style** — one input
> bar that opens, transcript fade, minimal chrome, hotkey summon/dismiss. Current
> frontend is functionally complete but **bloated/blocky**: `app.js` 2280 lines, a
> hand-rolled 108-line MDX renderer (`renderMdx`), a ~25-knob sampling panel + many
> config fields crammed **into the main window**, fixed 920×340. The problem is
> *placement*, not the knobs: per the user the config is **needed and must expand** —
> it just has to stop intruding on the bar (see U2). Some knobs (`tool-rounds`,
> citation/web-depth, grammar/schema) aren't wired to the backend yet — **wire them,
> don't delete**. **Keep the Tauri shell + `ui_bridge` data contract (SSE,
> `/turn/async`, job poll) — rewrite presentation only. Don't reinvent: vendor a tiny
> markdown lib instead of hand-rolling.**

**Hard constraints:** native Tauri (no web-app pivot); embedded frontend → rebuild
needed (`lawrence-desktop-ops`); never touch `.code-workspace` (I6); CLI=GUI parity
preserved (every control removed from view stays reachable via overlay/command).

- **U1 — Raycast geometry.** Window collapses to just the input bar when idle
  (~720×64) and **auto-grows to content** (clamp ≤ maxHeight) as the feed fills —
  measure feed height in JS, call Tauri `setSize(LogicalSize)`. Keep centered, no
  decorations, transparent, rounded, subtle border + backdrop blur, always-on-top.
  *Check:* fresh summon shows only the bar; first answer grows the window; dismiss
  on Esc/blur; re-summon restores. (`tauri.conf.json` width/height defaults +
  `main.rs` builder + a JS `autosize()`.)
- **U2 — Config as a separate, NON-INTERVENING surface (keep + EXPAND, don't delete).**
  *User directive (2026-06-14):* the knobs are **needed and must grow to more
  functionality** — the bug is only that they crowd the main window. So: the main
  interface stays a bare bar + feed, and **all** config moves into its own surface
  that **never reflows or covers the input bar** — a dedicated settings overlay
  (Raycast `⌘,`-style), ideally a **separate Tauri window** (`open_settings`) so it
  is independently sized/moved/dismissed and cannot push the bar around. Summon via
  a single "⋯ / ⌘K" command menu; the 4-button tool row + 6-section drawer collapse
  into that menu. **Wire currently-unwired knobs to the backend** (e.g. `tool-rounds`,
  citation/web-depth, grammar/schema) rather than deleting them; if a knob truly has
  no backend, mark it "planned", don't drop it. Organise the surface into searchable
  **categories** (next item). *Check:* idle main view = input bar + status only;
  opening settings does **not** change the main bar's size/position; every existing
  control id still has a home; no knob removed.
- **U2b — Expanded config scope (extrapolated).** The settings surface is the single
  place to reach every tunable, grouped + searchable:
  **Model/Routing** (preset switch · per-role backend routing incl. the new
  `refine`/`compact-l*`/`extract` roles · API keys status) · **Sampling** (the full
  llama.cpp set, each labelled by which backends honour it — API-dropped ones greyed,
  not hidden) · **Memory tiers** (the M1 follow-up: view/edit `memory.layers` — count,
  per-level budget/ratio/cap/role/promote) · **Loops** (`slow_loop`, refine depth,
  `elevate_delta`, `extract` on/off, `LK_NOTE_FLOOR`, C2 significance σ-thresholds,
  proactive interval) · **Retrieval/Web** (depth, citation mode, policy gate) ·
  **Response/Persona** (mode, length, effort, language, persona) · **Surface** (zoom,
  opacity, font, theme) · **Reminders/Tasks** defaults. Each control round-trips to
  `lk config`/`gate_config`/`memory.layers` so **GUI == CLI** (parity invariant).
  *Check:* changing a knob in the GUI is visible via `lk config get …` and vice-versa.
- **U3 — De-bloat `app.js`.** Replace the hand-rolled `renderMdx`/`renderInline`/
  `renderTable` (~150 lines) with a vendored single-file ESM markdown lib
  (`marked` or `markdown-it`, offline-vendored under `web/vendor/`). Keep the data
  layer (`sendTurn`, `postBridge`, SSE, `waitForBridgeJob`). Target: `app.js` ≪ half.
  *Check:* `node --check app.js` green; markdown (headings/lists/code/tables/links)
  still renders; citations + attachments still work.
- **U4 — Elevation rendering.** A refined answer (R2) updates its turn **in place**
  (a subtle "refined" affabox), and a tick/proactive finding appears as a dismissible
  card in the feed — the visible half of the elevation mechanism. *Check:* a
  `response{refined:true}` SSE event replaces the turn's body without a new bubble.
- **U5 — Visual polish.** Raycast aesthetic: one type scale, generous spacing,
  focus ring, mono for code, quiet status pill, theme tokens (the surface-opacity/
  zoom/font controls already exist — wire to CSS vars). *Check:* looks like a
  command palette, not a form.
- Tests: GUI ⇒ mostly **manual acceptance checkpoints** (above) + the existing
  `node --check apps/desktop/web/app.js` in `check.sh`. Add a tiny pure-JS unit
  only if a vendored md lib isn't used (we will use one, so skip).

## 9. Master checklist & checkpoints (path-correction goal-posts)

Tick these in order; each is a **checkpoint** — if a box can't be ticked, stop and
correct before moving on. `[x]` done · `[ ]` open.

**Done (verified `make check` green, 12 suites / 22 modules):**
- [x] M1 N-tier memory · [x] M2 per-tier compaction/role · [x] B1 extraction
  keystone · [x] M3 zettelkasten · [x] C1 cognitive tick (the spine) ·
  [x] C2 graded significance (running mean±σ → action tier) ·
  [x] R1 fast/slow split · [x] R2 elevation gate (shared by R1 + C1 findings).

**Post-compact build order (do next, in this sequence):**
1. [x] **C1 — cognitive tick** (`kernel/tick.py`): idle-cheap heartbeat; drains
   `Extractor.drain()`; started by bridge + REPL; yields to turns. *Goal-post met:* a
   no-input tick makes **zero** model calls; a queued high-significance event
   triggers exactly one action; model-down → tick swallows + self-heals.
   (`tests/test_tick.py`.)
2. [x] **C2 — graded significance** (mean±σ, gap-reasoning): three synthetic events
   land in log / note / study tiers; conservative default; no-model → lowest tier.
   (`ctx/significance.py` `Grader`; `tests/test_significance.py`.)
3. [x] **R1 — fast/slow split** then **R2 — elevation gate** (§7). *Goal-post met:*
   the §7 pseudo-tests pass with the model stubbed; `slow_loop:off` == today (edge
   suite regression green). (`kernel/refine.py` + `kernel/elevate.py`;
   `tests/test_refine.py` + `tests/test_elevate.py`.)
4. [ ] **WS-U/U1→U3** (Raycast geometry → slim chrome → de-bloat `app.js`). *Goal-post:*
   idle window = bar only; auto-grows; `node --check` green; markdown via vendored lib.
5. [~] **U4 elevation rendering** (needs R2) — `app.js` `onRefined` renders the
   `refined` SSE event in place (badge + critique + `.message.refined` accent);
   `finding` cards already existed. Remaining: turn-id-accurate targeting after
   U1/U3. · [ ] **U5 polish**.
6. [ ] **R3 realtime concurrency** — deferred-stretch (user-approved to defer).

**Standing path-correction signals (from §4 — re-check at every checkpoint):**
- A test only passes with the model up → missing degraded path. · Provider `if`
  outside `model.py` → I3 violation. · Default memory behaviour changed → broke the
  M1 regression contract. · A capability in GUI but not CLI (or vice-versa) → parity
  debt. · UI pivoted toward a web-app, or window stopped being a small overlay →
  wrong direction, revert. · `slow_loop`/`extract` on by default destabilised a slow
  local box → gate it off and keep the degraded path. · **Config got deleted or
  crammed back into the main bar → wrong: it must live in a separate, non-intervening
  surface and is meant to GROW (U2/U2b), never shrink the feature set.**

**Conceptual acceptance (the litmus, §5):** with the user idle, the tick runs cheap;
acts only on its own graded judgment; surfaces a refined/elevated answer or a found
gap **without** a re-prompt; the UI feels like a command palette, not a form.
