# LAWRENCE Next Work Checklist

> Detailed execution checklist derived from the current source review.
> Use this as an implementation aid, not as a replacement for
> `AUTONOMY.md` or `IMPLEMENTATION_PLAN.md`. The docs are the conceptual spine;
> the checked-out code remains the source of implementation truth.

## 0. How To Use This Doc

Work one section at a time. Each section below defines the goal, the visible
functionality, the expected interactions with other subsystems, the tests to add
or run, the self-alignment checks, and a correction method when the work drifts.

Definition of done for any checkbox:

- The visible behavior exists through the intended interface, not only in a
  helper function.
- The degraded path is explicit: model down, bridge down, missing optional
  dependency, bad provider response, or cancelled job.
- Runtime data remains under `memory/` or `.runtime/`; never commit runtime
  memory, models, caches, or secrets.
- Provider-specific behavior stays in `services/lk/model.py`.
- The UI reflects kernel state rather than pretending something happened.
- Tests cover the user-facing behavior and the cross-subsystem interaction.

Self-correction rule:

- If a task fails verification three times, stop expanding the fix. Re-read the
  local code path, reduce the scope to the smallest failing contract, and log the
  blocker before trying a different design.

## 1. Current State To Preserve

These are already meaningful assets. Avoid rebuilding them unless a task
explicitly requires it.

- Kernel turn path: analysis, retrieval, response, streaming, schema envelope,
  context write, turn log.
- Memory: rolling layers, daily event log, turn log, notes, journal, per-chat
  conversation stores, shared long-term memory.
- Provider seam: `call_model(role=..., schema=..., priority=...)`, per-role
  routing, local fallback, schema fallback, priority gate.
- Desktop bridge: HTTP routes, SSE, job queue, observer toggles, voice listen,
  task store, chat workspace, history, document ingestion endpoint.
- Perception spine: extraction layer, significance grading, cognitive tick,
  proactive path, finding SSE, desktop notification.
- Retrieval: SQLite FTS, web provider chain, ingestion backend, snippets,
  citations.

Checkpoint:

- Before changing any of the above, identify the exact existing function,
  endpoint, or UI path you are extending.
- If the change would replace a working seam, write down why extension is not
  enough.

## 2. Priority Order

Recommended order:

1. Job cancellation and hard timeouts.
2. Config capability routing: make decoding/tool/schema controls backend-aware.
3. UI truth cleanup: remove fake local answers and hollow controls.
4. Wire existing backend abilities to the UI: ingest and push-to-talk voice.
5. Scheduler/reminder backend.
6. Retrieval dedup and interleave test.
7. Artifact/deep-study engine.
8. Acceptance scenario.

Reason:

- Cancellation protects every later long-running capability.
- Capability routing prevents invalid controls from silently affecting nothing.
- Truthful UI prevents users from trusting decorative state.
- Wiring existing endpoints gives visible progress without inventing new core.
- Scheduler and artifacts are the first real steps from "chat with sensors" to
  "agent that can act over time and produce useful outputs".

## 3. Job Cancellation And Hard Timeouts

> **STATUS: DONE 2026-06-16.** `DELETE /jobs/{id}` (cooperative cancel via a
> per-job `threading.Event` → `should_stop` threaded through `run_turn` →
> `call_model` streaming loops, raising `TurnCancelled`). Queued→never-start,
> running→stops mid-stream, both end `cancelled`; idempotent on terminal jobs.
> Cancel writes nothing to rolling memory/transcript and never fabricates an
> answer; it releases the priority gate (try/finally). NEW: local **non-streaming**
> calls now carry a wall-clock deadline (`_post`/`_post_with_retry`, no retry
> storm). UI: Stop pill + Escape → `deleteBridge` → `bridge_delete` (Tauri shell;
> needs a shell rebuild). Tests: `tests/test_cancel.py` (transport + run_turn +
> bridge lifecycle) and `stress_ui.py` §E. Gate green at 23 suites.

### Goal

A user can stop a running turn. A runaway local generation cannot wedge the
single inference slot forever. Jobs have explicit states: `queued`, `running`,
`done`, `error`, `cancelled`.

