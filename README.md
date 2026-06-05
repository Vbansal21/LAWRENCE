# LAWRENCE

Local Agentic Watcher Reasoning on Edge Node Contextualizing Engine — a local-first personal assistant that watches your screen and audio, builds a rolling context of what you are doing, retrieves information proactively, and answers questions — all running entirely on your machine.

---

## What It Does

- **Watches passively.** Vision and audio observer daemons run in the background. Every few seconds they capture the screen and record a short audio window. When something significant happens (layout change, new speech) it is distilled into a compact context event.
- **Builds hierarchical memory.** Events are written to a permanent per-day event log (`memory/context-YYYY-MM-DD.log`) and to a three-tier rolling store (L1 → L2 → L3) that the model reads as working memory. As L1 fills, the model compresses the oldest events into dense L2 summaries; L2 compresses into L3. Nothing is truly dropped — it is progressively summarised across layers that together span from minutes to weeks.
- **Retrieves proactively.** After each significant sensor event, a background thread asks the model what adjacent information is worth pre-fetching, then runs DuckDuckGo search + full-page extraction and stores results in a local SQLite FTS5 database. When you ask a real question, the relevant content is already cached.
- **Answers in two passes.** When you type a question: (1) a fast analysis pass reads context + question, decides what to retrieve; (2) a response pass reads context + retrieved sources + analysis, produces a JSON answer with inline citations and a memory note.
- **Logs everything.** Every turn is written to `memory/logs/YYYY-MM-DD.jsonl`. Context events accumulate in `memory/context-YYYY-MM-DD.log` (one file per day, never trimmed). Memory is compressed hierarchically across L1→L2→L3 so nothing is truly forgotten — it is progressively summarised.
- **Journals.** At session end (or `/journal` command), the model writes a prose narrative of the day to `memory/journal/YYYY-MM-DD.md`. This is its synthesized understanding of what happened, not a raw event dump.

---

## What Actually Runs

The repository has two codebases:

| Path | Status | What it is |
| --- | --- | --- |
| `services/lk/` | **Running — use this** | Lean CLI kernel: observers, context, retrieval, LLM calls |
| `services/kernel/` | Legacy scaffold | FastAPI parallel-facet kernel, not wired to a live model |

Everything below refers to `services/lk/`.

---

## Repository Structure

```text
LAWRENCE/
├── lk.py                       # Entry point — python lk.py [flags]
├── pyproject.toml              # Package config (lk console script, optional deps)
│
├── services/lk/                # The running kernel
│   ├── cli.py                  # Main loop: arg parse, observer start, REPL, commands
│   ├── server.py               # llama-server lifecycle (start/stop/health)
│   ├── model.py                # HTTP client for llama-server (call_model, block builders)
│   ├── logger.py               # Per-day JSONL turn log (memory/logs/)
│   │
│   ├── ctx/                    # Context fabric
│   │   ├── gate.py             # Significance gate (vision_gate, audio_gate, STOPWORDS)
│   │   ├── distill.py          # Raw event → (compact, detailed) string pair
│   │   └── store.py            # ContextStore: append, trim, tail_for_model
│   │
│   ├── obs/                    # Sensor observers (daemon threads)
│   │   ├── vision.py           # Screen capture → OCR → gate → distill → store
│   │   └── audio.py            # Record → VAD → transcribe → gate → distill → store
│   │
│   ├── kernel/                 # LLM invocation
│   │   ├── prompts.py          # ANALYSIS, RESPONSE, PROACTIVE system prompts
│   │   └── invoke.py           # run_turn(), run_proactive(), TurnConfig
│   │
│   ├── retrieval/              # Perplexity-style retrieval pipeline
│   │   ├── web.py              # DDG search + parallel page fetch + trafilatura extract
│   │   ├── db.py               # SemanticDB: SQLite+FTS5, content-hash dedup, 30-day TTL
│   │   ├── ranker.py           # BM25-lite re-ranker (no external deps)
│   │   └── pipeline.py         # RetrievalPipeline: DB check → web fetch → rank → cite
│   │
│   └── ui/
│       └── connector.py        # UIConnector stub — kernel↔UI contract, WebSocket notes
│
├── memory/                     # Runtime data (created on first run)
│   ├── context-YYYY-MM-DD.log  # Compact event log — one file per day, never trimmed
│   ├── rolling-l1.jsonl        # Raw events — current session (L1, ~10K chars)
│   ├── rolling-l2.jsonl        # Model-compressed hourly summaries (L2, ~10K chars)
│   ├── rolling-l3.jsonl        # Model-compressed long-range summaries (L3, ~4K chars)
│   ├── retrieval.db            # SQLite FTS5 knowledge cache
│   ├── journal/YYYY-MM-DD.md  # Model's synthesized daily journal
│   └── logs/YYYY-MM-DD.jsonl  # Per-day turn log
│
├── models/local/               # Put your GGUF model files here
│   └── gemma-4-E4B-it-GGUF/
│       ├── gemma-4-E4B-it-Q4_K_M.gguf
│       └── mmproj-gemma-4-E4B-it-BF16.gguf
│
├── third_party/llama.cpp/      # llama.cpp checkout
│   └── build/bin/llama-server  # Must be built
│
├── apps/desktop/               # Tauri + React overlay (scaffold — not wired)
├── crates/system-hooks/        # Rust OS hooks (scaffold — not wired)
└── docs/                       # Architecture docs, paper, risk register
```

