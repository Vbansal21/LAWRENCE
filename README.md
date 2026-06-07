# LAWRENCE

Local Agentic Watcher Reasoning on Edge Node Contextualizing Engine — a local-first personal assistant that watches your screen and audio, builds a rolling context of what you are doing, retrieves information proactively, and answers questions — all running entirely on your machine.

---

## What It Does

- **Watches passively.** Vision and audio observer daemons run in the background. A cheap low-res frame every ~10s decides whether anything changed; if so a full-resolution frame is captured and **segmented into windows** — each window/section is OCR'd separately, tracked across frames with EMA-smoothed bounding boxes, and only re-read when its pixels actually change. A short audio window is sampled every ~4s. Heuristic gates keep noise out — only meaningful changes are written.
- **Builds hierarchical memory.** Events are written to a permanent per-day event log (`memory/context-YYYY-MM-DD.log`) and to a three-tier rolling store (L1 → L2 → L3) that the model reads as working memory. As L1 fills, the model compresses the oldest events into dense L2 summaries; L2 compresses into L3. Nothing is truly dropped — it is progressively summarised across layers that span minutes to weeks.
- **Retrieves and surfaces proactively.** After a significant sensor event, a background thread decides what adjacent information is worth pre-fetching, runs DuckDuckGo search + full-page extraction, and caches results in a local SQLite FTS5 database. When something is genuinely worth your attention it is **presented unprompted** as a finding card (+ desktop notification) — not just silently cached. This is the core loop: realize context → retrieve → present, without being asked. (`/set proactive-present off` to keep it silent.)
- **Answers in two passes.** When you type a question: (1) a fast analysis pass reads context + question and decides what to retrieve; (2) a response pass reads context + retrieved sources + analysis and produces a JSON answer with inline citations and a memory note. Retrieval is progressive — snippet previews first, full text only when the model asks (`expand_sources`).
- **Journals.** At session end (or `/journal`), the model writes a structured narrative of the session to `memory/journal/YYYY-MM-DD.mdx` — frontmatter (title, date, tags, entry count) plus a summary callout, highlights, topic pills, and collapsible open-threads per timestamped entry. Rich in MDX viewers (Docusaurus/Nextra/Obsidian), readable as plain Markdown anywhere.
- **Is model-agnostic.** A capability profile auto-detects modalities (text / vision / audio), projector, KV type, and flash-attention from the model files, so swapping GGUF models needs no code changes — even live, via `/set model … ; /server restart`. The model can also be a **remote OpenAI-compatible API** instead of the local llama-server (`--api-base` / `$LK_API_BASE`).
- **Is fully steerable at runtime.** Every data-stream knob (gate thresholds, observer rates, memory budgets, retrieval depth, proactive cadence) is configurable live from the CLI with `/set`. The LLM is the most replaceable part; the scripts and heuristics that shape the data streams are directly controllable.

---

## Architecture at a Glance

Two decoupled processes:

```text
┌──────────────────────────────┐         ┌────────────────────────────┐
│  lk CLI  (python3 lk.py)     │  HTTP   │  llama-server              │
│  observers · memory ·        │ ──────► │  127.0.0.1:8190            │
│  retrieval · kernel · REPL   │ ◄────── │  (own session; survives    │
└──────────────────────────────┘         │   the CLI exiting)         │
                                          └────────────────────────────┘
```

The CLI spawns the server but in its **own session**, so the server stays warm
when the CLI restarts, and the CLI runs in **degraded mode** (no model turns,
everything else works) if the server is down. `/server start|stop|restart`
controls it without leaving the REPL.

---

## Repository Structure