### Discrete Functionality

- Add `DELETE /jobs/{id}` to `apps/desktop/scripts/ui_bridge.py`.
- A cancelled queued job never starts.
- A cancelled running job stops streaming deltas and transitions to
  `cancelled`.
- The UI stop action and Escape key call `DELETE /jobs/{id}` for the active job.
- The bridge remains healthy after cancellation.
- Local non-streaming model calls obey a wall-clock deadline, not just streaming
  calls.

### Interaction Rules

- Cancellation must not corrupt memory. If a turn is cancelled before a final
  response, do not append a partial assistant answer to rolling memory or chat
  transcript.
- Cancellation must release the local priority gate.
- Cancellation must not kill observers, the tick, SSE, or unrelated jobs.
- A cancelled voice turn should not disable voice listen mode.
- A cancelled turn may leave a short UI status event, but not a fake answer.

### Tests

Add or update tests for:

- Queued job cancelled before it runs.
- Running stubbed job cancelled while streaming.
- Running stubbed job cancelled before first token.
- Local non-streaming stub that stalls beyond timeout returns an error at about
  the configured deadline and leaves the process healthy.
- SSE stops receiving deltas after cancellation.
- A later turn still succeeds after a cancellation.

Suggested verification commands:

```bash
python3 services/lk/tests/test_concurrency.py
python3 services/lk/tests/test_edge.py
python3 -m compileall -q services/lk apps/desktop/scripts && echo SYNTAX-OK
```

### Self-Alignment

Ask before finishing:

- Can the user see that the job was cancelled?
- Does the final job object distinguish `cancelled` from `error`?
- Does cancellation preserve all durable stores?
- Did the implementation avoid process-wide kill behavior?

### Correction Method

If cancellation becomes invasive, split it:

1. First support cancelling queued jobs.
2. Then add a cooperative cancel flag checked by bridge job code.
3. Then add model streaming cancellation.
4. Finally add non-streaming wall-clock deadline.

Do not solve cancellation by terminating the whole bridge.

## 4. Config Capability Routing

### Goal

The config surface can stay exhaustive, but each option must be routed only to
backends and model families that can actually honor it. Invalid options should
remain visible and configurable for future/provider-specific use, but they must
be marked inactive in the UI and must not silently affect a turn.

Current focus is `llama.cpp`. Future local targets include vLLM, Ollama, and
LM Studio. API targets include OpenAI-compatible endpoints, OpenRouter, Gemini,
Claude/Anthropic, POE, and other restricted hosted providers.

### Core Design

Add a capability layer between raw UI config and model call payloads:

- Backend adapter: local `llama.cpp`, vLLM, Ollama, LM Studio,
  OpenAI-compatible API, Gemini, Anthropic, POE, OpenRouter.
- Model-family profile: Qwen, DeepSeek, Gemma, Llama, Mistral, GPT, Claude,
  Gemini, and unknown/custom.
- Feature capability map: sampling, grammar/schema, partial continuation,
  tool calling, MCP/skills, multimodal input, streaming, JSON mode, stop
  sequences, logit bias, reasoning controls, prompt cache, seed, and timeout.
- Config resolver: takes user config plus active backend/model profile and
  returns three explicit buckets:
  - `active`: applied to this request.
  - `inactive`: valid config key, but not supported by this backend/model.
  - `unavailable`: feature has no direct provider config; suggest another path.

The UI should render these buckets as status markers:

- Green/active: the option will affect this turn.
- Red/inactive: the option is configured but skipped for this backend/model.
- Gray/unavailable: no direct config exists; use another method or provider.

### Capability Dimensions

Sampling options:

- Common: `temperature`, `top_p`, `stop`.
- Local/common llama.cpp-style: `top_k`, `min_p`, `typical_p`, `tfs_z`,
  `repeat_penalty`, `repeat_last_n`, `mirostat`, `mirostat_tau`,
  `mirostat_eta`, DRY parameters, seed.
- Provider-restricted: OpenAI/Claude/Gemini may accept only a subset, may reject
  combinations, or may accept a parameter but ignore it depending on model.
