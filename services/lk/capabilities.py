"""Backend/model capability registry + config resolver — WS-K, NEXT_WORK_CHECKLIST §4.

Pure data + pure functions. Given a backend identity (kind/provider/model) and
the UI's decoding config, decide which options are:

  - ACTIVE       valid key, supported here → applied to this turn.
  - INACTIVE     valid key, but this backend/model cannot honor it → kept in
                 config, never sent, marked red in the UI with a reason.
  - UNAVAILABLE  no direct provider config exists anywhere in the current set →
                 marked gray with a suggested alternative path.

This is the SINGLE source of truth for "what each backend can honor". model.py
imports SAMPLING_SUPPORT from here so the request-payload filter and the UI
markers can never drift, and re-exports resolve_config()/capability_summary() so
the bridge calls through the model layer only (invariant I3: provider logic
stays in the model layer, never scattered across UI/bridge/kernel). Future
vLLM/Ollama/etc support = add data here, not new `if provider ==` branches.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── canonical sampling vocabulary ─────────────────────────────────────────────
# snake_case payload name → camelCase key the UI sends in config["decoding"].
# (temperature/stop are universal; the rest split common-API vs local-only.)
SAMPLING_KEYS: dict[str, str] = {
    "temperature":        "temperature",
    "top_p":              "topP",
    "presence_penalty":   "presencePenalty",
    "frequency_penalty":  "frequencyPenalty",
    "seed":               "seed",
    "stop":               "stopSequences",
    # local / llama.cpp-style samplers
    "top_k":              "topK",
    "min_p":              "minP",
    "typical_p":          "typicalP",
    "tfs_z":              "tfsZ",
    "repeat_penalty":     "repeatPenalty",
    "repeat_last_n":      "repeatLastN",
    "mirostat":           "mirostat",
    "mirostat_tau":       "mirostatTau",
    "mirostat_eta":       "mirostatEta",
    "dry_multiplier":     "dryMultiplier",
    "dry_base":           "dryBase",
    "dry_allowed_length": "dryAllowedLength",
}
_CAMEL_TO_SNAKE = {camel: snake for snake, camel in SAMPLING_KEYS.items()}
_ALL_SAMPLING = set(SAMPLING_KEYS)

# Common subset every OpenAI-compatible API accepts. temperature is sent as a
# top-level payload field on every non-Claude backend, so it is universally active
# (model.py applies it directly, not through the per-provider option filter).
_COMMON_API = {"temperature", "top_p", "presence_penalty", "frequency_penalty", "seed", "stop"}

# Per-provider sampling support (snake_case). "local" honors the full llama.cpp
# set; the API providers honor subsets. This MUST match model._api_options_for_backend
# (model.py imports SAMPLING_SUPPORT to build that filter — one source of truth).
SAMPLING_SUPPORT: dict[str, set[str]] = {
    "local":      set(_ALL_SAMPLING) | {"temperature"},
    "api":        _COMMON_API,
    "openai":     _COMMON_API,
    "openrouter": _COMMON_API,
    "lmstudio":   _COMMON_API,
    "poe":        {"temperature", "top_p", "stop"},
    "gemini":     {"temperature", "top_p", "stop"},
    # native Claude: at most one of temperature/top_p, plus stop_sequences.
    "anthropic":  {"temperature", "top_p", "stop"},
}

# Structured-output strategy per backend (informational, for /health + suggestions).
SCHEMA_STRATEGY: dict[str, str] = {
    "local":      "grammar",        # llama.cpp json_schema / json_object → GBNF
    "anthropic":  "native",         # output_config json_schema
    "gemini":     "json_schema",    # relaxed schema in the gemini adapter
    "api":        "json_schema",    # probed: json_schema → json_object → none
    "openai":     "json_schema",
    "openrouter": "json_schema",
    "lmstudio":   "json_schema",
    "poe":        "prompt",         # no reliable constrained decoding → prompt only
}

# Assistant prefill / continue-from-partial. Local chat templates allow it; most
# hosted APIs reject it. Conservative defaults; refined as adapters land.
PREFILL_SUPPORT: dict[str, bool] = {
    "local": True, "anthropic": True,
    "api": False, "openai": False, "openrouter": False,
    "lmstudio": True, "poe": False, "gemini": False,
}

# UI keys with NO direct provider config in ANY current backend → always
# unavailable, with a suggested path. grammarSchema is honored only as a prompt
# hint today (no constrained-decoding wiring for a user-supplied schema).
UNAVAILABLE_KEYS: dict[str, str] = {
    "epsilonCutoff": "No current backend exposes epsilon-cutoff sampling.",
    "etaCutoff":     "No current backend exposes eta-cutoff sampling.",
    "grammarSchema": "Custom grammar/JSON-schema decoding is not wired; this value "
                     "is applied as a prompt hint only. Use the local llama.cpp "
                     "backend for hard schema constraints.",
}


@dataclass
class ResolvedConfig:
    """Three explicit buckets for one turn's decoding config."""
    active: dict[str, Any] = field(default_factory=dict)          # camelCase → value, applied
    inactive: list[dict[str, str]] = field(default_factory=list)  # {key, reason}
    unavailable: list[dict[str, str]] = field(default_factory=list)  # {key, reason, suggestion}

    def as_dict(self) -> dict[str, Any]:
        return {"active": self.active, "inactive": self.inactive, "unavailable": self.unavailable}


