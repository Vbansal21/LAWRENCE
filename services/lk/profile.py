"""Model capability profile — makes the kernel model-agnostic.

LAWRENCE was built around a Gemma-4 omni GGUF (text + vision + audio, flash
attention, q4_0 KV cache, embedded Jinja chat template). Swapping in a different
model — a text-only Llama, a vision-only Qwen-VL, a build without flash attention
— used to break because those assumptions were hardcoded.

A ModelProfile captures everything that varies between models in one place:
  - which modalities the model accepts (vision / audio)   → gates observers + media blocks
  - whether a multimodal projector (mmproj) is present     → controls --mmproj
  - server flags that depend on the model/build            → flash-attn, KV type, jinja, ctx

Capabilities auto-detect from the mmproj file's presence and can be overridden
by environment variables, so any model runs with sensible defaults:

  LK_VISION=0/1      force vision on/off          (default: mmproj present)
  LK_AUDIO=0/1       force audio  on/off          (default: mmproj present)
  LK_FLASH_ATTN=on|off|auto                        (default: on if KV quantized, else auto)
  LK_KV_TYPE=q4_0|q8_0|f16|none   KV cache type    (default: q4_0; f16/none → unquantized)
  LK_JINJA=0/1       embedded chat template        (default: on)
  LK_CTX_SIZE=N      context window                (default: 65536)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_UNQUANTIZED = {"f16", "fp16", "none", ""}


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _find_mmproj(model: Path) -> Path | None:
    """Look for a projector GGUF (mmproj*.gguf) alongside the model file."""
    try:
        for p in sorted(model.parent.glob("*mmproj*.gguf")):
            return p
    except OSError:
        pass
    return None


@dataclass
class ModelProfile:
    model:   Path
    bin:     Path
    mmproj:  Path | None        # None → text-only (no --mmproj passed)
    vision:  bool
    audio:   bool
    ctx_size: int
    flash_attn: str             # "on" | "off" | "auto"
    kv_type: str | None         # quantized type, or None for default f16 cache
    jinja:   bool

    # ── construction ───────────────────────────────────────────────────────────

    @classmethod
    def detect(
        cls,
        *,
        model:   Path | str,
        bin_path: Path | str,
        mmproj:  Path | str | None = None,
        ctx_size: int = 65_536,
    ) -> "ModelProfile":
        """Build a profile, auto-detecting capabilities and applying env overrides."""
        model    = Path(model)
        bin_path = Path(bin_path)
        mmproj_p = Path(mmproj) if mmproj else _find_mmproj(model)
        has_proj = mmproj_p is not None and mmproj_p.exists()

        # Modalities default to projector presence; env can force either way.
        # Without a projector the model is text-only no matter what env says.
        vision = _env_bool("LK_VISION", has_proj) and has_proj
        audio  = _env_bool("LK_AUDIO",  has_proj) and has_proj

        # KV cache type. Quantized KV requires flash attention; f16/none = unquantized.
        kv_raw = os.environ.get("LK_KV_TYPE", "q4_0").strip().lower()
        kv_type: str | None = None if kv_raw in _UNQUANTIZED else kv_raw

        # Flash attention: forced on when KV is quantized (hard requirement),
        # otherwise honour the env override, defaulting to "auto".
        fa = os.environ.get("LK_FLASH_ATTN", "on" if kv_type else "auto").strip().lower()
        if kv_type and fa == "off":
            # Inconsistent request — quantized KV needs FA. Drop quantization
            # rather than the user's explicit FA choice.
            kv_type = None

        jinja = _env_bool("LK_JINJA", True)
        ctx   = int(os.environ.get("LK_CTX_SIZE", str(ctx_size)))

        return cls(
            model=model, bin=bin_path, mmproj=mmproj_p if has_proj else None,
            vision=vision, audio=audio, ctx_size=ctx,
            flash_attn=fa, kv_type=kv_type, jinja=jinja,
        )

    # ── display ────────────────────────────────────────────────────────────────

    @property
    def modalities(self) -> str:
        mods = ["text"]
        if self.vision:
            mods.append("vision")
        if self.audio:
            mods.append("audio")
        return "+".join(mods)

    def summary(self) -> str:
        return (
            f"{self.model.name} | {self.modalities} | ctx {self.ctx_size // 1024}K "
            f"| FA {self.flash_attn} | KV {self.kv_type or 'f16'}"
            f"{'' if self.jinja else ' | no-jinja'}"
        )