- Unsupported-but-configured: keep the UI value, mark red/inactive, and include
  it in `controls.uiInactiveConfig`.

Structured output and grammar:

- `llama.cpp` may support grammar/JSON schema shapes depending on server build.
- vLLM may support guided decoding depending on version and engine options.
- OpenAI-compatible providers differ between `json_object`, `json_schema`,
  tool-call schema, or no constrained decoding.
- Anthropic structured output is native but not the same payload shape as
  OpenAI-compatible schema.
- Gemini compatibility may require relaxed schemas.
- If grammar restricted decoding is unavailable, offer alternatives:
  - model-prompted schema plus post-parse validation,
  - tool-call schema if the provider supports tools,
  - local fallback through llama.cpp for grammar-heavy turns,
  - response repair pass with explicit warning.

Continuation and partial-prefill behavior:

- Some DeepSeek/Qwen-style or local chat-template paths may allow continuation
  from a partial assistant message or prefilled output.
- Many hosted APIs restrict or reject assistant-prefill behavior.
- The capability map should distinguish:
  - `prefill_assistant`: provider accepts an assistant prefix.
  - `continue_final_message`: backend can continue from a partial response.
  - `raw_completion`: backend exposes non-chat completion mode.
  - `not_supported`: mark inactive and suggest local backend or prompt-level
    workaround.

Tools, MCP, and skills:

- Tool calling is not one feature. Track:
  - provider-native tool calls,
  - OpenAI-compatible tool schema,
  - local grammar-shaped tool JSON,
  - MCP transport availability,
  - Codex/plugin skills availability,
  - LAWRENCE internal tools.
- If native tools are unavailable, the system may still offer a controlled
  fallback: model emits a validated JSON proposal, then LAWRENCE confirms and
  executes through its own tool layer.
- UI must not imply MCP/tools are active unless an executor path exists.
- Skills should be listed as available only when the runtime can actually route
  to them; otherwise show them as configured-but-inactive or unavailable.

Multimodal and local runtime options:

- Vision input, audio input, and local whisper transcription are separate
  capabilities.
- A text-only API may still support audio query through local transcription.
- A local multimodal model may support image blocks but not audio blocks.
- vLLM/Ollama/LM Studio may expose different message block formats even when
  they claim OpenAI compatibility.
- UI should show which modalities are applied to the model, locally converted,
  or skipped.

Custom decoding options:

- Investigate and record what each backend can accept today:
  - `llama.cpp` server request fields and grammar support.
  - vLLM guided decoding and sampling options.
  - Ollama generation options and template/raw mode.
  - LM Studio OpenAI-compatible deviations.
  - OpenAI model-specific sampling and structured output limits.
  - Anthropic sampling, structured output, thinking, and prompt-cache limits.
  - Gemini OpenAI-compatible and native structured-output limits.
  - OpenRouter/POE pass-through behavior and blocked fields.
- The result should be represented as data, not scattered `if` statements.
- Unknown backend means conservative mode: only common options active; everything
  else red/inactive with a reason.

### Discrete Functionality

- Add a backend/model capability registry. Keep it simple data first.
- Add a resolver that returns applied, inactive, and unavailable config lists.
- Route request payload construction through the resolver before `call_model`
  sends anything.
- Include capability summary in `/health`, e.g. backend, provider, model,
  active config families, inactive config families, and modality status.
- Return per-turn `uiAppliedConfig`, `uiInactiveConfig`,
  `uiUnavailableConfig`, and provider warnings in controls.
- Update UI controls to display active/inactive/unavailable markers without
  removing advanced options.
- Keep inactive options persisted in config, but ensure they do not affect the
  current request.
- Provide a path suggestion for unavailable options, such as "use llama.cpp for
  grammar decoding" or "use tool JSON fallback".

### Interaction Rules

- Config is per-turn unless the user explicitly changes global defaults.
- Unsupported fields must not be sent to APIs that reject them.
- Local-only fields may be sent only to local backends that support them.
- Capability detection should happen at backend/model selection time and be
  cheap enough for `/health`.
