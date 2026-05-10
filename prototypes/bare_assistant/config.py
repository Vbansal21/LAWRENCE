from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "models/local/gemma-4-E4B-it-GGUF"


@dataclass
class AssistantConfig:
    llama_bin: Path = REPO_ROOT / "third_party/llama.cpp/build/bin/llama-mtmd-cli"
    model: Path = MODEL_DIR / "gemma-4-E4B-it-Q4_K_M.gguf"
    mmproj: Path = MODEL_DIR / "mmproj-gemma-4-E4B-it-BF16.gguf"
    schema: Path = REPO_ROOT / "prototypes/bare_assistant/schemas/assistant_response.schema.json"
    context_probe_schema: Path = REPO_ROOT / "prototypes/bare_assistant/schemas/context_probe.schema.json"
    log_dir: Path = REPO_ROOT / "memory/bare_logs"
    ctx_size: int = 2048
    predict: int = 384
    temperature: float = 0.2
    max_context_chars: int = 6000
    timeout_seconds: int = 600
    web_results: int = 3
    mmap: bool = True
    no_mmproj_offload: bool = True
