# LAWRENCE — Cheatsheet

---

## Three things run. Know them.

```
llama-server    port 8190    the model — stays alive when CLI exits
lk CLI          REPL         observers, memory, answers — attach via tmux
ui-bridge       port 8765    optional desktop popup backend
```

The server and CLI are decoupled on purpose. Restart the CLI; the model doesn't reload.

---

## Start

```bash
# Recommended — detached, survives terminal close
tmux -S /tmp/lk-tmux new-session -d -s lawrence -x 220 -y 50
tmux -S /tmp/lk-tmux send-keys -t lawrence "cd /home/user/LAWRENCE && python3 lk.py --no-audio" Enter

# Or just run it directly (exits when terminal closes, server lives on)
python3 lk.py --no-audio

# Text only, no observers
python3 lk.py --no-vision --no-audio

# Remote model (no local server)
python3 lk.py --api-base https://api.openai.com/v1 --api-model gpt-4o-mini --api-key "$OPENAI_API_KEY"
```

---

## Attach / detach

```bash
tmux -S /tmp/lk-tmux attach -t lawrence    # attach
Ctrl-b  d                                   # detach (stays running)
tmux -S /tmp/lk-tmux ls                    # list sessions

# From Windows PowerShell:
wsl.exe -d Ubuntu -- bash -lic "tmux -S /tmp/lk-tmux attach -t lawrence"
```

---

## Stop

```bash
# Inside the CLI:
/exit                      # quit CLI, write journal, server stays running
/server stop               # stop server only, CLI keeps running

# From outside:
tmux -S /tmp/lk-tmux kill-session -t lawrence        # kill CLI
kill $(pgrep -f llama-server)                         # kill server
kill $(pgrep -f ui_bridge)                            # kill bridge

# Kill everything at once:
tmux -S /tmp/lk-tmux kill-session -t lawrence 2>/dev/null; kill $(pgrep -f "llama-server|ui_bridge") 2>/dev/null
```

---

## Check what's running

```bash
# From outside:
ps aux | grep -E "(llama-server|lk\.py|ui_bridge)" | grep -v grep
curl http://127.0.0.1:8190/health    # server alive?
curl http://127.0.0.1:8765/health    # bridge alive?

# From inside the CLI:
/status    # server health, memory sizes, observer state
/obs       # live sensor readings
```

---

## Swap model (no restart of CLI)

```
/set model /path/to/model.gguf
/set mmproj auto
/server restart
```

---

## Commands inside the REPL

```
any text           ask a question
/screenshot [q]    grab screen now, attach to this turn
/record SECS [q]   record mic for N seconds, attach

/vision on|off     start/stop screen observer
/audio-on|off      start/stop audio observer
/obs               live sensor state

/status            overall health
/config            all settings
/set KEY VAL       change a setting (see below)
/server restart    apply staged model/ctx changes

/context           what the model reads this turn (L3→L2→L1)
/mem info          memory layer sizes
/mem clear all     wipe rolling memory
/mem archive       snapshot + start fresh

/log               tail today's event log
/journal           write + print today's journal

/db clear          wipe retrieval cache
/help set          list all /set keys
/exit              quit
```

---

## /set — everything you can change live

**Inference**
```
max-tokens   2048      response length cap
temp         0.2       randomness
timeout      300       per-turn timeout (seconds)
retrieval    on|off    web/DB retrieval
analysis     on|off    analysis pre-pass
```

**Advanced sampling** (None = backend default)
```
top-p        0.95      nucleus sampling cutoff
min-p        0.05      minimum probability floor
top-k        40        top-K token cutoff
repeat-penalty  1.1   penalty for repeated tokens
presence-penalty  0   penalise tokens already present
frequency-penalty 0   penalise frequent tokens
seed         random    fixed seed for reproducibility (integer or 'off')
stop         (none)    comma-separated stop sequences, or 'clear'
```