```text
LAWRENCE/
├── lk.py                       # Entry point — python3 lk.py [flags]
├── lk_sensor.py                # Out-of-process sensor agent launcher (headless/Docker)
├── Makefile                    # make run | lint | test | help
├── pyproject.toml              # Package config (lk console script, optional deps)
│
├── services/lk/                # The running kernel
│   ├── cli.py                  # Main loop: args, observers, REPL, all commands
│   ├── server.py               # llama-server lifecycle (start/stop/restart/health)
│   ├── profile.py              # ModelProfile.detect() — model-agnostic capabilities
│   ├── model.py                # HTTP client for llama-server (call_model, blocks)
│   ├── admin.py                # Memory admin: journal MDX writer, log/journal ops
│   ├── sensor.py               # Standalone out-of-process sensor agent (python3 lk_sensor.py)
│   ├── logger.py               # Per-day JSONL turn log (memory/logs/)
│   │
│   ├── ctx/                    # Context fabric
│   │   ├── gate.py             # Significance gates (live-tunable gate_config)
│   │   ├── distill.py          # Raw event → (compact, detailed) pair
│   │   └── store.py            # ContextStore: L1/L2/L3, dynamic budget, layer ops
│   │
│   ├── obs/                    # Sensor observers (daemon threads)
│   │   ├── vision.py           # Low-res gate → full-res → per-window OCR → store
│   │   ├── regions.py          # Window-rect providers + RegionTracker (IoU+EMA)
│   │   ├── audio.py            # Record → VAD → transcribe → gate → distill → store
│   │   └── spool.py            # SpoolWriter/Reader — decoupled (out-of-process) capture
│   │
│   ├── kernel/                 # LLM invocation
│   │   ├── prompts.py          # ANALYSIS / RESPONSE / PROACTIVE(/_BRIEF) / COMPACT / JOURNAL
│   │   └── invoke.py           # run_turn(), run_proactive() (+surfacing), compaction, journal
│   │
│   ├── retrieval/              # Perplexity-style retrieval pipeline
│   │   ├── web.py              # DDG search + parallel fetch + trafilatura extract
│   │   ├── db.py               # SemanticDB: SQLite+FTS5, hash dedup, 30-day TTL
│   │   ├── ranker.py           # BM25-lite re-ranker (no external deps)
│   │   └── pipeline.py         # DB check → web fetch → rank → cite (live-tunable)
│   │
│   └── ui/connector.py         # UIConnector stub — kernel↔UI contract
│
├── memory/                     # Runtime data (created on first run)
│   ├── context-YYYY-MM-DD.log  # Compact event log — one file per day, never trimmed
│   ├── rolling-l1.jsonl        # Raw events — current session (L1)
│   ├── rolling-l2.jsonl        # Model-compressed session summaries (L2)
│   ├── rolling-l3.jsonl        # Model-compressed long-range summaries (L3)
│   ├── rolling-YYYYMMDD-HHMM.jsonl  # Archived L1 from past idle sessions
│   ├── retrieval.db            # SQLite + FTS5 knowledge cache
│   ├── journal/YYYY-MM-DD.mdx  # Model's synthesized daily journal (MDX)
│   └── logs/YYYY-MM-DD.jsonl   # Per-day structured turn log
│
├── models/local/               # Put your GGUF model + mmproj here
├── third_party/llama.cpp/      # llama.cpp checkout (build llama-server)
└── docs/                       # CLI.md, ARCHITECTURE.md, OPERATIONS.md, paper, …
```

> See **[docs/CLI.md](docs/CLI.md)** for the complete command + configuration reference.

---

## How It Works Internally

### Context pipeline (passive, background)

```text
VisionObserver._tick()              [every ~10s]
  capture low-res 640×360            (cheap "did anything change?" gate)
  pixel_change_score(prev, curr)
    if score < vision-pixel-min (0.10) → skip
  ── useful change → full read, per window ─────────────────────────────────
  capture_fullres()                  (native, DPI-aware, full virtual screen)
  screen_windows()                   (OS window rects: PowerShell / wmctrl)
  RegionTracker.update(rects)        (stable ids + EMA-smoothed boxes, occluded
                                      windows deduped, top-to-bottom ordering)
  per region: crop → change-sig → OCR only if changed (>= region-change-min)
              else reuse the region's cached text
  combine → "[Window Title]\n<text>" blocks
  ── whole-screen OCR is the fallback when no window source / no Pillow ─────
  vision_gate(score, prev_written, combined_text)
    score ≥ vision-high (0.50) → pass;  else OCR novelty ≥ 0.30 → pass
  rate-limit: ≥ vision-write-min (60s) since last write
  distill.vision() → ContextStore.append() → context-DATE.log + rolling-l1.jsonl
  if on_event → trigger proactive retrieval (rate-limited)

AudioObserver._tick()               [every ~4s, parallel]
  record 4s window (arecord / ffmpeg+pulse)
  rms_db() VAD — skip if quieter than -42 dB
  transcribe() via faster-whisper ("base", int8) or whisper-cli
  audio_gate(transcript, recent)
    ≥ audio-min-words (3) AND Jaccard vs recent < audio-dedup-max (0.60)
  distill.audio() → ContextStore.append()
```

