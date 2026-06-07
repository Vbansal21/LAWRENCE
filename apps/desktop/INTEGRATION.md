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
  "modalities": "text+vision+audio",
  "observers": { "vision": false, "audio": false }
}
```

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