- A provider error caused by a bad field should update the capability cache or
  emit a warning so the UI can mark that field inactive next time.
- Retrieval/deep search config is not model decoding config; keep it routed to
  retrieval, not to model payloads.
- Grammar/schema config affects structured response generation; it must not
  override the kernel's required envelope schemas unless explicitly scoped to
  answer formatting.
- Tool/MCP/skill config affects agent execution policy; it must not be treated
  as sampling.
- If a user changes backend while a turn is queued, the queued job should use
  the config snapshot taken at enqueue time.

### Example Behavior

When backend is `llama.cpp` with a Qwen/DeepSeek-style local model:

- Enable local sampling knobs that the detected server accepts.
- Enable grammar/schema if the server supports it.
- Enable assistant-prefill/continuation only if the local template path supports
  it.
- Mark hosted-provider-only options inactive.

When backend is Anthropic:

- Enable supported Claude options only.
- Mark `top_k`, `min_p`, Mirostat, DRY, grammar-schema, and raw continuation as
  inactive unless the SDK/provider supports an equivalent.
- If structured output is available through native schema, route through the
  Anthropic adapter rather than OpenAI-style `response_format`.

When backend is Gemini:

- Enable only Gemini-compatible sampling and structured output shape.
- Relax schema only in the Gemini adapter, not globally.
- Mark local decoding options inactive.

When backend is unknown OpenAI-compatible API:

- Enable common OpenAI-compatible fields conservatively.
- Probe schema mode once, cache the working shape, and mark rejected modes
  inactive.
- Do not assume local llama.cpp sampling options work.

### Tests

Add resolver tests:

- llama.cpp profile activates local sampling options and grammar when declared.
- Anthropic profile deactivates llama-only sampling options with reasons.
- Gemini profile transforms or relaxes schema capability without mutating the
  canonical schema.
- Unknown OpenAI-compatible profile sends only conservative common fields.
- DeepSeek/Qwen local profile can enable continuation only when declared.
- A rejected provider field moves from active to inactive after a probe failure.
- Inactive config stays persisted but is absent from outgoing payload.
- Retrieval config is not mixed into model payload config.
- Tool/MCP/skill config is reported separately from sampling config.

Add UI/bridge tests:

- Inactive controls render red/inactive markers.
- Active controls render active markers.
- Unavailable controls render gray markers and a suggested path.
- Switching backend updates markers after `/health`.
- Per-turn controls include applied, inactive, and unavailable buckets.
- Stress test verifies no fabricated support when backend changes.

Suggested verification:

```bash
python3 services/lk/tests/test_offline.py
python3 services/lk/tests/test_edge.py
bash apps/desktop/scripts/stress-ui.sh
node --check apps/desktop/web/app.js
```

### Self-Alignment

Ask before finishing:

- Is capability information data-driven instead of scattered across UI, bridge,
  and model code?
- Can the user see why an option is inactive?
- Does inactive mean "saved but not applied", never "silently ignored"?
- Is the model request payload free of unsupported fields?
- Did provider-specific formatting stay inside model/provider adapter code?
- Can future vLLM/Ollama/LM Studio support be added by extending capability
  data and adapters rather than changing every UI control?

### Correction Method

If the plan becomes too broad, implement it in layers:

1. Add static capability maps for current backends.
2. Add resolver and payload filtering for `llama.cpp` plus current API backend.
3. Add UI markers from resolver output.
4. Add schema/grammar capability routing.
5. Add continuation/prefill capability routing.
6. Add tools/MCP/skills capability routing.
7. Add probe/cache behavior for providers that reject fields dynamically.

Do not start by building every provider adapter. Start with the resolver contract
and current `llama.cpp`/API behavior.

## 5. UI Truth Cleanup

### Goal

The desktop UI should show only state backed by the kernel or explicitly label
local drafts as local-only. Avoid decorative features that imply the agent can do
something it cannot do.

### Discrete Functionality

- Remove `localDraft` fabricated assistant answers.
- Replace bridge-unreachable behavior with an honest error message.
- Remove or disable unsupported sampling controls unless the backend actually
  supports them.