### User turn

```text
run_turn(user_text, ctx, retrieval, cfg, images, audios)
  ctx.tail_for_model()                  → L3→L2→L1, trimmed to working budget

  Pass 1 — ANALYSIS (max_tokens=768)
    call_model(ANALYSIS, context+question[+media]) → {situation, intent,
      needs_retrieval, queries[], capture_hires}

  Retrieval (if needed)  — progressive
    RetrievalPipeline.retrieve(queries)
      DB check (FTS5 BM25) → web fetch for misses (DDG + trafilatura)
      store new chunks (hash dedup) → BM25-lite rank → top-k snippets
    response pass sees previews; expand_sources:[N] pulls full text on a 2nd pass

  Pass 2 — RESPONSE (max_tokens=2048)
    call_model(RESPONSE, context+sources+situation+question) → {answer_text,
      modalities_used, note_compact, note_full, context_tags, confidence,
      expand_sources?, controls?}

  distill.turn() → ContextStore.append()   (feeds future turns)
  write_turn() → memory/logs/DATE.jsonl
  note_compact → rolling terminal narrative
```

### Autonomous loop (no user input)

```text
on a gated sensor event (rate-limited by proactive-interval):
  run_proactive(ctx, retrieval, present_fn)
    Pass A — PROACTIVE (max_tokens=512)
      call_model(PROACTIVE, context) → {needs_retrieval, queries[]}
    retrieve(queries) → warm the semantic DB (silent)
    if proactive-present and results:
      Pass B — PROACTIVE_BRIEF (max_tokens=1024)
        call_model(PROACTIVE_BRIEF, context+snippets) → {surface, headline, insight}
        if surface:
          present a finding card + desktop notification     ← presented unprompted
          ContextStore.append(kind="finding")               ← remembered, not repeated
```

This is the "realize context → retrieve → present" loop that runs without you
asking. `/set proactive-present off` reverts to silent cache-warming.

The model may also emit `controls: {vision, audio}` to start/stop/upgrade sensors
itself, and `capture_hires` to request a high-res frame for the response pass.

### Hierarchical memory (L1 / L2 / L3)

Rather than dropping old events, LAWRENCE compresses them through progressive
model-summarisation. Three layers cascade oldest-first into the context window:

| Layer | File | Role |
|---|---|---|
| L1 | `rolling-l1.jsonl` | Raw sensor + conversation events (current session) |
| L2 | `rolling-l2.jsonl` | Model-compressed session summaries |
| L3 | `rolling-l3.jsonl` | Model-compressed long-range summaries |

When L1 exceeds 70% of the **dynamic working budget**, a background thread calls
the model (`COMPACT_L1`) on the oldest ~60% of L1, producing a dense L2 entry and
trimming L1. The same cascade runs L2→L3 when L2 passes `l2-budget`. A 5-minute
cooldown (`compact-min`) prevents compaction storms.

**Dynamic working budget:** the injected context grows as fresh activity
accumulates (toward ~80K chars) and decays back toward a floor (~8K chars) after
the session goes idle, recovering immediately on new activity. The fixed 32K-token
KV cache is the ceiling it flexes within.

The model always receives `[LONG-TERM MEMORY]` (L3) → `[SESSION MEMORY]` (L2) →
`[CURRENT CONTEXT]` (L1), oldest-first. Without a running model the store falls
back to naive L1 trimming (no L2/L3 built).

