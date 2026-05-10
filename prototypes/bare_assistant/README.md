# LAWRENCE Bare Assistant Prototype

This is a deliberately small terminal assistant path for v0.1 experimentation.

It supports:

- text input/output all the time
- user-invoked screenshot capture
- user-invoked Windows clipboard image capture
- newest screenshot/image from a specified directory
- audio file input or short WSL recording
- local text file context
- web retrieval before model invocation
- media-aware context probe that creates the web search query before retrieval
- schema-constrained JSON model output
- daily Markdown logs in `memory/bare_logs/YYYY-MM-DD.md`

Run:

```bash
python3 -m prototypes.bare_assistant.cli
```

Default generation uses `--ctx-size 2048 --predict 384`. Keep those defaults
unless the model call is too slow for the machine.

Optional startup flags:

```bash
python3 -m prototypes.bare_assistant.cli --web-results 5 --screenshot-dir /mnt/c/Users/XriyalVixen/Pictures/Screenshots
```

Useful commands:

```text
plain text
/screenshot What should I notice here?
/clipboard Explain this image.
/recent /mnt/c/Users/XriyalVixen/Pictures/Screenshots What changed?
/audio ./sample.wav Summarize this audio.
/record 5 What did I say?
/file README.md Summarize this local file.
/web off
/clear
/status
/exit
```

Notes:

- This is not the main LAWRENCE kernel yet.
- Rolling context is bounded by `--max-context-chars`.
- With web enabled, LAWRENCE first asks the model to summarize the current
  text/media/local context and generate a search query. Web evidence from that
  query is then included in the final model call.
- The terminal prints the generated web query and result count before the final
  model call, so it is clear what outside knowledge was added.
- The daily log records the context probe, generated web query, captures, web
  evidence, response, and distilled context log.
- Rolling context stores both the previous context summary and answer, then is
  clipped by `--max-context-chars`.
- llama.cpp mmap is enabled by default for faster loads.
- KV-cache reuse is not implemented here because current `llama-mtmd-cli`
  native resident chat is unreliable with `--json-schema-file` across later
  turns. The current practical compromise is bounded rolling context plus mmap.
- A system key chord is not implemented inside WSL. Use `/screenshot` now; a
  Windows AutoHotkey or Tauri/Rust hotkey bridge can invoke this later.