- Make observer, retrieval, proactive, and voice toggles reflect `/health` and
  SSE status instead of only local pressed state.
- Keep UI layout compact. This is a cleanup, not a redesign.

### Interaction Rules

- If the bridge is unreachable, the user message should not appear answered.
- If retrieval is off, deep search must be off for that turn.
- If voice listen fails, the voice button must revert or show unavailable state.
- If an observer toggle is denied by model capability, the button must reflect
  the denied state.
- Unsupported config should be visible as a warning only when the user actually
  requested it.

### Tests

Add or update `apps/desktop/scripts/stress-ui.sh` cases:

- Bridge unavailable produces an error, not a local answer.
- `grep -c localDraft apps/desktop/web/app.js` returns `0`.
- Observer toggle sends `/observer`, then refreshes from `/health`.
- Voice listen failed response leaves voice listen off.
- Retrieval off forces deep search off.
- Unsupported sampling controls are absent or disabled with explicit reason.

Suggested verification:

```bash
bash apps/desktop/scripts/stress-ui.sh
node --check apps/desktop/web/app.js
```

### Self-Alignment

Ask before finishing:

- Is every visible control backed by a real route, local-only label, or disabled
  state?
- Is the user ever shown generated-looking content when the bridge failed?
- Did the change preserve the existing simple floating assistant surface?

### Correction Method

If a control has no backend, choose one:

- Wire it now with a small backend route and tests.
- Hide it until the backend exists.
- Mark it disabled with exact unsupported reason.

Do not keep an active-looking control that only mutates local UI state.

## 6. Ingest UI And Attachment Persistence

### Goal

Document ingestion already exists in the bridge and CLI. The UI needs a clear
path to save attachments or URLs into the knowledge base, then confirm what was
indexed.

### Discrete Functionality

- Add a compact "save to knowledge base" action for eligible attachments.
- Add URL ingestion from the existing URL attachment path.
- Call `POST /ingest` with `{"path": ...}` or `{"url": ...}`.
- Show success with title and chunk count.
- Show failure with a specific converter or fetch error.
- Let future turns cite ingested content through normal retrieval.

### Interaction Rules

- Attachment-to-turn and attachment-to-knowledge-base are different actions.
  Attaching a file for one question should not automatically make it durable
  unless the user requested persistence.
- Ingested documents should go into the same `SemanticDB` used by retrieval.
- Large conversion should be async if it can block the UI.
- Ingestion status should appear in SSE or job polling, not only as a silent
  console event.
- If retrieval is disabled for a later turn, ingested content should not be
  force-injected unless explicitly attached again.

### Tests

Add tests for:

- UI calls `/ingest` for a file attachment with persist action.
- UI calls `/ingest` for a URL.
- Successful ingest returns title and chunks and renders a visible confirmation.
- Failed ingest shows the bridge error.
- After ingesting a small markdown fixture, `SemanticDB.search` finds the text.
- A follow-up turn with retrieval enabled can receive the ingested source as a
  citation.

Suggested verification:

```bash
python3 services/lk/tests/test_offline.py
bash apps/desktop/scripts/stress-ui.sh
```

### Self-Alignment

Ask before finishing:

- Did the user explicitly choose durable ingestion?
- Can the user tell the difference between "attached for this turn" and "saved
  to knowledge base"?
- Does the route reuse `retrieval/ingest.py` rather than duplicating conversion
  logic in the UI?

### Correction Method

If ingestion feels too broad, start with markdown and URL fixtures only. Keep
the UI affordance generic, but report unsupported converters honestly.

## 7. Push-To-Talk Voice

### Goal

Voice should have two distinct modes:

- Voice listen: continuous transcription that may auto-submit turns when intent
  is detected.
- Push-to-talk: user explicitly records one utterance and sends it as one turn.

### Discrete Functionality

- Add a mic PTT button that calls `POST /voice`.
- Surface transcript before or alongside the answer.
- Add debug fixture support in `LK_DEBUG=1` so voice e2e can run without a live
  microphone.
- Preserve voice listen toggle behavior.
- Do not auto-submit every tiny audio chunk as a full turn.

