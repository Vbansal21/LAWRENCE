# LAWRENCE CLI Reference

The complete command + configuration reference for the `lk` REPL.

Start it:

```bash
python3 lk.py            # or: make run
```

Inside the REPL the prompt is `you>`. Type a question to talk to the model, or a
`/command` to control the system. Type `/help` for a short list, `/help set` for
all tunables. `DATE` arguments accept `today` (default), `yesterday`, or
`YYYY-MM-DD`.

---

## 1. Ask & attach

| Command | Description |
|---|---|
| `text` | Send a question/statement to the model (two-pass: analysis → retrieval → response). |
| `/screenshot [q]` | Capture the screen now and attach it to this turn. |
| `/image PATH [q]` | Attach an image file. |
| `/audio PATH [q]` | Attach an audio file (passed to the model as native audio). |
| `/record SECS [q]` | Record the microphone for `SECS` seconds and attach. |

Media attached to a model that lacks that modality is dropped with a notice
(capabilities come from the active [model profile](#7-server--model)).

## 2. Sensors

| Command | Description |
|---|---|
| `/vision on` / `/vision off` | Start/stop the rolling screen observer. |
| `/audio-on` / `/audio-off` | Start/stop the rolling audio observer. |
| `/obs` | Live preprocessor state: latest frame Δ-score, OCR snippet, heuristic diff, pending hi-res, poll/write rates, audio status. |

## 3. Rolling memory (L1 / L2 / L3)

The working memory the model reads every turn. L1 = raw recent events, L2 =
model-compressed session summaries, L3 = long-range summaries.

| Command | Description |
|---|---|
| `/context` | Print exactly what the model receives (L3 → L2 → L1, trimmed to the working budget). |
| `/mem info` | Layer sizes, dynamic working budget, compaction cooldown, L2/L3 budgets. |
| `/mem show [l1\|l2\|l3]` | Print one layer (no arg = all, same as `/context`). |
| `/mem clear [l1\|l2\|l3\|all]` | Wipe one layer, or everything. |
| `/mem archive` | Snapshot L1 to `rolling-YYYYMMDD-HHMM.jsonl` and truncate it — starts a fresh session. |
| `/mem export PATH` | Copy non-empty layers to a folder. |
| `/clear` | Shortcut for `/mem clear all`. |

## 4. Event & turn logs

Per-day append-only logs. The **event log** (`context-DATE.log`) is a compact
one-liner per sensor/turn event; the **turn log** (`logs/DATE.jsonl`) is the
structured record of each Q&A.

| Command | Description |
|---|---|
| `/log [N]` | Tail the last `N` lines of today's event log (default 30). |
| `/log list` | All available log dates with event-log + turn-log sizes. |
| `/log show [DATE [N]]` | View a day's event log (optionally last `N` lines). |
| `/log export PATH [DATE]` | Copy event + turn logs out (one date, or all). |
| `/log trim DATE N` | Keep only the last `N` lines of a day's event log. |
| `/log delete DATE` | Remove a day's event **and** turn logs. |

## 5. Journal (daily MDX)

The model's synthesized prose narrative of each day, written to
`memory/journal/DATE.mdx` — frontmatter (title, date, tags, entry count) plus
timestamped, titled sections. Designed to be browsed in any MDX/Markdown viewer
(Obsidian, Docusaurus, VS Code preview).

| Command | Description |
|---|---|
| `/journal` | Write a new entry for the current session and print it. |
| `/journal list` | All journal dates with entry counts. |
| `/journal show [DATE]` | View a journal (raw MDX). |
| `/journal edit [DATE]` | Open it in `$EDITOR` (falls back to nano/vim). |
| `/journal export PATH [DATE]` | Copy journal(s) out (one date, or all). |
| `/journal delete DATE` | Remove a journal file. |

A journal entry is also written automatically on clean exit (`/exit`).

## 6. Retrieval cache

| Command | Description |
|---|---|
| `/db info` | Semantic DB chunk count + on-disk size. |
| `/db clear` | Drop all cached web-retrieval chunks. |
| `/skip-retrieval` | Toggle web/DB retrieval for the session (same as `/set retrieval off`). |

## 7. Server & model

The CLI and the llama-server are decoupled — the server survives the CLI exiting,
and the CLI runs in degraded mode (no model turns) if the server is down.

| Command | Description |
|---|---|
| `/status` | Server health, memory sizes, observer state, proactive interval. |
| `/server status` | Server health + whether staged settings need a restart. |
| `/server start` | Start the server with the current (possibly staged) settings. |
| `/server stop` | Stop the server (CLI keeps running). |
| `/server restart` | Stop + start — applies staged settings and model swaps. |

**Swap models without leaving the CLI:**

```text
/set model /path/to/other-model.gguf
/set mmproj auto          # auto-detect a projector next to the model (or give a path)
/server restart           # reload; modalities (text/vision/audio) auto-detected
```

## 8. Configuration — `/config` and `/set`

`/config` prints every setting. `/set KEY VAL` changes one. Most apply
immediately ("live"); a few that control how the server is launched are
"staged" and take effect on the next `/server restart`.

### Live settings (apply immediately)

| Key | Default | Meaning |
|---|---|---|
| `max-tokens` | 2048 | Max tokens in the response pass. |
| `temp` | 0.2 | Sampling temperature. |
| `timeout` | 300 | Per-turn timeout (seconds). |
| `retrieval` | on | Web/DB retrieval on/off. |
| `analysis` | on | Analysis pre-pass on/off. |
| `retrieval-top-k` | 6 | Final ranked sources sent to the model. |
| `retrieval-fresh` | 3 | Web results fetched per query. |
| `retrieval-db-min` | 3 | Min DB hits before hitting the web. |
| `vision-high` | 0.50 | Pixel-Δ at/above which a frame is always written. |
| `vision-pixel-min` | 0.10 | Pixel-Δ below which a frame is skipped. |
| `vision-novelty-min` | 0.30 | OCR Jaccard-distance required between min and high. |
| `vision-interval` | 10 | Screen poll interval (seconds); patches a running observer. |
| `vision-write-min` | 60 | Min seconds between context writes; patches a running observer. |
| `audio-min-words` | 3 | Minimum words for speech to pass the gate. |
| `audio-dedup-max` | 0.60 | Jaccard-similarity ceiling before a segment is dropped as duplicate. |
| `proactive-interval` | 600 | Minimum seconds between proactive retrieval calls. |
| `proactive-present` | on | Surface findings unprompted (cards) vs. only warm the cache silently. |
| `compact-min` | 300 | Minimum seconds between memory compaction runs. |
| `l2-budget` | 10000 | L2 chars before L2→L3 compaction. |
| `l3-budget` | 4000 | L3 chars before oldest entries drop. |

### Staged settings (need `/server restart`)

| Key | Default | Meaning |
|---|---|---|
| `model` | (launch flag) | Path to the GGUF model file. |
| `bin` | (launch flag) | Path to the `llama-server` binary. |
| `mmproj` | auto | Multimodal projector path, or `auto` to detect next to the model. |
| `ctx` | 65536 | Context window (tokens) — the KV-cache ceiling. |
| `threads` | 9 | Inference threads. |
| `gpu-layers` | 0 | Layers offloaded to GPU (0 = CPU only). |
| `kv-type` | q4_0 | KV-cache type: `q4_0` / `q8_0` / `f16` / `none`. |
| `flash-attn` | on | Flash attention: `on` / `off` / `auto`. |
| `jinja` | on | Use the model's embedded chat template. |

> Quantized KV (`q4_0`/`q8_0`) requires flash attention. If you set
> `flash-attn off` with a quantized KV type, the profile drops the KV
> quantization rather than override your explicit choice.

## 9. Session

| Command | Description |
|---|---|
| `/help` | Short command list. |
| `/help set` | All `/set` keys. |
| `/exit`, `/quit` | Quit. Writes a journal entry automatically; the server stays alive. |

---

## Launch flags

Settable at start (most map to a `/set` key you can also change live):

```text
--no-vision        Don't start the screen observer
--no-audio         Don't start the audio observer
--no-retrieval     Disable retrieval for the session
--skip-analysis    Single-pass mode (no analysis, no retrieval)
--audio-query      Treat every gated speech segment as a query (autonomous)
--stop-server      Stop llama-server on exit (default: leave it running)

--model PATH       GGUF model file
--mmproj PATH      Projector GGUF (default: auto-detect next to --model)
--bin PATH         llama-server binary
--ctx-size N       Context window (default 65536)
--ingest-spool [DIR]  Ingest events from an out-of-process sensor (default memory/spool)
--gpu-layers N     GPU offload layers (default 0 / $LLAMACPP_GPU_LAYERS)
--threads N        Inference threads (default 9)
--max-tokens N     Response-pass max tokens (default 2048)
--temp FLOAT       Temperature (default 0.2)
--timeout N        Per-call timeout seconds (default 300)
```

## The autonomous loop

With observers running, LAWRENCE works without being asked:

1. **Capture** — vision/audio observers run as daemon threads and write gated,
   distilled events to the event log + rolling memory autonomously.
2. **Retrieve** — each significant event triggers a rate-limited background pass
   that decides what's worth pre-fetching and warms the retrieval DB.
3. **Surface** — when a finding is genuinely worth your attention, it is presented
   unprompted as a card (and a desktop notification):

   ```text
   ╭─ ⚡ LAWRENCE noticed ───────────────────────────────────────────────
   │ <headline>
   │
   │ <1-3 sentence insight with [N] citations>
   │ [1] Source title — https://…
   ╰─────────────────────────────────────────────────────────────────────
   ```

Tune it: `/set proactive-interval N` (cadence), `/set proactive-present off`
(warm cache silently, no cards), `/set proactive-present on` (default).

## Out-of-process sensors (headless / Docker)

Capture + preprocessing can run as a **separate process** so vision/audio keep
working when the kernel is headless. The sensor writes events to a spool dir; the
kernel ingests them.

```bash
# on a host with screen + mic (writes events to a shared spool):
python3 lk_sensor.py --spool memory/spool
#   options: --no-vision --no-audio --vision-interval N --vision-write-min N

# the kernel (can be headless / in a container) ingests them:
python3 lk.py --no-vision --no-audio --ingest-spool memory/spool
```

The spool is just a directory of atomic JSON files — share it via a mounted
volume between host and container. The kernel applies the same proactive loop to
ingested events as to local ones.

## Running detached (tmux)

The CLI is normally run inside a tmux session so it survives terminal close; the
server survives the CLI either way.

```bash
# create a detached session and launch
tmux -S /tmp/lk-tmux new-session -d -s lawrence -x 220 -y 50
tmux -S /tmp/lk-tmux send-keys -t lawrence "cd /path/to/LAWRENCE && python3 lk.py" Enter

# attach / detach
tmux -S /tmp/lk-tmux attach -t lawrence      # attach
#   (detach from inside with: Ctrl-b then d)
tmux -S /tmp/lk-tmux ls                       # list
tmux -S /tmp/lk-tmux kill-session -t lawrence # stop CLI (server keeps running)
```

From Windows (WSL2 forwards localhost), attach via:

```powershell
wsl.exe -d Ubuntu -- bash -lic "tmux -S /tmp/lk-tmux attach -t lawrence"
```

or talk to the server directly: `curl.exe http://127.0.0.1:8190/health`.
