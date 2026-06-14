# LAWRENCE Implementation Plan — v2, minimal-edit revision (2026-06-12)

Working TODO for bringing the repo back to the concept. Written for smaller
models executing one task per session, with per-task checks for self-correction.

**v2 vs v1 — why this is much less edit-intensive:**
- **No new daemon process.** `apps/desktop/scripts/ui_bridge.py` already builds
  the full kernel (stores, retrieval, observers, SSE, job queue). It *is* the
  kernel service. We harden it instead of writing `lkd` and rewriting `cli.py`
  into an HTTP client.
- **The two-kernel data race is fixed with a ~40-line writer lock** making the
  REPL kernel and the UI kernel mutually exclusive — not with a client/server
  rewrite. (REPL-as-HTTP-client stays as an optional stretch task, P9.)
- **No `backends/` package.** All provider logic stays inside
  `services/lk/model.py` behind the existing `call_model()` signature.
- **No UI rewrite.** The current UI's transport (Rust proxy), SSE listener,
  panels, and async-job flow are sound. It gets ~5 targeted patches (P7).

---

## 0. Agent protocol

1. One task per session. Run the task's `Verify` before starting (see it fail)
   and after finishing (it must pass). Never tick a box without running it.
2. If `Verify` fails 3× → revert, log `BLOCKED: <diagnosis>` in the Worklog (§8).
3. Update this file at session end: checkbox + one Worklog row.
4. Commit per finished task, message prefixed `P3.T2: …`. Never commit
   `models/`, `memory/` runtime data, `.runtime/`.
5. Touch only what the task names. Update README/CLI.md in the same task if
   behavior described there changes.

### Invariants

- **I1** Exactly one process writes `memory/` — enforced by the writer lock
  (`services/lk/lock.py`). Never bypass or remove it.
- **I2** JSONL/Markdown/MDX under `memory/` stay canonical + human-readable.
- **I3** Provider-specific logic lives only in `services/lk/model.py`.
  `kernel/invoke.py` and everything above it stay provider-blind.
- **I4** Core runs on stdlib. Heavy deps (`anthropic`, faster-whisper,
  trafilatura, Pillow) are optional extras, imported lazily, failing with a
  clear "pip install …" message.
- **I5** Wire contracts are stable: HTTP payloads per
  `apps/desktop/INTEGRATION.md`; SSE envelope `{"type": "status"|"response"|
  "context"|"tasks"|"delta"|"finding"|...}`. Add types freely; never rename.
- **I6** Never delete/modify `LAWRENCE.code-workspace` or editor config.
- **I7** Ports: llama-server 8190, bridge HTTP 8765, SSE events 8766.
- **I8** Keep `max_tokens` ceilings high on thinking models (ANALYSIS ≥768,
  COMPACT ≥512/768, JOURNAL ≥2048) — small ceilings → budget eaten by the
  thought block → empty output.
- **I9** Don't serialize the parallel paths (observers/proactive/turns) into a
  pipeline; they coordinate through the priority gate in `model.py`.

### Harness

```bash
make check                                    # after P0.T1
python3 services/lk/tests/test_offline.py     # must stay green, no model needed
python3 services/lk/tests/test_concurrency.py
python3 services/lk/tests/test_edge.py
python3 -m compileall -q services/lk apps/desktop/scripts && echo SYNTAX-OK
curl -s http://127.0.0.1:8190/health          # llama-server
curl -s http://127.0.0.1:8765/health          # bridge/kernel
curl -sN http://127.0.0.1:8766/events | head  # SSE
```

"Stub model" = monkeypatch `lk.model._post` (pattern:
`services/lk/tests/test_offline.py:292`).

---

## 1. Goals (user's request, restated)

- **G1** One kernel at a time owns `memory/` (lock), reachable over HTTP+SSE;
  interfaces: overlay UI (primary), REPL, light control CLI, other software.
- **G2** Desktop surface = simple Tauri overlay (hotkey summon/dismiss,
  non-blocking). Keep it close to the current UI; fix, don't redesign.
- **G3** Audio capture → whisper → voice query works.
- **G4** Proactive context→retrieve→surface-unprompted works; system feels
  autonomous, not request/response.
- **G5** Web retrieval robust (multi-provider) + NotebookLM-style doc ingestion.
- **G6** Modern decoding: real streaming, schema-constrained JSON, timeouts/
  cancel, multi-provider (local llama.cpp default; Claude native; GPT/
  OpenRouter/POE via OpenAI-compat), per-role routing.
- **G7** The interleaved whole is the product.

---