---

## How It Works Internally

### Context pipeline (every 3–4 seconds, passively)

```text
VisionObserver._tick()
  capture screen (320×180 PNG via PowerShell/scrot)
  pixel_change_score(prev, curr)
    if score < 0.04 → skip
  run_ocr(frame) via tesseract
  vision_gate(score, prev_written_ocr, curr_ocr)
    if score ≥ 0.18 → pass (significant layout change)
    else: Jaccard novelty vs last-written OCR ≥ 0.20 → pass
  distill.vision() → compact line + detailed block
  ContextStore.append() → context-YYYY-MM-DD.log + rolling-l1.jsonl
  if on_event callback → trigger proactive retrieval (background thread)

AudioObserver._tick()  [parallel, every 4 seconds]
  record_window() via arecord or ffmpeg+pulseaudio
  rms_db() VAD — skip if silence < -42 dB
  transcribe() via faster-whisper (singleton) or whisper-cli
  audio_gate(transcript, recent_transcripts)
    len ≥ 3 words AND Jaccard similarity vs last 4 transcripts < 0.60
  distill.audio() → compact + detailed
  ContextStore.append() → context-YYYY-MM-DD.log + rolling-l1.jsonl
  if on_event → trigger proactive retrieval
```

### Proactive retrieval (on every gated sensor event)

```text
_make_proactive_trigger() → non-blocking lock closure
  if lock busy → drop (at most one proactive call in flight)
  spawn daemon thread:
    run_proactive(ctx, retrieval)
      ctx.tail_for_model() → recent detailed events as string
      call_model(PROACTIVE prompt + context, max_tokens=256)
        → {needs_retrieval: bool, queries: [str]}
      if needs_retrieval: retrieval.retrieve(queries) → warms DB
```

### User turn (when you type a question)

```text
run_turn(user_text, ctx, retrieval, cfg, images, audios)
  ctx.tail_for_model()          → rolling context string

  Pass 1 — ANALYSIS (max_tokens=768)
    _build_messages(ANALYSIS, context+question, images, audios)
    call_model() → raw text → _extract_json() (finds last JSON object)
      → {situation, intent, needs_retrieval, queries[]}
    _strip_thinking() removes Gemma 4 <|channel>thought...answer blocks

  Retrieval (if needs_retrieval and queries)
    RetrievalPipeline.retrieve(queries)
      for each query: SemanticDB.search() → FTS5 BM25
      queries with 0 DB hits → search_and_fetch() (parallel DDG + page fetch)
        ddg_search() → HTML parse → real URLs
        fetch_and_chunk() in ThreadPoolExecutor → trafilatura → ~500 char chunks
      SemanticDB.upsert() → content-hash dedup, stores new chunks
      BM25-lite rank(queries, all_chunks) → top-6 CitedResult

  Pass 2 — RESPONSE (max_tokens=cfg.max_tokens, default 1024)
    _build_messages(RESPONSE, context+retrieval+situation+question, images, audios)
    call_model() → {answer_text, modalities_used, note_compact, note_full,
                    context_tags, confidence}

  distill.turn() → append to context (feeds future turns)
  write_turn() → memory/logs/YYYY-MM-DD.jsonl
  ui.push_response() → no-op in CLI mode
  return answer_text (+ citation list if sources used)
```

### Context store — hierarchical memory (L1/L2/L3)

Rather than dropping old events when the budget fills, LAWRENCE compresses them through progressive model-summarisation. Three layers cascade oldest-first into the context window:

| Layer | File | Target size | Effective span | Content |
| --- | --- | --- | --- | --- |
| L1 | `rolling-l1.jsonl` | 10K chars | 30-60 min | Raw sensor + conversation events (current session) |
| L2 | `rolling-l2.jsonl` | 10K chars | 8-20 hours | Model-compressed hourly summaries (each L2 entry ≈ 1K chars) |
| L3 | `rolling-l3.jsonl` | 4K chars | Days to a week | Model-compressed session summaries (each L3 entry ≈ 500 chars) |

When L1 exceeds its 10K budget a background thread calls the model (`COMPACT_L1` prompt) on the oldest 60% of L1 events, generating a ~300-token dense summary that becomes a new L2 entry. L1 is trimmed to the remaining 40%. The same cascade applies from L2→L3 when L2 fills.

The model always receives: `[LONG-TERM MEMORY]` (L3) → `[SESSION MEMORY]` (L2) → `[CURRENT CONTEXT]` (L1), oldest-first, totalling ≤ 24K chars — well within the 32K context window after accounting for system prompt, retrieval, question, and response space.

Without a running model (no `compact_fn`), the store falls back to naive trimming of L1 (old behaviour, no L2/L3 built).

`memory/context-YYYY-MM-DD.log` — one compact line per event, one file per calendar day, append-only, never trimmed. This is the permanent raw event log.

`memory/journal/YYYY-MM-DD.md` — the model's synthesized daily journal. Written at session exit and via `/journal`. Prose narrative: what the user worked on, what was found, what questions were asked — not a raw event log.

### LLM backend

llama-server runs as a persistent process on `127.0.0.1:8190`. The model is never reloaded between turns. HTTP calls use `timeout=None` (blocks until generation completes). With `--parallel 1`, only one request runs at a time — a proactive background call will delay the next user turn by however long generation takes (typically under 10s at 256 tokens).

---

## Requirements

### Hardware

| Component | Minimum | Recommended |
| --- | --- | --- |
| RAM | 8 GB | 16 GB |
| CPU | 4 cores | 8+ cores |
| GPU | not required | any CUDA/Metal for speed |

### Software

- Python ≥ 3.11
- llama.cpp built with `llama-server` binary (see below)
- Gemma 4 E4B GGUF model + mmproj file
- **Vision** (optional): `tesseract` for OCR; `Pillow` for pixel comparison; on WSL: `powershell.exe` available; on Linux: `scrot`
- **Audio** (optional): `arecord` (ALSA) or `ffmpeg` with PulseAudio; `faster-whisper` for transcription
- **Retrieval** (optional): `trafilatura` for clean article extraction (falls back to `<p>` regex)

### Build llama.cpp

```bash
git submodule update --init third_party/llama.cpp
cd third_party/llama.cpp
cmake -B build -DLLAMA_CURL=OFF          # CPU only
# cmake -B build -DGGML_CUDA=ON          # CUDA GPU
cmake --build build --config Release -j$(nproc) --target llama-server
```

---

## Installation

```bash
# Clone and enter
git clone <repo> LAWRENCE && cd LAWRENCE

# Create virtualenv
python -m venv .venv && source .venv/bin/activate

# Core only (stdlib — no extra deps needed for basic text Q&A)
pip install -e .

# Full optional deps (vision, audio, web extraction)
pip install -e ".[full]"
```

---

## Running

### Minimal (text-only, no observers)

```bash
python lk.py --no-vision --no-audio
```

### Standard (vision + audio observers)

```bash
python lk.py
```

### Fully autonomous (speech triggers responses automatically)

```bash
python lk.py --audio-query
```

With `--audio-query`, every significant speech segment captured by the audio observer is treated as a query. The transcript is passed to `run_turn()` in a background thread and the response is printed to the terminal as soon as it arrives — no typing required. The main loop is non-blocking so responses surface between prompts without corrupting terminal state.

Without `--audio-query`, audio speech goes into the rolling context only (passive observation). The audio observer still enriches what the model knows but does not generate responses on its own.

### Skip the analysis pass (faster, no retrieval)

```bash
python lk.py --skip-analysis
```

### Full flags

```text
--no-vision          Disable rolling screen observer
--no-audio           Disable rolling audio observer
--no-retrieval       Disable web retrieval entirely
--skip-analysis      Single-pass mode (response only, no retrieval)
--audio-query        Treat all significant audio as a query (see below)
--stop-server        Stop llama-server when you exit (default: leave it running)

--model PATH         Path to GGUF model file
--mmproj PATH        Path to mmproj GGUF file (for vision/audio)
--bin PATH           Path to llama-server binary
--ctx-size N         Context window size (default: 32768; max: 131072)
--gpu-layers N       GPU layers to offload (default: 0 / env LLAMACPP_GPU_LAYERS)
--threads N          CPU threads (default: nproc)
--max-tokens N       Max tokens for the response pass (default: 1024)
--temp FLOAT         Sampling temperature (default: 0.2)
--timeout N          Per-call timeout in seconds (default: 300)
```