### Interaction Rules

- PTT should work even when the active query model is text-only, because local
  whisper produces text first.
- If a turn is already running, PTT should either queue once or return a clear
  busy state. It should not flood the queue.
- If the microphone records silence, return a specific "no speech detected"
  state.
- Voice transcript should enter chat history as the user message for that turn.
- A cancelled PTT turn should cancel only that generated answer, not the audio
  observer.

### Tests

Add tests for:

- `POST /voice` with fixture produces a queued job.
- Empty transcript returns 422 and no turn job.
- PTT while a turn is running does not produce an unbounded queue.
- UI mic button calls `/voice`, renders transcript, and receives final answer.
- Voice listen remains controlled by `/voice/listen`.

Suggested verification:

```bash
python3 services/lk/tests/test_offline.py
bash apps/desktop/scripts/stress-ui.sh
```

### Self-Alignment

Ask before finishing:

- Are PTT and always-listen visibly different?
- Is transcript handling deterministic in tests?
- Does the audio path still feed extraction for ambient memory separately from
  explicit voice query?

### Correction Method

If live microphone behavior is hard to verify, make fixture mode pass first.
Then run manual live checks separately and log the environment facts.

## 8. Scheduler And Real Reminders

### Goal

Replace the decorative reminders panel with temporal agency: durable scheduled
intents that fire exactly once, survive restarts, and surface through the UI and
desktop notification.

### Discrete Functionality

- Add a scheduler store, either `memory/schedule.jsonl` or SQLite.
- Add CLI commands: `lk remind add`, `lk remind list`, `lk remind done/remove`.
- Add bridge routes for reminders.
- Wire the existing reminders panel to the backend or remove it until backend is
  ready.
- The cognitive tick checks due reminders without a model call.
- Due reminders emit SSE and desktop notification.
- Recurring reminders are optional; if added, they must avoid double-fire.

### Interaction Rules

- Scheduler belongs to the system, not the model. The model may propose a
  reminder, but user confirmation should create it unless policy explicitly
  allows automatic scheduling.
- Due reminders should not block turns, retrieval, observers, or compaction.
- A reminder firing should write a small durable event so it is not repeated
  after restart.
- Time parsing must be timezone-aware and explicit.
- The UI reminder count must come from the backend.

### Tests

Add `services/lk/tests/test_schedule.py`:

- Add reminder, list it, mark done.
- Due reminder fires once.
- Past-due reminder on startup fires once.
- Restart simulation does not double-fire completed reminders.
- Invalid time returns a specific error.
- Tick calls due scheduler without invoking `call_model`.

Add UI stress cases:

- Reminder form posts to backend.
- Badge updates from backend.
- Due event renders in feed.

### Self-Alignment

Ask before finishing:

- Does this make LAWRENCE do something useful when the user is not prompting?
- Can every fired reminder be traced to a durable record?
- Is model involvement optional rather than required?

### Correction Method

If recurrence or natural-language time parsing expands scope, cut it. Ship exact
ISO/local datetime first, then add parsing later.

## 9. Proactive Dedup And Stale Guard

### Goal

The proactive loop should surface useful findings without repeating itself or
surfacing stale conclusions after context has moved on.

### Discrete Functionality

- Deduplicate findings against recent `[FOUND]` and `[PROACTIVE FINDING]`
  entries.
- Add a context version counter or equivalent freshness marker.
- Capture version at proactive start; drop finding if context advanced too far.
- Keep one queued proactive action at a time.

### Interaction Rules

- Dedup should compare headline and insight, not only exact text.
- Stale guard should not block normal memory writes.
- If a user turn is running, proactive should yield or drop according to the
  existing priority gate.
- Dropped proactive output should not create a user-visible error.
- If retrieval warmed the DB but the finding was stale, keep the DB cache but do
  not surface the finding.

### Tests

Add tests for:

- Two equivalent findings produce one surfaced card.
- Similarity below threshold allows a new finding.
- Context version advanced beyond threshold drops the finding.
- Context version small advance still allows finding.
- Proactive while turn gate is busy skips cleanly.