### Model-agnostic profile

`profile.ModelProfile.detect()` builds the server launch config from the model
files + environment, so any GGUF runs with sensible defaults:

- modalities (vision/audio) ← presence of an `mmproj*.gguf` next to the model
- `--mmproj`, `--flash-attn`, `--cache-type-k/v`, `--jinja`, `--ctx-size` ← profile
- env overrides: `LK_VISION`, `LK_AUDIO`, `LK_KV_TYPE`, `LK_FLASH_ATTN`, `LK_JINJA`, `LK_CTX_SIZE`
- safety: quantized KV requires flash attention (else KV quantization is dropped)

Swap models live: `/set model PATH` → `/set mmproj auto` → `/server restart`.

### LLM backend

Two interchangeable backends behind one client ([model.py](services/lk/model.py)):

- **local** (default) — llama-server runs as a persistent process on
  `127.0.0.1:8190`; the model is never reloaded between turns. Requests send
  `cache_prompt: true` so the KV cache is reused when the prefix matches. With
  `--parallel 1`, one request runs at a time — a proactive call briefly delays
  the next turn.
- **api** — any external OpenAI-compatible endpoint (OpenAI, OpenRouter, Together,
  vLLM, LM Studio, …). Enable with `--api-base URL --api-model NAME [--api-key KEY]`
  or the env vars `LK_API_BASE` / `LK_API_MODEL` / `LK_API_KEY`. The local server
  is not started; `/server` reports the external endpoint, and `/set api-model`
  switches model live. Modalities for the API backend come from `LK_VISION` /
  `LK_AUDIO` (default text-only).

```bash
# use a hosted model instead of the local one
python3 lk.py --api-base https://api.openai.com/v1 --api-model gpt-4o-mini --api-key "$OPENAI_API_KEY"
# or via env
LK_API_BASE=https://openrouter.ai/api/v1 LK_API_MODEL=anthropic/claude-3.5-sonnet LK_API_KEY=… python3 lk.py
```

---

## Requirements

### Hardware

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB |
| CPU | 4 cores | 8+ cores |
| GPU | not required | any CUDA/Metal for speed (set `gpu-layers`) |

### Software

- Python ≥ 3.11 (core path is **stdlib-only**)
- llama.cpp built with the `llama-server` binary
- A GGUF model (+ `mmproj` file for vision/audio)
- **Vision** (optional): `tesseract` (OCR); `Pillow` (pixel diff); WSL → `powershell.exe`; Linux → `scrot` (+ `imagemagick`)
- **Audio** (optional): `arecord` (ALSA) or `ffmpeg`+PulseAudio; `faster-whisper`
- **Retrieval** (optional): `trafilatura` (falls back to a `<p>` regex extractor)

### Build llama.cpp

```bash
git submodule update --init third_party/llama.cpp
cd third_party/llama.cpp
cmake -B build -DLLAMA_CURL=OFF          # CPU only
# cmake -B build -DGGML_CUDA=ON          # CUDA GPU
cmake --build build --config Release -j"$(nproc)" --target llama-server
```

---

## Installation

```bash
git clone <repo> LAWRENCE && cd LAWRENCE
python -m venv .venv && source .venv/bin/activate

pip install -e .            # core (stdlib only — text Q&A works)
pip install -e ".[full]"    # + vision, audio, web extraction
```

---

## Running

```bash
# Most common — vision on, audio off (audio needs ALSA/PulseAudio + mic)
python3 lk.py --no-audio

# Text-only, no sensors
python3 lk.py --no-vision --no-audio

# Use a remote model instead of the local server
python3 lk.py --api-base https://api.openai.com/v1 --api-model gpt-4o-mini --api-key "$OPENAI_API_KEY"
```

**Detached (recommended)** — survives terminal close, server stays warm:

```bash
tmux -S /tmp/lk-tmux new-session -d -s lawrence -x 220 -y 50
tmux -S /tmp/lk-tmux send-keys -t lawrence "cd $(pwd) && python3 lk.py --no-audio" Enter
tmux -S /tmp/lk-tmux attach -t lawrence       # attach  (detach: Ctrl-b d)
```