---

## CLI Commands

Once inside the REPL (`you>`):

```text
text                      Send a question or statement
/screenshot [q]           Capture screen now and attach it to the next turn
/image PATH [q]           Attach an image file
/audio PATH [q]           Attach an audio file
/record SECS [q]          Record microphone for SECS seconds and attach
/vision on|off            Start or stop the rolling screen observer
/audio-on|off             Start or stop the rolling audio observer
/context                  Print memory context L1/L2/L3 (what the model will read)
/log                      Print last 30 lines of today's event log
/journal                  Write and print a journal entry for this session
/status                   Show server health, memory sizes, observer state
/clear                    Clear rolling context L1+L2+L3 (event log preserved)
/skip-retrieval           Toggle web retrieval on/off for this session
/help                     Show this list
/exit, /quit              Quit — writes session journal automatically
```

---

## Where Responses Appear

LAWRENCE has two output paths:

**1. Typed query → immediate response**
You type a question at `you>`, the main loop runs `run_turn()` synchronously, and the answer is printed inline before the next prompt.

**2. Audio-triggered response (`--audio-query`)**
The audio observer captures speech in a background thread. When a transcript passes the significance gate it is sent to `run_turn()` in a separate daemon thread. The result is pushed to an internal queue. The main loop drains that queue every 150ms and prints:

```text
[heard] what you said
LAWRENCE> the answer
you>
```

This happens without you typing anything. The terminal stays interactive — you can still type questions while audio turns run in the background. If two audio segments arrive while a turn is already in flight, the second is silently dropped (non-blocking lock).

**What never surfaces automatically (passive mode, no `--audio-query`)**
Audio goes into the L1 rolling context as context but generates no response. Proactive retrieval warms `memory/retrieval.db` silently so future queries are faster, but nothing is printed. To see what is in the context at any time, type `/context`.

## Memory Layout

All runtime files land under `memory/` in the repo root.

```text
memory/
  context-YYYY-MM-DD.log   Compact one-liner per event. One file per day. Never trimmed.
  rolling-l1.jsonl         Raw events — current session (~30-60 min, ~10K chars).
  rolling-l2.jsonl         Model-compressed hourly summaries (~8-20 hours, ~10K chars).
  rolling-l3.jsonl         Model-compressed long-range summaries (~days, ~4K chars).
  rolling-YYYYMMDD-HHMM.jsonl  Archived L1 from past idle sessions.
  retrieval.db             SQLite + FTS5. Chunks from web fetches. 30-day TTL.
  journal/
    2026-01-15.md          Model's synthesized prose journal for that day.
    2026-01-16.md
  logs/
    2026-01-15.jsonl       One line per turn: query, analysis, answer, latency.
    2026-01-16.jsonl
    ...
```

---

## UI Integration

`services/lk/ui/connector.py` defines the kernel↔UI contract. In CLI mode all methods are no-ops. To connect a desktop UI:

1. Start a WebSocket server in `UIConnector.__init__` on `ws://127.0.0.1:8765`
2. Replace each `pass` stub with `ws.send(json.dumps(...))` — envelopes are documented in the file
3. Implement `get_query()` to receive queries from the UI instead of stdin
4. The Tauri shell in `apps/desktop/` is the intended host; its build setup is scaffolded there

The kernel emits three event types toward the UI:

- `{type: "status", status: "analysing"|"retrieving"|"responding"|"idle", detail: ""}`
- `{type: "response", answer, citations, note_compact, confidence, latency_ms}`
- `{type: "context", kind: "vision"|"audio"|"turn", text: compact_line}`

---

## Deferred / Not Yet Wired

| Feature | State |
| --- | --- |
| Slow reasoning loop (draft → critique → revise) | Designed, not implemented |
| Voice output / TTS | Not implemented |
| Global hotkeys | Not implemented |
| Tauri desktop UI | Scaffold only (`apps/desktop/`) |
| Rust system hooks (screen pixel stream, audio tap, active window) | Scaffold only (`crates/system-hooks/`) |
| FastAPI parallel-facet kernel | Scaffold in `services/kernel/` — separate codebase, not connected to `lk` |

---

## License

PolyForm Noncommercial — see [LICENSE](LICENSE).
