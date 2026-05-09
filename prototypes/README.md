# Prototypes

This directory contains small, local experiments that are not wired into the
LAWRENCE kernel yet.

## Gemma 4 E4B VAL Terminal Prototype

`gemma4_val_terminal.py` runs a continuous terminal chat against the local
Gemma 4 E4B GGUF model.

Text is always available and required for each model turn. Screenshots, images,
and audio are optional per-turn attachments that are used only when explicitly
requested.

Default model paths prefer the Linux-side copy first:

- `models/local/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf`
- `models/local/gemma-4-E4B-it-GGUF/mmproj-gemma-4-E4B-it-BF16.gguf`

If those files do not exist, the wrapper falls back to the LM Studio cache:

- `/mnt/c/Users/XriyalVixen/.cache/lm-studio/models/lmstudio-community/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf`
- `/mnt/c/Users/XriyalVixen/.cache/lm-studio/models/lmstudio-community/gemma-4-E4B-it-GGUF/mmproj-gemma-4-E4B-it-BF16.gguf`

Examples:

```bash
python3 prototypes/gemma4_val_terminal.py
python3 prototypes/gemma4_val_terminal.py --prompt "Start by summarizing LAWRENCE in one sentence."
python3 prototypes/gemma4_val_terminal.py --screenshot --prompt "Describe the current screen."
python3 prototypes/gemma4_val_terminal.py --audio ./sample.wav --prompt "Transcribe and summarize this audio."
```

Inside the chat:

```text
you> Explain the current prototype.
you> /screenshot What is visible on screen?
you> /image ./example.png What is important here?
you> /audio ./sample.wav What did the speaker say?
you> /record 5 What did I say?
you> /clear
you> /exit
```

Notes:

- By default, rolling context is maintained by the Python wrapper and each turn
  is sent to llama.cpp with the transcript so JSON schema enforcement remains
  reliable across turns.
- `--resident-native` uses llama.cpp's native chat context, but current testing
  shows native resident chat is unstable across later turns when
  `--json-schema-file` is active.
- The wrapper translates terminal media commands into llama.cpp native chat
  commands for each turn.
- Structured JSON is enforced by llama.cpp constrained decoding through
  `--json-schema-file prototypes/schemas/lawrence_val_response.schema.json`.
- Use `--plain-text` only when you intentionally want unconstrained text output.
- Gemma 4 currently needs llama.cpp `--jinja`, so the wrapper enables it by
  default.
- llama.cpp warmup is disabled by default for faster prototype startup.
- mmap-backed model loading is enabled by default because it is the practical
  fast path for repeated local runs. Use `--no-mmap` only if OS page-cache
  behavior is a problem and you prefer slower process-owned loading.
- The wrapper starts llama.cpp children in their own process group and cleans
  them up on normal exit, Ctrl-C, timeout, SIGTERM, and SIGHUP.
- llama.cpp logs stay visible by default because `--log-disable` also suppresses
  this CLI's interactive output in current testing. Use `--disable-llama-logs`
  only for non-interactive diagnostics.
- Screenshot capture uses Windows PowerShell from WSL.
- Audio recording needs a WSL-accessible recorder such as `arecord` or `ffmpeg`.
- If recording is unavailable, provide a pre-recorded file with `--audio`.
- Use `--dry-run` to inspect the generated `llama-mtmd-cli` command.
