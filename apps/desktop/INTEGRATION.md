# Desktop Popup Integration

The native desktop surface is a small Tauri launcher popup, not the static web
preview. Use the popup controller for normal operation:

```bash
cd apps/desktop
npm run popup
npm run popup:status
npm run popup:stop
npm run popup:restart
```

The default global hotkey is `Ctrl+Shift+L`. Change it and restart:

```bash
npm run popup:hotkey -- Ctrl+Shift+L
npm run popup:restart
```

Runtime config is stored in `.runtime/desktop/desktop.env`.
The WSL-friendly default keeps blur-hide off; set `LAWRENCE_HIDE_ON_BLUR=1` in
that env file if the popup should hide whenever it loses focus.

## Process Ownership

The desktop layer owns two processes:

- `lawrence-desktop`: the native Tauri popup window.
- `ui_bridge.py`: a small HTTP bridge on `http://127.0.0.1:${LK_UI_PORT:-8765}`.

The bridge imports the existing `services/lk` modules and calls kernel paths. It
does not require changes inside the kernel or CLI.

The kernel/CLI manager should treat the desktop UI as an optional client:

- Start/stop/restart it with `apps/desktop/scripts/desktopctl.sh`.
- Read health from `GET /health`.
- Submit UI turns through the async job API.
- Push future kernel events to the same bridge shape, or replace this bridge
  with a manager-owned transport that keeps the same payload contracts.

## Async Bridge Contract

Health:

```http
GET /health
```

Response:

```json
{
  "ok": true,
  "modelHealth": true,
  "backend": "local: http://127.0.0.1:8190",
  "capabilities": {
    "backend": "local", "provider": "local", "model": "",
    "sampling": ["frequencyPenalty", "minP", "mirostat", "topK", "topP", "..."],
    "schema": "grammar", "prefill": true,
    "unavailable": ["epsilonCutoff", "etaCutoff", "grammarSchema"]
  },
  "modalities": "text+vision+audio",
  "observers": { "vision": false, "audio": false }
}
```

`capabilities` (WS-K) describes which decoding families the **live** backend can
honor, so the UI can mark options active/inactive/unavailable before a turn runs.
`sampling` lists the active sampler families (camelCase); `schema` is the
structured-output strategy (`grammar`/`native`/`json_schema`/`prompt`); `prefill`
is assistant-prefill/continuation support; `unavailable` keys have no direct
provider config on any current backend. Per turn, `controls` carries
`uiAppliedConfig`, `uiInactiveConfig` (`[{key, reason}]`), and
`uiUnavailableConfig` (`[{key, reason, suggestion}]`): inactive options stay
saved in config but are **never sent** to a backend that cannot honor them.

## Subsystem metrics (§5)

Cheap, **honest** per-subsystem aggregation for the launcher's Detailed metrics
view. No model probe, no DB scan — readiness still comes from `/health`. A
subsystem reports `null` when it has no published number, and the launcher renders
that as `n/a` rather than fabricating a value. The shape is fixed; individual
values may turn from `null` → data as subsystems learn to report, without breaking
the contract.

```http
GET /metrics
```

```json
{
  "ok": true,
  "subsystems": {
    "model":      { "backend": "local: …", "modalities": "text+vision+audio" },
    "context":    { "used": 1234, "limit": 8192, "l1": 3, "l2": 1, "l3": 0 },
    "preprocess": { "pendingImages": 0, "pendingAudio": 0 },
    "web":        { "providers": { } },
    "doc":        null,
    "log":        null,
    "journal":    null,
    "mem":        null,
    "sensors":    { "vision": false, "audio": false }
  }
}
```

Every key under `subsystems` is always present; its value is either an object of
already-published counters or `null` (⇒ `n/a`). The launcher polls this off its
GUI thread alongside `/health` and never blocks on a slow bridge.

Submit a turn:

```http
POST /turn/async
Content-Type: application/json
```

Payload:

```json
{
  "turn": {
    "text": "user text",
    "attachments": [],
    "kernelContext": [],
    "config": {
      "retrieval": true,
      "responseFormat": "mdx",
      "temperature": 0.2,
      "maxTokens": 2048,
      "decoding": { "timeout": 300 }
    }
  }
}
```

Immediate response:

```json
{ "accepted": true, "jobId": "turn-abc123", "state": "queued" }
```

Poll the job:

```http
GET /jobs/turn-abc123
```

Possible states:

- `queued`
- `running`
- `done`
- `error`
- `cancelled`

Cancel a turn (Stop / Escape):

```http
DELETE /jobs/turn-abc123
```

Cooperative cancellation. A queued job never starts; a running job stops
streaming deltas and transitions to `cancelled`. It is idempotent — cancelling a
finished job returns its current view. A cancelled turn writes **nothing** to
rolling memory or the chat transcript and never fabricates an answer; the kernel
emits a short `status: "cancelled"` SSE event only. Local non-streaming model
calls also obey a wall-clock deadline (`decoding.timeout`), so a runaway CPU
generation can no longer wedge the single inference slot. The Tauri shell proxies
this through the `bridge_delete` command (alongside `bridge_get`/`bridge_post`).

Done response:

```json
{
  "id": "turn-abc123",
  "state": "done",
  "result": {
    "answer": "assistant answer",
    "controls": {},
    "events": []
  }
}
```

Request live context:

```http
POST /context
```

Payloads:

```json
{ "kind": "screen", "action": "capture_screenshot" }
{ "kind": "audio", "action": "record_audio_window", "seconds": 4 }
```

Toggle observers:

```http
POST /observer
```

Payloads:

```json
{ "observer": "vision", "enabled": true }
{ "observer": "audio", "enabled": false }
```

## Reminders (§8 scheduler)

Durable reminders that fire exactly once via the cognitive tick (no model call)
and survive restarts. Storage is an append-only event log at
`memory/schedule.jsonl`, shared with the CLI (`lk remind …`).

```http
GET /reminders
```

```json
{ "ok": true,
  "reminders": [ { "id": "rem-…", "text": "stand up", "due": "2026-06-18T09:00:00+05:30",
                   "status": "pending", "created": "…", "source": "user" } ],
  "counts": { "pending": 1, "fired": 0, "done": 0, "total": 1 } }
```

```http
POST /reminders        { "op": "add", "text": "stand up", "when": "+30m" }
POST /reminders        { "op": "done", "id": "rem-…" }
DELETE /reminders/{id}
```

`when` is ISO-8601 (`2026-06-18T09:00`, naive = host local timezone) or a relative
offset `+<n>[smhd]`. A bad time returns `422` with a specific message. The badge
count must come from `/health.reminders` (backend truth), never localStorage. When
a reminder fires, the bridge marks it fired **durably first** (idempotent — no
double-fire across restarts), then emits a `context` SSE event (`kind:"reminder"`)
and an OS notification. The reminders **panel/badge** UI wiring lands with the WS-U
UI redesign; the backend it reads is complete.

## Manager Integration Shape

A future kernel/CLI manager should not block on UI work. Suggested loop:

1. Start `desktopctl.sh start` when desktop UI is enabled.
2. Poll `GET /health` or subscribe to a future event stream.
3. Accept `/turn/async` jobs into the manager's own queue.
4. Run kernel turns on the manager worker pool.
5. Expose `GET /jobs/{id}` for UI polling.
6. Route `/context` and `/observer` to the existing capture/observer lifecycle.
7. On shutdown, call `desktopctl.sh stop` or send equivalent process signals.

The manager can replace `ui_bridge.py` later. Keep the same endpoint payloads so
the Tauri popup does not need to know whether it is talking to this thin bridge
or to a full kernel/CLI manager.