Suggested verification:

```bash
python3 services/lk/tests/test_concurrency.py
python3 services/lk/tests/test_tick.py
```

### Self-Alignment

Ask before finishing:

- Would this annoy the user with repeated cards?
- Can a late retrieval result talk about an old state after the user moved on?
- Is the drop silent and durable-state-safe?

### Correction Method

If context versioning touches too much at once, first implement dedup in
`run_proactive`; then add versioning at the `ContextStore.append/clear/archive`
chokepoints.

## 10. Retrieval Dedup, Caps, And Recency

### Goal

Retrieval should return varied, high-signal citations without over-representing
one page or stale duplicate chunks.

### Discrete Functionality

- Normalize chunk text before dedup.
- Limit chunks per URL before ranking or citation assembly.
- Add mild recency boost for web rows where timestamp is known.
- Preserve existing exact URL citation dedup.
- Keep provider chain errors counted and visible in health.

### Interaction Rules

- Ingested local files should not be treated as stale.
- A file with many similar chunks should not crowd out web evidence.
- Deep search may increase breadth, but should still obey per-URL caps.
- Retrieval disabled means no forced retrieval unless UI explicitly requests
  deep search.

### Tests

Add tests for:

- Near-duplicate chunks collapse.
- Per-URL cap limits repeated chunks.
- Local `file://` rows are never stale.
- Deep search expands breadth without mutating global pipeline defaults.
- Ranking still returns source numbers in stable order.

Suggested verification:

```bash
python3 services/lk/tests/test_offline.py
python3 services/lk/tests/test_edge.py
```

### Self-Alignment

Ask before finishing:

- Did retrieval become more diverse without hiding the best source?
- Does the dedup logic use structured fields where available, not fragile string
  hacks?
- Is the behavior deterministic under stubbed data?

### Correction Method

If ranking changes become hard to reason about, keep the first patch to
pre-ranking dedup and per-URL caps. Add recency only after deterministic tests
are green.

## 11. Artifact And Deep-Study Engine

### Goal

LAWRENCE should produce durable artifacts: markdown explainers, MDX context
packs, code files, and notebooks. The deep-study path should replace or redirect
the current dead `context_pack` endpoint.

### Discrete Functionality

- Add an artifact engine with `make(spec) -> path`.
- Store artifacts under `memory/vault/<slug>/`.
- Support initial kinds: `md`, `mdx`, `code`, and later `notebook`.
- Pull grounding from retrieval, notes, and relevant rolling memory.
- Require citations or mark claims as unsourced.
- Add CLI command: `lk study` or `lk artifact`.
- Add bridge route and compact UI action.
- Redirect or remove `/context-pack/async` once deep study exists.

### Interaction Rules

- Artifact generation must be async and cancellable.
- Generated files are durable outputs, not rolling memory entries.
- The model may propose an artifact, but the user should accept before a large
  job runs.
- Artifacts should record provenance: prompt, sources, model/backend, timestamp.
- If retrieval fails, the artifact should either be clearly unsourced or fail
  with a structured error. Do not fabricate citations.
- A notebook can be valid but unexecuted if Jupyter tooling is unavailable.

### Tests

Add `services/lk/tests/test_artifacts.py`:

- `kind=md` writes a file with citations.
- `kind=mdx` has valid frontmatter/body shape.
- `kind=code` parses or compiles for a simple fixture.
- `kind=notebook` emits valid `.ipynb` JSON when implemented.
- Missing model writes no partial artifact.
- Cancelled artifact job leaves job state `cancelled` and no partial final file.

Add UI/bridge tests:

- Artifact route enqueues a job.
- Job result includes artifact path.
- Existing `/context-pack/async` is either removed, redirected, or clearly
  documented as legacy.

### Self-Alignment

Ask before finishing:

- Is the artifact useful without reopening the chat?
- Does every citation map to an actual retrieved or ingested source?
- Is the output durable and inspectable?
- Is the artifact engine provider-blind?

### Correction Method

Start with `md` only. Do not build notebooks, code execution, and deep-study
iteration in the same first patch.