See **[docs/CLI.md](docs/CLI.md)** for the full operations guide: start/stop/attach/detach, all launch flags, live configuration, and memory management.

### Running detached (tmux)

The CLI is typically run inside tmux so it survives terminal close; the server
survives the CLI either way (it runs in its own session).

```bash
tmux -S /tmp/lk-tmux new-session -d -s lawrence -x 220 -y 50
tmux -S /tmp/lk-tmux send-keys -t lawrence "cd $(pwd) && python3 lk.py" Enter
tmux -S /tmp/lk-tmux attach -t lawrence       # attach (detach: Ctrl-b d)
tmux -S /tmp/lk-tmux kill-session -t lawrence # stop CLI (server keeps running)
```

From Windows (WSL2 forwards localhost):

```powershell
wsl.exe -d Ubuntu -- bash -lic "tmux -S /tmp/lk-tmux attach -t lawrence"
curl.exe http://127.0.0.1:8190/health        # or talk to the server directly
```

---

## CLI Commands (summary)

Full reference: **[docs/CLI.md](docs/CLI.md)**. In-REPL: `/help`, `/help set`.

```text
ask        text · /screenshot · /image · /audio · /record
sensors    /vision on|off · /audio-on|off · /obs
memory     /context · /mem (info|show|clear|archive|export) · /clear
logs       /log (tail|list|show|export|trim|delete)
journal    /journal (write|list|show|edit|export|delete)
retrieval  /db info|clear · /skip-retrieval
control    /status · /config · /set KEY VAL · /server start|stop|restart|status
session    /help · /help set · /exit
```

### Managing the three memories

All three kinds are inspectable, exportable, trimmable, and deletable:

| Memory | Inspect | Export | Trim / clear | Delete |
|---|---|---|---|---|
| **Rolling** (L1/L2/L3) | `/mem show`, `/context` | `/mem export PATH` | `/mem clear [l1\|l2\|l3\|all]`, `/mem archive` | — |
| **Logs** (event + turn) | `/log show`, `/log list` | `/log export PATH` | `/log trim DATE N` | `/log delete DATE` |
| **Journal** (MDX) | `/journal show`, `/journal list` | `/journal export PATH` | — | `/journal delete DATE` |

Journals are also editable in place: `/journal edit [DATE]` opens `$EDITOR`.

---

## Deployment & Portability

The core kernel is pure Python (stdlib) with paths relative to the repo root, so
it runs anywhere Python ≥ 3.11 and a `llama-server` binary are available. Sensor
and notification integrations are **optional and degrade gracefully** — if a tool
or device is missing, that capability is simply skipped, never fatal.

| Environment | Text Q&A | Vision (screen) | Audio (mic) | Notes |
|---|---|---|---|---|
| **WSL2** (current) | ✅ | ✅ via `powershell.exe` | ✅ via ALSA/PulseAudio | localhost forwards to Windows |
| **Native Linux (desktop)** | ✅ | ✅ via `scrot` (X11) | ✅ via `arecord`/`ffmpeg` | Wayland needs a grim/wlroots shim |
| **macOS** | ✅ | ⚠️ no capture backend wired | ⚠️ needs an `ffmpeg`/avfoundation shim | server + text path work as-is |
| **Docker (headless)** | ✅ | ✅ via host sensor agent | ✅ via host sensor agent | see "Keeping sensors in Docker" below |
| **Headless VM / SSH** | ✅ | ➖ host sensor agent | ➖ host sensor agent | or `--no-vision --no-audio` |

### Docker / headless

A container needs: Python 3.11+, the `llama-server` binary (build in the image or
mount it), and a model under `models/local/` (mount as a volume — model files are
gitignored and large). The server binds `127.0.0.1:8190`; expose or proxy it if
needed. Mount `memory/` as a volume to persist context, logs, journals, and the
retrieval DB. Optionally add `tesseract`/`trafilatura` for OCR + clean extraction.

Text-only (no sensors):