def _provider_key(kind: str, provider: str) -> str:
    if kind == "local":
        return "local"
    if kind == "anthropic":
        return "anthropic"
    return provider if provider in SAMPLING_SUPPORT else "api"


def supported_sampling(kind: str, provider: str) -> set[str]:
    """The snake_case sampling keys this backend honors."""
    return SAMPLING_SUPPORT.get(_provider_key(kind, provider), _COMMON_API)


def _no_sampling_model(kind: str, model: str | None) -> bool:
    # Claude opus-4.7/4.8 + fable reject ALL sampling params (mirrors
    # model._ANTHROPIC_NO_SAMPLING_PREFIXES — kept local to avoid an import cycle).
    if kind != "anthropic" or not model:
        return False
    return model.startswith(("claude-opus-4-7", "claude-opus-4-8", "claude-fable"))


def _has_value(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (list, tuple, dict)):
        return len(v) > 0
    return True


def resolve_config(decoding: dict[str, Any] | None, *, kind: str,
                   provider: str, model: str | None = None) -> ResolvedConfig:
    """Split a UI decoding dict into active/inactive/unavailable for this backend.

    Only keys the user actually set (non-empty) are bucketed — an unset advanced
    knob is neither applied nor flagged. Pure: no I/O, no network probe.
    """
    decoding = decoding or {}
    pkey = _provider_key(kind, provider)
    label = provider or kind
    supported = SAMPLING_SUPPORT.get(pkey, _COMMON_API)
    no_sampling = _no_sampling_model(kind, model)
    res = ResolvedConfig()

    for key, value in decoding.items():
        if not _has_value(value):
            continue
        if key in UNAVAILABLE_KEYS:
            res.unavailable.append({"key": key, "reason": "No direct provider config.",
                                    "suggestion": UNAVAILABLE_KEYS[key]})
            continue
        snake = _CAMEL_TO_SNAKE.get(key)
        if snake is None:
            continue  # not a decoding sampler we route (retrieval/agent live elsewhere)
        if no_sampling:
            res.inactive.append({"key": key,
                                 "reason": f"{model} rejects all sampling parameters."})
        elif snake in supported:
            res.active[key] = value
        else:
            res.inactive.append({"key": key,
                                 "reason": f"Not honored by the {label} backend "
                                           "(local llama.cpp sampler)."})
    return res


def capability_summary(*, kind: str, provider: str, model: str | None = None) -> dict[str, Any]:
    """Cheap capability snapshot for /health (no network calls)."""
    pkey = _provider_key(kind, provider)
    supported = sorted(SAMPLING_KEYS[s] for s in supported_sampling(kind, provider)
                       if s in SAMPLING_KEYS)
    return {
        "backend": kind,
        "provider": provider,
        "model": model or "",
        "sampling": supported,                       # active sampler families (camelCase)
        "schema": SCHEMA_STRATEGY.get(pkey, "prompt"),
        "prefill": PREFILL_SUPPORT.get(pkey, False),
        "unavailable": sorted(UNAVAILABLE_KEYS),      # never honored directly anywhere
    }