## 12. Interleave And Acceptance Harness

### Goal

The system needs one holistic test that proves the "mess" works: user turns,
sensor events, extraction, proactive findings, retrieval, voice, tasks,
ingestion, cancellation, and memory writes all running without deadlock.

### Scenario To Prove

One scripted session:

1. Start bridge with stub model.
2. Inject a sensor event.
3. Extraction writes clean memory and optionally a note.
4. Tick drains the event.
5. Proactive warms retrieval and surfaces one finding.
6. User sends a typed turn while background work exists.
7. Model emits a task; UI receives task SSE.
8. Ingest a small document.
9. Ask a follow-up; answer cites the ingested document.
10. Start a long turn, cancel it, and verify later turn still works.
11. Trigger voice fixture as PTT.
12. Write or preview journal.
13. Stop cleanly.

### Expected Interactions

- User turn priority beats proactive and extraction.
- Proactive can skip without failing the session.
- Retrieval cache can persist between steps.
- Memory files remain valid JSONL/Markdown/MDX.
- UI receives deltas, response, tasks, finding, and status without duplicate
  final answers.
- Cancellation does not kill the bridge.
- Journal and notes remain distinct from rolling memory.

### Tests

Create `scripts/test-interleave.py` or a plain test script under
`services/lk/tests/`:

- Use stubbed model responses.
- Use temporary memory directory where possible.
- Assert no fallback parses.
- Assert no deadlock under a bounded timeout.
- Assert all produced JSONL lines parse.
- Assert surfaced event counts exactly match expectations.

Suggested final gate:

```bash
make check
python3 scripts/test-interleave.py
```

### Self-Alignment

Ask before finishing:

- Does this test represent actual user workflows, not only isolated functions?
- Does it catch duplicate responses and stale background actions?
- Is the script deterministic enough for small models and future agents to run?

### Correction Method

If the full interleave script is flaky, split it into two deterministic scripts:

- `test-interleave-core.py`: memory, tick, retrieval, proactive, tasks.
- `test-interleave-ui.py`: bridge jobs, SSE, cancellation, UI-facing events.

Then recombine only after both pass reliably.

## 13. Docs To Refresh After Implementation

Do not update broad docs before behavior exists. When a task lands, update only
the docs whose commands or contracts changed.

Likely updates:

- `README.md`: current quickstart, provider table, ingest, voice, reminders,
  artifacts.
- `docs/CLI.md`: `lk remind`, `lk study`, cancellation/status commands, config
  capability commands if added.
- `apps/desktop/INTEGRATION.md`: new routes, SSE envelopes, and config
  capability marker payloads.
- `docs/IMPLEMENTATION_PLAN.md`: mark stale V3 items done where code proves it.
- `docs/AUTONOMY.md`: update scorecard after scheduler/artifacts land.
- `docs/OPERATIONS.md`: replace conceptual FastAPI/n8n commands or keep the
  banner and avoid using it for current operations.

Doc self-check:

- Every command shown should run in this checkout or be explicitly labelled
  conceptual.
- If a doc names a port, endpoint, or executable, verify it against source.
- If a feature is UI-visible but backend-missing, call it draft/local-only or
  remove it.

## 14. Final Goalposts

The project is past "basic chat" when these are true:

- A user can start the UI, ask, stop, retry, and recover without restarting the
  bridge.
- Screen/audio perception can produce clean memory without user prompting.
- The tick can surface a useful finding without a fresh user prompt.
- Backend/model selection updates config markers so active, inactive, and
  unavailable options are visible before a turn runs.
- Unsupported decoding/tool/schema options are persisted but never silently sent
  to a backend that cannot honor them.
- A scheduled reminder fires after restart exactly once.
- A document can be ingested from UI and cited in a later answer.
- A voice PTT query works with a deterministic fixture and with live mic in a
  manual check.
- A deep-study artifact is created as a file with provenance and real sources.
- The UI has no active decorative controls that imply missing backend behavior.
- `make check` plus the interleave harness pass.

When these pass, the next planning document should shift from "make it real" to
"make it pleasant, fast, and dependable".