```bash
python3 lk.py --no-vision --no-audio
```

### Keeping sensors in Docker (out-of-process sensor agent)

Screen/microphone capture can't run inside a typical headless container — but it
doesn't have to. The capture + preprocessing stage is **decoupled from the
kernel**: run it as a separate `lk.sensor` process on a machine that *does* have
a screen/mic (the host), and have it write gated, distilled events to a spool
directory that the containerized kernel ingests over a shared volume.

```bash
# on the host (has screen + mic) — pure preprocessing, no model/server:
python3 lk_sensor.py --spool /shared/spool

# in the container (headless kernel) — ingests host-captured events:
python3 lk.py --no-vision --no-audio --ingest-spool /shared/spool
```

The spool is atomic JSON files; the kernel applies the same proactive loop to
ingested events as to local ones. Only desktop notifications are unavailable in
the container (the host sensor doesn't notify; the kernel's cards still print).

### Configuration via environment

Useful for non-interactive / container starts (see `profile.py`):

```text
LLAMACPP_GPU_LAYERS   GPU offload layers (default 0)
LK_CTX_SIZE           context window (default 65536)
LK_KV_TYPE            q4_0 | q8_0 | f16 | none
LK_FLASH_ATTN         on | off | auto
LK_VISION / LK_AUDIO  force a modality on/off (default: from mmproj presence)
LK_JINJA              embedded chat template on/off
EDITOR                editor for /journal edit
# external API backend (selects the "api" model backend when LK_API_BASE is set)
LK_API_BASE           OpenAI-compatible base URL (e.g. https://api.openai.com/v1)
LK_API_KEY            bearer token
LK_API_MODEL          model name to request
```

---

## UI Integration

`services/lk/ui/connector.py` defines the kernel↔UI contract; in CLI mode all
methods are no-ops. The kernel emits three event types toward a UI:

- `{type: "status", status: "analysing"|"retrieving"|"responding"|"idle", detail}`
- `{type: "response", answer, citations, note_compact, confidence, latency_ms}`
- `{type: "context", kind: "vision"|"audio"|"turn", text}`

The Tauri popup lives in `apps/desktop/`. It is intentionally a small
Raycast-style input surface: transcript fade, one input bar, kernel-context
controls, document attachment classification, and expandable config.

The desktop UI uses `apps/desktop/scripts/ui_bridge.py`, a thin HTTP bridge that
imports the existing `services/lk` kernel modules and calls the working kernel
paths without changing kernel code.

Desktop setup:

```bash
cd apps/desktop
npm run bootstrap      # Rust/npm setup + dependency doctor
npm run deps:system    # interactive sudo: Ubuntu GTK/WebKit/pkg-config packages
npm run popup          # native Ctrl+Shift+L popup plus bridge
```

Useful non-native checks:

```bash
cd apps/desktop
npm run dev:web        # static preview on http://127.0.0.1:${PORT:-1423}
npm run bridge         # UI bridge on http://127.0.0.1:${LK_UI_PORT:-8765}
npm run popup:status   # popup/bridge status
npm run popup:restart  # restart after config or hotkey changes
npm run stress         # DOM-level UI stress test
npm run doctor         # dependency report
```

In WSL/Docker-style setups, the UI should talk to the kernel over the configured
kernel URL instead of assuming the Python kernel runs inside the Tauri process.
The async manager-facing bridge contract is in `apps/desktop/INTEGRATION.md`.

---

## Deferred / Not Yet Wired

| Feature | State |
|---|---|
| Slow reasoning loop (draft → critique → revise) | Designed, not implemented |
| Voice output / TTS | Not implemented |
| Global hotkeys | Implemented in the Tauri popup; default `Ctrl+Shift+L` |
| Tauri desktop UI | Popup and desktop bridge in `apps/desktop/`; manager-side deep search/MDX response contracts still pending |
| Rust system hooks (pixel stream, audio tap, active window) | Scaffold only (`crates/system-hooks/`) |
| macOS / Wayland screen-capture backends | Not wired |

---

## License

PolyForm Noncommercial — see [LICENSE](LICENSE).
