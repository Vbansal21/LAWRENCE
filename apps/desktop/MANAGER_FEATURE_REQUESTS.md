# Desktop Manager Feature Requests

These requests are outside the Tauri UI boundary. The popup can send intent, but
the kernel/CLI manager should own retrieval breadth, response formatting,
conversion, privacy policy, and long-running jobs.

## MDX Response Format

The popup sends `config.responseFormat: "mdx"` on ordinary chat turns. The
manager should treat this as a response-format contract, not as a separate
button or export workflow.

Suggested turn config:

```json
{
  "responseFormat": "mdx"
}
```

Expected manager behavior:

- Ask the model for MDX-compatible Markdown on every UI turn.
- Preserve citations, code fences, tables, lists, headings, and frontmatter when useful.
- If the user asks to compact/export context, answer through the normal chat path
  in MDX rather than requiring a dedicated UI button.
- Keep raw JSX/HTML unsafe by default unless a trusted renderer is explicitly added.

## Deep Web Search Turn Flag

The popup sends `config.deepSearch: true` when the user explicitly requests a
comprehensive web search. The manager should translate that into a per-turn
retrieval profile without mutating global defaults.

Suggested config extension:

```json
{
  "deepSearch": true,
  "retrieval": true,
  "deepSearchConfig": {
    "searchDepth": "comprehensive",
    "freshPerQuery": 8,
    "topK": 18,
    "expandSources": true,
    "requireCitations": true
  }
}
```

Expected manager behavior:

- Force retrieval/web search for the turn.
- Increase source breadth and citation capture for that turn only.
- Return a visible event such as `deep-search: 12 sources considered`.
- If the current backend cannot browse, return a structured unsupported-state
  error so the UI can show that instead of silently continuing.

## Live Visual And Audio Controls

The popup already separates live context from document attachment:

- Main visual/audio buttons toggle rolling observers through `/observer`.
- `Screen now` and `Mic now` request kernel capture through `/context`.
- File/URL attachment remains document ingestion, not live capture.

The manager should preserve that distinction when it replaces
`scripts/ui_bridge.py`.

## Advanced Sampling And Agent Controls

The popup now sends a richer `config.decoding` and `config.agent` payload. The
bridge currently forwards only the fields already supported by `TurnConfig`
directly. The manager/kernel should decide which backend-specific fields are
valid for the active model and surface unsupported fields as structured warnings.

Requested decoding fields:

```json
{
  "decoding": {
    "topP": 0.95,
    "minP": 0.05,
    "typicalP": 1.0,
    "topK": 40,
    "tfsZ": 1.0,
    "epsilonCutoff": 0,
    "etaCutoff": 0,
    "mirostat": 0,
    "mirostatTau": 5,
    "mirostatEta": 0.1,
    "repeatPenalty": 1.1,
    "repeatLastN": 256,
    "presencePenalty": 0,
    "frequencyPenalty": 0,
    "dryMultiplier": 0,
    "dryBase": 1.75,
    "dryAllowedLength": 2,
    "timeoutEnabled": true,
    "timeout": 300,
    "grammarSchema": "",
    "stopSequences": []
  }
}
```

Requested agent fields:

```json
{
  "agent": {
    "toolRounds": 8,
    "toolCallLimit": 24,
    "webDepth": "Auto",
    "citationMode": "Auto"
  }
}
```

Intent:

- Keep per-turn sampler settings isolated; do not mutate global CLI defaults.
- Map supported fields to llama.cpp/OpenAI-compatible backend equivalents.
- Use `timeoutEnabled: false` as no UI-requested timeout, while still allowing
  the manager to enforce hard safety limits.
- Expose grammar/schema, logit-bias, DRY sampling, tail-free sampling, epsilon
  cutoff, eta cutoff, and Mirostat support where the backend allows it.
- Return `controls.unsupportedSampling` for ignored fields so the UI can show
  exact state instead of pretending the model used them.

## Runtime Telemetry Stream

The popup has a compact strip under the text bar for context fill, system load,
memory use, queued jobs, backend/model state, visual/audio pipeline state, and
recent transcription or pipeline events. The current desktop bridge exposes only
best-effort `/health` data and raw SSE context events.

Requested manager contract:

```json
{
  "context": {
    "used": 18200,
    "limit": 65536,
    "layers": { "l1": 4200, "l2": 9000, "l3": 5000 }
  },
  "system": {
    "cpuPercent": 24,
    "memoryPercent": 58,
    "accelerator": { "kind": "CUDA", "name": "RTX 4090", "vramPercent": 41 }
  },
  "jobs": {
    "queued": 1,
    "running": 2,
    "background": [
      { "kind": "web-search", "state": "running", "label": "retrieving sources" },
      { "kind": "doc-retrieval", "state": "queued", "label": "indexing PDF" }
    ]
  },
  "pipeline": {
    "visual": {
      "state": "active",
      "lastCaptureMs": 180,
      "changedRegions": 3,
      "ocrMs": 420,
      "preprocessMs": 95,
      "lastThumbnail": "data:image/png;base64,..."
    },
    "audio": {
      "state": "active",
      "rms": 0.03,
      "vad": "speech",
      "transcribeMs": 310,
      "partialTranscript": "..."
    }
  }
}
```

Intent:

- Let the UI reflect what the kernel is actually doing instead of showing
  placeholders.
- Keep thumbnails/transcripts privacy-aware and opt-in under the same live
  visual/audio controls.
- Expose accelerator stats only when an accelerator is detected and used by the
  active backend.
- Send incremental updates over SSE so long-running tool calls, web searches,
  document conversions, visual preprocessing, and audio transcription do not
  wait for turn completion.