## 2. Phases

| Phase | Theme | Status |
|---|---|---|
| P0 | Diagnosis + harness | **done 2026-06-12** |
| P1 | Single-writer lock + inference gate | **done 2026-06-12** |
| P2 | Light control CLI `lk ctl` | **done 2026-06-12** (`./lk`) |
| P3 | Decoding core: streaming, schemas, Anthropic | core done; T6–T8 open |
| P4 | Agentic loop hardening | T2 core done (proactive runs in UI mode now) |
| P5 | Audio fix | **capture+whisper working 2026-06-12** (parec, no sudo); voice e2e T3 open |
| P6 | Retrieval: providers + ingestion | T1+T2 done; T3 open |
| P7 | UI: 5 targeted patches | T1+T3 done; T2/T4/T5 open |
| P8 | Polish + acceptance | open |
| P9 | Optional stretch | open |

### Diagnosis findings (2026-06-12 — drives P5/P6)

- **Audio (P0.T2):** not a code bug. The toolchain is absent: no `arecord`,
  no `ffmpeg`, no `pactl`, no faster-whisper, no whisper-cli. WSLg Pulse socket
  IS present (`PULSE_SERVER=unix:/mnt/wslg/PulseServer`). Fix = install:
  `sudo apt install alsa-utils ffmpeg pulseaudio-utils` +
  `pip install -e ".[audio]"`, then re-run `scripts/diag-audio.sh` and proceed
  with P5.T1 hardening.
- **Retrieval (P0.T3):** DDG **bot-blocks bursts with HTTP 202 anomaly pages**;
  the old code fired parallel query bursts and swallowed every failure →
  silent empty results after the first call. Fixed by P6.T1 (pacing ≥1s,
  provider chain, 5-min cooldown circuit breaker, surfaced `search_stats()` in
  `/health`). Verified live: `pipeline.retrieve` went 0 → 3 cited results.

### P0 — Diagnosis + harness (do these first; no behavior change)

- [x] **P0.T1 `make check`.** New `scripts/check.sh`: `python3 -m compileall -q
  services/lk apps/desktop/scripts` + the three test scripts; print
  `CHECK: PASS|FAIL`; nonzero exit on FAIL. Add `check:` to `Makefile`.
  *Verify:* `make check` exits 0 on current tree.
- [x] **P0.T2 Audio diagnosis.** New `scripts/diag-audio.sh`, stages each
  printing `STAGE <n>: OK|FAIL <reason>`: arecord present → ffmpeg present →
  Pulse reachable (`pactl info`; WSLg server `/mnt/wslg/PulseServer`) → 2s
  record via `lk.obs.audio.record_window` → `rms_db` value →
  `import faster_whisper` → transcribe. *Verify:* runs to completion; the
  failing stage + reason goes in the Worklog. Fixes happen in P5, not here.
- [x] **P0.T3 Retrieval diagnosis.** New `scripts/diag-retrieval.sh`:
  `ddg_search("python json parsing", 5)` count → raw GET of the DDG html
  endpoint (status + first 200 chars; look for captcha/bot-block) →
  `import trafilatura` → fetch+extract one URL → `SemanticDB().search("test")`.
  *Verify:* definitive per-stage output; findings in Worklog.
- [x] **P0.T4 Proactive regression test.** Extend `test_offline.py`: stub
  `_post` to return PROACTIVE then PROACTIVE_BRIEF JSON; stub
  `RetrievalPipeline.retrieve` → one fake `CitedResult`; assert `present_fn`
  got a finding and ctx gained `kind="finding"`. *Verify:* `make check` green.
- [x] **P0.T5 Stale-docs banner.** Prepend `> **CONCEPTUAL REFERENCE ONLY** …`
  to the 8 Mar-2026 docs (ARCHITECTURE, AGENT_HANDOFF, PLAN_COVERAGE,
  IMPLEMENTATION_STATUS, interfaces, SCHEMAS, OPERATIONS, N8N_WORKFLOWS).
  *Verify:* `grep -l "CONCEPTUAL REFERENCE ONLY" docs/*.md | wc -l` → 8.

### P1 — Single writer + inference gate

- [x] **P1.T1 Writer lock** *(done 2026-06-12)* — `services/lk/lock.py`:
  `flock` on `memory/.writer.lock`; acquired by `cli.main()` (role `repl`) and
  `DesktopBridge.__init__` (role `ui-bridge`). Second kernel exits with a clear
  message naming the owner. REPL and UI bridge are now mutually exclusive.
