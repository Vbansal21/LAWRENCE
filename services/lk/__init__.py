# LAWRENCE local kernel v0.1
#
# Package layout:
#   ctx/        — context store (file-based rolling context, gate, distillation)
#   obs/        — sensor observers (vision + audio → write to ctx when significant)
#   retrieval/  — Perplexity-style retrieval (web, BM25 ranker, SQLite semantic DB)
#   kernel/     — LLM invocation (analysis → retrieval → response)
#   ui/         — connector stubs for Tauri desktop UI (apps/desktop/)
#   server.py   — llama-server lifecycle (start once, keep resident)
#   model.py    — HTTP client to llama-server
#   logger.py   — JSONL turn log writer
#   cli.py      — terminal entry point