**Vision**
```
vision-regions      on     per-window OCR vs whole-screen
vision-interval     10     poll every N seconds
vision-write-min    60     min seconds between context writes
vision-pixel-min    0.10   skip frame if pixel-Δ below this
vision-high         0.50   always write frame if pixel-Δ above this
vision-novelty-min  0.30   OCR novelty required in the middle range
region-ema          0.4    box smoothing (higher = snappier)
region-change-min   0.06   pixel change needed to re-OCR a window
```

**Audio**
```
audio-min-words    3       min words to pass speech gate
audio-dedup-max    0.60    Jaccard ceiling to drop duplicate speech
```

**Proactive**
```
proactive-interval  600    seconds between background retrieval runs
proactive-present   on     surface finding cards (off = silent)
```

**Memory**
```
compact-min   300    min seconds between compaction runs
l2-budget     10000  L2 chars before L2→L3 compaction
l3-budget     4000   L3 chars before oldest L3 entries drop
```

**Retrieval**
```
retrieval-top-k   6   sources sent to model
retrieval-fresh   3   web results per query
retrieval-db-min  3   min DB hits before going to web
```

**Staged** — need `/server restart`
```
model        path to GGUF
mmproj       path to projector GGUF, or 'auto'
ctx          65536    context window tokens
threads      9        inference threads
gpu-layers   0        GPU offload layers
kv-type      q4_0     q4_0 | q8_0 | f16 | none
flash-attn   on       on | off | auto
jinja        on       embedded chat template
```

---

## Memory — three kinds

| Kind | Files | Inspect | Clear/trim | Export |
|---|---|---|---|---|
| Rolling (L1/L2/L3) | `memory/rolling-*.jsonl` | `/context`, `/mem show` | `/mem clear [l1\|l2\|l3\|all]` | `/mem export PATH` |
| Event logs | `memory/context-DATE.log` | `/log show [DATE]` | `/log trim DATE N` | `/log export PATH` |
| Journal (MDX) | `memory/journal/DATE.mdx` | `/journal show [DATE]` | `/journal delete DATE` | `/journal export PATH` |

---

## Desktop UI bridge

```bash
python3 apps/desktop/scripts/ui_bridge.py          # start on port 8765
LK_UI_PORT=8765 python3 apps/desktop/scripts/ui_bridge.py
curl http://127.0.0.1:8765/health                  # check it
```

The bridge handles: kernel capture requests (`/screenshot`, `/record`), observer toggles (vision/audio on/off), full document attachment conversion (PDF, DOCX, HTML, CSV, EPUB, video, …), and all advanced sampling parameters from the UI.

---

## Out-of-process sensors (Docker)

```bash
# host with screen + mic:
python3 lk_sensor.py --spool memory/spool

# headless kernel:
python3 lk.py --no-vision --no-audio --ingest-spool memory/spool
```

---

## Launch flags

```
--no-vision / --no-audio     skip observers
--no-retrieval               disable web/DB retrieval
--skip-analysis              single-pass, fastest mode
--audio-query                autonomous: speech = query
--stop-server                kill server on exit

--model PATH                 GGUF model
--mmproj PATH                projector GGUF (or auto)
--ctx-size N                 context window (default 65536)
--gpu-layers N               GPU offload layers
--threads N                  inference threads
--max-tokens N               response max tokens
--temp FLOAT                 temperature
--timeout N                  per-call timeout

--api-base URL               use remote OpenAI-compatible model
--api-key KEY                bearer token
--api-model NAME             model name

--ingest-spool [DIR]         ingest from out-of-process sensor

LK_API_BASE / LK_API_KEY / LK_API_MODEL    env alternatives
LK_CTX_SIZE / LK_KV_TYPE / LK_FLASH_ATTN  server params
LK_VISION / LK_AUDIO                        force modalities on/off
LLAMACPP_GPU_LAYERS                          GPU layers
EDITOR                                       for /journal edit
```