- [x] **P1.T2 Priority inference gate** *(done 2026-06-12)* — in `model.py`:
  local calls serialize through a priority gate (turn 0 < compact 1 <
  proactive 2); proactive is droppable (`skipped: True` when the gate is busy
  — `run_proactive` already no-ops on empty text).
- [x] **P1.T3 Controls actuation in the bridge path.** Today only the REPL
  applies model `controls` (`cli.py` `_apply_controls`). In `ui_bridge.py
  DesktopBridge.turn()`: after `run_turn`, apply `controls` via
  `self._set_vision/_set_audio` (map `"hi"` → `capture_now` + pending image),
  then `self.ui.push_context_event("controls", str(applied))`.
  *Verify:* stub backend returning `controls:{"vision":"off"}` with a running
  vision observer → observer stopped; SSE event seen on `/events`.
- [x] **P1.T4 Gate regression test.** In `test_concurrency.py`: stub `_post`
  sleeping 0.2s; fire a proactive call while a turn holds the gate → proactive
  returns `skipped`; queue order respects priority. *Verify:* `make check`.

### P2 — Light control CLI (the "before heavy machinery" interface)

- [x] **P2.T1 `lk ctl` subcommand set.** New `services/lk/ctl.py` +
  console-script `lkc = "lk.ctl:main"` in pyproject (keep `lk` pointing at the
  REPL for compatibility). Stdlib-only module-level imports. Subcommands:
  `status` (bridge `/health`, llama `/health`, lock owner from
  `memory/.writer.lock` — all readable without loading anything heavy),
  `start [repl|ui]` (delegates to existing entry points / `desktopctl.sh`),
  `stop`, `attach` (tmux `/tmp/lk-tmux`), `doctor` (runs `scripts/diag-*.sh`),
  `config get|set` (reads/writes `.runtime/lk.json`, consumed by cli/bridge as
  defaults under their existing flags).
  *Verify:* `time python3 -m lk.ctl status` < 0.5s with everything stopped;
  `python3 -X importtime -m lk.ctl status 2>&1 | grep -cE "PIL|whisper|trafilatura|anthropic"` → 0.
- [x] **P2.T2 Config file consumption.** `cli.py` + `ui_bridge.py` read
  `.runtime/lk.json` (if present) for defaults: backend kind, api base/model/
  key-env, model path, ctx size. Precedence: flags > env > lk.json > built-ins.
  Small helper `services/lk/config.py` (~60 lines), used by both.
  *Verify:* write `{"backend":"anthropic","api_model":"claude-opus-4-8"}` →
  `lk.ctl status` and bridge `/health` report that backend without env vars.

### P3 — Decoding core (all inside `model.py` / `kernel/`)

- [x] **P3.T1 JSON schemas** *(done 2026-06-12)* —
  `services/lk/kernel/schemas.py`: ANALYSIS / RESPONSE / PROACTIVE /
  PROACTIVE_BRIEF envelopes (`answer_text` first in RESPONSE — property order
  drives grammar order and answer streaming).
- [x] **P3.T2 Schema-constrained decoding** *(done 2026-06-12)* — `call_model`
  accepts `schema=`; local/OpenAI-compat: `response_format json_schema` →
  fallback `json_object+schema` → plain (working shape cached per session);
  Anthropic: `output_config.format`. `_extract_json` stays as safety net;
  fallback uses are counted in `model.fallback_parses()`.
- [x] **P3.T3 Real token streaming** *(done 2026-06-12)* — `call_model`
  accepts `stream_fn=`; local/compat parse SSE `data:` lines; Anthropic uses
  `messages.stream`. `run_turn` accepts `stream_fn` and streams **the
  `answer_text` value as it decodes** via `AnswerTextStreamer` (incremental
  JSON-string scanner — handles escapes across chunk boundaries). The bridge
  forwards deltas as SSE `{"type":"delta","text":...}`.
- [x] **P3.T4 Native Anthropic backend** *(done 2026-06-12)* — kind
  `"anthropic"` in `model.py`: official SDK (lazy import; `pip install -e
  ".[api]"`), `ANTHROPIC_API_KEY` env, `LK_BACKEND=anthropic` (+ optional
  `LK_API_MODEL`, default `claude-opus-4-8`). Maps system param, base64 image
  blocks, `max_tokens` always, `stop_sequences`; **drops all sampling on
  opus-4-7/4-8/fable** (Appendix A); audio blocks dropped with a one-time
  warning (whisper stays local). Streaming + structured outputs wired.
- [x] **P3.T5 Sampling capability gating** *(done 2026-06-12)* — llama-only
  knobs (mirostat/dry/typical/tfs/min_p/top_k/penalty extras) are stripped
  before any API backend, with a one-time stderr warning per key.
- [ ] **P3.T6 Wall-clock timeout + cancel.** Streaming local calls now have a
  wall-clock deadline; finish the job: non-stream local calls keep
  `req_timeout=None` today — give them the same deadline by routing JSON call
  sites through the streaming path internally OR a reader thread with
  deadline. Then `DELETE /jobs/{id}` in `ui_bridge.py`: set a cancel flag the
  stream loop checks (raise → job state `cancelled`).
  *Verify:* stub server that stalls → call errors at ~deadline, process
  healthy; DELETE a running stubbed job → `cancelled`.
- [ ] **P3.T7 Per-role routing.** `model.py`: optional `routing` dict in
  `.runtime/lk.json` mapping role→`{kind, base_url, model, key_env}`;
  `call_model(role="response"|"analysis"|"proactive"|"compact"|"journal")`
  resolves the backend per call (default: the one configured backend —
  zero behavior change unless configured). `invoke.py` already tags priorities;
  add `role=` at the same call sites.
  *Verify:* unit test with two stub backends; `compact` routed to the second.
- [ ] **P3.T8 Provider smoke scripts.** `scripts/check-provider.sh
  [anthropic|BASE MODEL KEYVAR]`: one `/turn`-level call, assert valid
  envelope; print `SKIP` (exit 0) when the key env is unset. Document POE
  (`https://api.poe.com/v1`), OpenRouter, OpenAI, LM Studio base URLs in
  README's provider table.
  *Verify:* script passes or SKIPs for each provider.

### P4 — Agentic loop hardening

- [ ] **P4.T1 Proactive dedup + coalescing.** In `daemon-less` terms: in
  `kernel/invoke.py run_proactive`, before `present_fn`, Jaccard-compare
  (reuse `ctx/gate.py` helpers) headline+insight against the last 5
  `[FOUND]`/`[PROACTIVE FINDING]` entries in L1; skip if similarity > 0.6.
  In `cli.py`/`ui_bridge.py` trigger paths ensure max one queued proactive
  (the gate's droppable behavior already gives this — add a regression test).
  *Verify:* stubbed double event → one finding.
- [ ] **P4.T2 Desktop notification for findings.** `services/lk/notify.py`
  (~30 lines): `notify-send` if present else PowerShell balloon on WSL else
  no-op; never raises. Call from both finding presenters.
  *Verify:* function returns cleanly on a system with neither tool.
- [ ] **P4.T3 Tasks SSE everywhere.** `_tasks_fn` in `cli.py` doesn't broadcast
  (UIConnector is no-op there — fine), but the bridge's must `push_tasks` on
  *every* mutation including user ops (already does on `/tasks` POST; add to
  `_tasks_fn`). *Verify:* stub model emits `tasks:["x"]` → SSE `tasks` event.
- [ ] **P4.T4 Context-version stale guard.** `ctx/store.py`: monotonic
  `self.version` bumped in `append/clear/_archive`; `run_proactive` captures it
  at start, drops the finding if `ctx.version` advanced > 5.
  *Verify:* unit test both sides of the threshold.
- [ ] **P4.T5 Interleave test (the holistic gate).** `scripts/test-interleave.py`
  (stub backend): 3 turns + spool-injected sensor events + forced compaction
  (tiny budgets) + proactive + model-emitted tasks/controls, 60s. Assert: all
  responses ordered, memory files valid JSONL, `fallback_parses()==0`, no
  deadlock. Wire into `make check`. *Verify:* prints `INTERLEAVE: PASS`.
- [ ] **P4.T6 (optional, after P4.T5 is stable) Slow-loop addendum.** One
  bounded refinement pass behind config `slow_loop:on`: REFINE prompt returns
  the RESPONSE envelope or `{"improved":false}`; queued at proactive priority
  (droppable); SSE `{"type":"addendum","turn_id",...}`.
  *Verify:* stub: addendum after response with matching turn_id; `improved:
  false` → silence.

### P5 — Audio (fix what P0.T2 found; likely WSLg/Pulse)

- [ ] **P5.T1 Recorder probe order.** `obs/audio.py`: on observer start, probe
  recorders once (ffmpeg-pulse first when `$WSL_DISTRO_NAME`/`$PULSE_SERVER`
  present — ALSA `arecord` usually can't see the WSLg mic), remember the
  winner; set `PULSE_SERVER=/mnt/wslg/PulseServer` fallback if unset on WSL;
  surface one live-feed line on failure instead of silent
  `recording_ok=False`. *Verify:* diag stages 1–5 OK; speaking during a window
  yields `rms_db > -42`.
- [ ] **P5.T2 Transcription observability + fixture test.** Configurable
  whisper model size; log active transcriber at start; errors to live feed.
  Fixture `services/lk/tests/data/hello.wav` (record a short phrase once);
  offline test asserts a known word (SKIP without faster-whisper).
  *Verify:* `make check`; REPL `/record 3 …` returns the transcript.
- [ ] **P5.T3 Voice query e2e.** Confirm `/voice` (PTT) and `/voice/listen`
  paths work against the fixed recorder; debug hook: `/voice` accepts
  `{"fixture": "<path>"}` in `LK_DEBUG=1` mode → deterministic e2e test.
  *Verify:* fixture call returns an answer containing the known word (stub
  backend fine).

### P6 — Retrieval

- [ ] **P6.T1 Provider chain.** `retrieval/web.py`: providers in order
  `ddg_html` (current) → `ddg_lite` (`https://lite.duckduckgo.com/lite/`,
  simpler markup) → `searxng` (JSON API, only if `searxng_url` configured) →
  `brave` (only if `brave_api_key`). Each: 10s timeout, failures *counted and
  logged*, never raised; bot-block detection (HTTP 202/403/captcha marker) →
  next provider. Expose per-provider counters via a `web.stats()` dict shown
  in bridge `/health`. *Verify:* diag script shows ≥1 provider ≥3 results;
  unit test: first provider stub raises → chain falls through.
- [x] **P6.T2 Document ingestion.** `retrieval/ingest.py` (~60 lines):
  `ingest(path_or_url)` = `converters.convert` → `web.chunk_text` →
  `SemanticDB.upsert(url=f"file://{abspath}", title=name)`. `url_known`:
  treat `file://` as never stale. Bridge: `POST /ingest {"path"|"url"}`;
  attachments get `"persist": true` flag calling the same path; REPL `/ingest
  PATH`. *Verify:* ingest a small .md fixture → `SemanticDB.search` finds its
  text → `retrieve()` returns it as a CitedResult; `/db info` count grows.
- [ ] **P6.T3 Dedup + caps.** `retrieval/pipeline.py`: near-dup chunk drop
  (normalized hash), per-URL cap 3, mild recency boost for web rows.
  *Verify:* unit tests.

### P7 — UI: five targeted patches (no redesign — keep current look/structure)

The current `web/app.js` already has: EventSource on `/events`, async job
polling, panels, attachments, Rust-proxy transport. Patch in place; rebuild
embedded frontend after every change (`npm run popup:restart`).

- [x] **P7.T1 Real streaming.** `app.js` `connectEvents` `onmessage`: handle
  `payload.type === "delta"` → append `payload.text` to the in-flight
  assistant draft (reuse the existing draft mechanism in `streamAssistant`);
  on the final job result, replace draft with rendered markdown. Delete the
  timer-based fake chunk loop. *Verify:* asking with a local model shows
  progressive text matching generation; `grep -c "setTimeout" web/app.js`
  drops by the typewriter's two uses.
- [ ] **P7.T2 Truthful toggles.** Observer/retrieval/proactive toggles read
  initial state from `/health` and update on SSE `status`/`context` events —
  no purely-local pressed state. *Verify:* toggle vision in REPL-less bridge →
  `/health.observers.vision` flips and the button reflects it after refresh.
- [x] **P7.T3 Findings surface.** Handle SSE `{"type":"context","kind":
  "finding"}` / future `finding` events → small dismissable card above the
  input (markdown, citation links). *Verify:* stubbed proactive finding shows
  a card; dismiss removes it.
- [ ] **P7.T4 Dead-path cleanup.** Remove `localDraft` fabricated responses
  (replace with an honest "bridge unreachable: <err>" message) and any control
  that has no backend endpoint; keep layout otherwise untouched.
  *Verify:* `grep -c localDraft web/app.js` → 0; stress script passes.
- [ ] **P7.T5 Cancel button.** Esc / stop-button during generation →
  `DELETE /jobs/{id}` (after P3.T6). *Verify:* mid-stream cancel stops deltas,
  UI returns to idle, bridge healthy.

### P8 — Polish + acceptance

- [ ] **P8.T1 One-command start.** `lk.ctl start ui` = bridge (spawns
  llama-server if local backend) + popup; degraded-mode message until model
  ready. *Verify:* cold machine → first answer with one command.
- [ ] **P8.T2 Crash hygiene.** Stale-lock reclaim (owner PID dead → take over);
  SIGTERM → journal write. *Verify:* `kill -9` the bridge → restart works with
  no manual lock removal.
- [ ] **P8.T3 Docs to reality.** README/CLI.md/INTEGRATION.md: lock semantics,
  `lk.ctl`, providers table, streaming, ingestion. *Verify:* every command in
  README runs; `grep -rn "lawrence_kernel\|:8000\|:5678" README.md docs/CLI.md` → 0.
- [ ] **P8.T4 Acceptance scenario.** One continuous session: start → screen
  events → unprompted finding card → voice question answered with citations →
  PDF ingested + follow-up cites it → model self-adds a task → `/journal` →
  stop. Transcript saved to `.runtime/acceptance/`. Failures become new tasks
  here. *Verify:* all steps pass.

### P9 — Optional stretch (only after P8)

- [ ] **P9.T1 REPL as HTTP client** of the bridge (removes mutual exclusion).
- [ ] **P9.T2 Adaptive cadence controller** (event-rate → proactive interval).
- [ ] **P9.T3 Anthropic prompt caching** (`cache_control` breakpoint after the
  L2 section of the context tail; verify `usage.cache_read_input_tokens > 0`
  on consecutive turns; best-effort — trim/compaction may invalidate).

---

## Appendix A — Anthropic backend facts (verified 2026-06; do not guess)

- Official `anthropic` SDK, lazy import, extra `api` in pyproject.
  `anthropic.Anthropic()` reads `ANTHROPIC_API_KEY`.
- `client.messages.create/stream`. **`max_tokens` required.** `system` is a
  top-level param. First message role must be `user`.
- Model IDs (exact, no date suffixes): default `claude-opus-4-8`; also
  `claude-sonnet-4-6`, `claude-haiku-4-5`, `claude-opus-4-7`, `claude-fable-5`.
  $/1M in/out: opus-4-8 5/25, sonnet-4-6 3/15, haiku-4-5 1/5.
- Images: `{"type":"image","source":{"type":"base64","media_type":...,
  "data":...}}`. **No audio input** — drop audio blocks; whisper stays local.
- Sampling: opus-4-7/opus-4-8/fable-5 → `temperature`/`top_p`/`top_k` all
  **400**; omit. Other models: at most one of temperature/top_p. Never send
  llama-only knobs.
- Thinking: omit the param by default; opt-in `thinking={"type":"adaptive"}`
  (never `budget_tokens`; explicit `disabled` 400s on fable-5). Thinking comes
  as separate blocks → only join `text` blocks.
- Structured outputs: `output_config={"format":{"type":"json_schema",
  "schema":S}}`; every object needs `"additionalProperties": false`; no
  recursion, no min/max/length constraints. Guarantees first text block is
  valid JSON. Incompatible with prefills/citations.
- Streaming: `with client.messages.stream(...) as s: for t in s.text_stream:
  …; s.get_final_message()`.
- Errors: typed exceptions; SDK retries 429/5xx itself (`max_retries`).
  Handle `stop_reason` ∈ end_turn / max_tokens / refusal /
  model_context_window_exceeded.
- Works today without any of this: Claude via OpenRouter on the existing
  compat backend (`LK_API_BASE=https://openrouter.ai/api/v1
  LK_API_MODEL=anthropic/claude-sonnet-4-6`) — no caching/structured-output/
  thinking control; that's what the native backend adds.

## Appendix B — Environment facts

- WSL2+WSLg. Vision capture via `powershell.exe` works. Mic: PulseAudio at
  `/mnt/wslg/PulseServer` (ALSA arecord usually fails — see P5.T1).
- llama-server `third_party/llama.cpp/build/bin/llama-server`, gemma-4-E4B
  Q4_K_M + mmproj, port 8190, `--parallel 1`, kept warm (tmux `/tmp/lk-tmux`).
- WebKitGTK/WSLg blocks direct fetch to localhost — UI HTTP goes through the
  Rust `bridge_get`/`bridge_post` commands. Tauri frontend is embedded at
  build time → `npm run popup:restart` after `web/` edits; window APIs need
  entries in `src-tauri/capabilities/default.json`.
- Tests are plain scripts (no pytest): `python3 services/lk/tests/test_*.py`
  with `sys.path.insert(0, "services")`. They stub `lk.model._post` — keep
  that function name and `(payload, timeout)` signature stable.

## 10. v3 — Agentic loop redesign (2026-06-13, from user spec)

The system is a continuous **sense → extract → remember → (act)** loop, not a
chatbot. Decisions confirmed with the user:

- **Preprocess (no model):** vision OCR + audio transcription run continuously
  into a raw buffer — NOT context yet.
- **Extract (cheap model, NO rolling context):** on real info-gain, hand the
  model just the raw slice → clean semantic entry → L1 → cascade L1→L2→L3. Fixes
  garbled-OCR AND prompt bloat. Routed to the fast background model.
- **Voice:** model-classifies-intent (primary) + wake word + push-to-talk, all
  available. A 4s chunk must NOT auto-queue a full turn (current bug).
- **Graded proactive:** model scores context significance across parameters
  (grammar-enforced JSON); score vs configurable mean±σ → tier:
  below −1σ → log+journal only; within ±1σ → brief retrieval+update;
  above +1σ → dense study+response. Default conservative; per-domain configurable.
- **Memory split (keep distinct):** Log = discrete independent entries; Rolling
  L1/L2/L3 = compressing associative working memory; Journal = model's reflective
  narrative of what the user's been doing.
- **Deep-study export:** explicit command + UI button, plus the model *proposing*
  it when depth exceeds inline capacity. "Context of context" — relevant bits +
  dense retrieval + where/how to study (articles/blogs/social/videos). Iterative
  study + compaction into the DOCUMENT (not system memory). MD/MDX + strict cites.
- **Backends:** queries on chosen backend; background (extract/proactive/compact/
  journal/study) routed to fast API (Gemini) with **local fallback**. Secrets in
  `~/.lawrence/secrets.env` (never in git).

### v3 tasks

- [x] **V3.T1 Secrets + providers + per-role routing** *(done 2026-06-13)* —
  `config.py` (secrets file, PROVIDERS, routing resolution), `model.py`
  (thread-local per-role backend + `configure_routing` + local fallback),
  `ctl.py` `lk secrets`. Default config: query=local, background=gemini.
- [x] **V3.T2 Gemini live** *(done 2026-06-13)* — user adds `GEMINI_API_KEY` via `lk secrets set`;
  verify a routed background call hits Gemini and a query stays local.
- [ ] **V3.T3 Extraction layer** — `run_extract(slice)` in invoke.py: terse
  EXTRACT prompt, no rolling context, role="extract". Observers buffer raw
  OCR/transcript; on info-gain gate, run extract → clean L1 entry (replaces raw
  distill dump). New EXTRACT prompt + schema.
- [ ] **V3.T4 Audio loop fix** — stop auto-queuing a turn per chunk. Audio →
  preprocessing → extraction. Voice→model only via intent-classification +
  wake word + PTT. Accumulate utterances; transcribe larger windows.
- [ ] **V3.T5 Graded proactive** — significance scoring (grammar JSON) → mean±σ
  tiers (log / brief / dense). Config: thresholds + per-domain.
- [ ] **V3.T6 Terse prompts** — shorten ANALYSIS/RESPONSE system prompts (schema
  enforces structure, so drop per-field prose). Cuts ~400 tok/pass on CPU.
- [ ] **V3.T7 Don't auto-attach stale images** — only user-attached / Screen
  mode / model-requested hi-res reach a turn (vision-encoding a 2880×1800 frame
  on CPU is the turn-latency killer).
- [ ] **V3.T8 Deep-study export** — `run_study()` + `lk study` + UI button +
  model-proposes-when-deep. Iterative fetch+study+compact → cited MD/MDX export.
- [ ] **V3.T9 Memory-split crispness** — verify Log vs Rolling vs Journal are
  cleanly separated and each is inspectable/exportable.

### Diagnosis that drove this (2026-06-13)

Bridge turns were 54–120s while a direct model call was 1–14s. Root causes, all
fixed or planned: (a) **thinking on** — Gemma spent 100s of tokens thinking
(≈128s vs ≈1s) → fixed, `chat_template_kwargs enable_thinking=false` default;
(b) **schema forced all ~10 envelope fields** → ~300-token output every turn →
fixed, lean schemas (only answer_text required); (c) **runaway gens to
max_tokens=2048 wedged the single CPU slot for ~8 min** → fixed, `_LOCAL_MAX_TOKENS`
cap (1024); (d) **audio voice-mode flooded the queue** (a turn per 4s chunk) →
fixed, in-flight coalescing + V3.T4; (e) **stale screenshot auto-attached** →
vision-encoded on CPU → V3.T7. The structural fix for all latency is V3's clean
small context + background routing to Gemini.

## 8. Worklog

| date | task | result | notes |
|---|---|---|---|
| 2026-06-12 | plan v1→v2 | rewritten | minimal-edit strategy; UI kept, no daemon rewrite |
| 2026-06-12 | P1.T1 P1.T2 P3.T1–T5 | implemented | lock.py, gate+schema+stream+anthropic in model.py, schemas.py, invoke.py streaming, bridge delta SSE |
| 2026-06-12 | P0.T1–T5 | done | make check green; diag scripts written+run; findings recorded above; banners on 8 docs |
| 2026-06-12 | P1.T3 P1.T4 | done | bridge _apply_model_controls + SSE; gate ordering test in test_concurrency.py |
| 2026-06-12 | P6.T1 | done | provider chain (ddg_html/ddg_lite/searxng/brave) + pacing + cooldown + search_stats in /health; live verify 0→3 results |
| 2026-06-12 | P7.T1 | done | app.js consumes SSE delta → live draft; typewriter replay skipped when deltas streamed; REBUILD frontend before testing (npm run popup:restart) |
| 2026-06-13 | hotkey fix | done | WSLg global hotkey via Windows-side listener (host/windows/GlobalHotkey.ps1) → control socket (:8767) in main.rs; debounce + hide()-not-minimize + recenter-if-offscreen; auto-launched by desktopctl start |
| 2026-06-13 | audio fix | done | _parec recorder (WSLg, no sudo); gain-normalize quiet capture; SILENCE_DB -55; whisper cached; real transcription confirmed in SSE |
| 2026-06-13 | vision rework | done | foreground-window capture (1 PS call, native-res, relevant title) as primary; OCR psm3 (real content vs chrome); precise self-skip; fixes ~11s/tick + garbled all-window OCR |
| 2026-06-13 | speed root-cause | done | thinking-off default (≈128s→≈1s), lean schemas (only answer_text required), _LOCAL_MAX_TOKENS cap (anti-wedge); voice in-flight coalescing |
| 2026-06-13 | V3.T1 | done | secrets (~/.lawrence/secrets.env, 0600, off-repo), PROVIDERS registry, per-role routing (thread-local backend + local fallback) in model.py, lk secrets cmd; default cfg query=local/background=gemini |
| 2026-06-13 | V3.T2 | done | Gemini verified: key valid, gemini-2.5-flash (2.0-flash hit free quota); apply_to_env now configures default backend + routing directly; query via Gemini 8.2s + streaming + valid envelope (was 50s+ local) |
| 2026-06-13 | hotkey hardening | done | GlobalHotkey.ps1 rewritten: PeekMessage+Sleep (no busy-loop), self-terminates ~30s after control socket gone, killable by lk stop (kill_windows_hotkey by cmdline). Note: the 79-min CPU hog PID 33088 is ELEVATED/non-LAWRENCE — user must admin-kill it |
| 2026-06-13 | backend default | done | switched query backend to gemini (local too slow at ~4tok/s); local is the resilience fallback. Switch back: lk config set backend local |
| 2026-06-13 | gemini model | done | switched to gemini-3.1-flash-lite-preview (1M ctx, multimodal, ~380 tok/s, free tier) — verified 3.0s; PROVIDERS default updated |
| 2026-06-13 | impl audit | done | docs/AUDIT.md: kernel stub-free (1 intentional no-op); HOLLOW=reminders panel (localStorage only, no backend) + 3 unsupported sampling knobs; DEAD=/context-pack,/ingest,/voice PTT (backends w/o UI); doc drift: README crates/system-hooks absent |
| 2026-06-12 | harness | note | offline store-cascade check was flaky (read during compaction) — settle-wait added; not a code regression |
| 2026-06-12 | P2.T1 P2.T2 | done | ./lk front door (ctl.py, 0.3s status) + config.py (.runtime/lk.json → env); wizard validated; README quickstart rewritten |
| 2026-06-12 | P5 partial | done | installed faster-whisper (pip) + pulseaudio-client (conda, NO sudo); new _parec recorder first in chain; diag-audio: record 64KB OK, VAD gates, whisper importable — speech test pending a human |
| 2026-06-12 | P4.T2 core | done | bridge now triggers run_proactive on sensor events (was REPL-only!) + finding SSE + notify.py (notify-send/PS balloon); dedup vs recent findings still open |
| 2026-06-12 | P6.T2 | done | retrieval/ingest.py + POST /ingest + ./lk ingest; offline test (md fixture searchable via FTS5) |
| 2026-06-12 | P7.T3 | done | app.js renders finding SSE as a card-message; REBUILD frontend (npm run popup:restart) |
