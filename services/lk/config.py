"""User configuration + secrets + per-role model routing.

Three layers, precedence high→low: real environment  >  ~/.lawrence/secrets.env
(confidential, never in git)  >  .runtime/lk.json (preferences)  >  built-ins.

- ``.runtime/lk.json`` holds non-secret preferences (which backend, model path,
  routing, ports). Safe to read; lives in the repo's runtime dir.
- ``~/.lawrence/secrets.env`` holds API keys / passwords. It is in $HOME, OUTSIDE
  the repo, so it can never be committed. ``lk secrets set KEY`` writes it (0600).

Named providers (gemini/openai/openrouter/poe/lmstudio/anthropic/local) let a
config say ``"backend": "gemini"`` instead of spelling out base URLs. Per-role
routing (``"routing": {"extract": "gemini", ...}``) sends background work
(extraction, proactive, compaction, journal) to a fast API while queries stay
wherever you choose — the heart of the autonomous loop on slow local hardware.

Stdlib only. Consumed once at startup by each entry point via apply_to_env().
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT   = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / ".runtime" / "lk.json"
SECRETS_DIR = Path.home() / ".lawrence"
SECRETS_PATH = SECRETS_DIR / "secrets.env"

# Background roles route here by default when a fast API is configured; query
# roles (analysis/response) stay on the default backend unless routed.
# `compact` is the generic memory-compaction role; `compact-l1/-l2/-l3` are the
# per-tier roles (WS-M/M2) — a layer can name one so a deep tier compacts on a
# different/cheaper/longer-context model. They default to the same route as
# `compact` and are unused unless a memory.layers config opts in.
BACKGROUND_ROLES = ("extract", "proactive", "refine", "compact",
                    "compact-l1", "compact-l2", "compact-l3", "journal", "study")
ALL_ROLES        = ("query", "analysis", "response") + BACKGROUND_ROLES

# One-pick setups. Each writes the default backend + per-role routing in one go,
# so a user (or the launcher) never has to reason about individual roles. Shared
# by `lk preset` (CLI) and the launcher menu (UI) — same behaviour either way.
PRESETS: dict[str, dict[str, Any]] = {
    "local":  {"label": "Local only — fully offline & private (slowest on CPU)",
               "backend": "local", "routing": {}},
    "hybrid": {"label": "Hybrid — you chat locally, Gemini does background work",
               "backend": "local", "routing": {r: "gemini" for r in BACKGROUND_ROLES}},
    "gemini": {"label": "Gemini — fast, every role on Gemini 3.1 Flash-Lite",
               "backend": "gemini", "routing": {r: "gemini" for r in ALL_ROLES}},
    "claude": {"label": "Claude — every role on the Anthropic API",
               "backend": "anthropic", "routing": {r: "anthropic" for r in ALL_ROLES}},
}

# Named providers — base URL + sensible default model + which secret holds the key.
PROVIDERS: dict[str, dict[str, str]] = {
    "local":      {"kind": "local"},
    "anthropic":  {"kind": "anthropic", "model": "claude-opus-4-8", "key_env": "ANTHROPIC_API_KEY"},
    "gemini":     {"kind": "api", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                   "model": "gemini-3.1-flash-lite-preview", "key_env": "GEMINI_API_KEY"},
    "openai":     {"kind": "api", "base_url": "https://api.openai.com/v1",
                   "model": "gpt-4o-mini", "key_env": "OPENAI_API_KEY"},
    "openrouter": {"kind": "api", "base_url": "https://openrouter.ai/api/v1",
                   "model": "google/gemini-2.0-flash-001", "key_env": "OPENROUTER_API_KEY"},
    "poe":        {"kind": "api", "base_url": "https://api.poe.com/v1",
                   "model": "Gemini-2.0-Flash", "key_env": "POE_API_KEY"},
    "lmstudio":   {"kind": "api", "base_url": "http://127.0.0.1:1234/v1",
                   "model": "local-model", "key_env": ""},
}

# Non-backend config key → env var the codebase already reads.
_ENV_MAP = {
    "model":         "LK_MODEL",
    "mmproj":        "LK_MMPROJ",
    "ctx_size":      "LK_CTX_SIZE",
    "kv_type":       "LK_KV_TYPE",
    "flash_attn":    "LK_FLASH_ATTN",
    "gpu_layers":    "LLAMACPP_GPU_LAYERS",
    "vision":        "LK_VISION",
    "audio":         "LK_AUDIO",
    "extract":       "LK_EXTRACT",
    # autonomy: cognitive tick (C1) + graded significance (C2) — all config-driven
    # so the knobs round-trip through `lk config` and the GUI settings surface.
    "tick":          "LK_TICK",
    "tick_floor":    "LK_TICK_FLOOR",
    "tick_act_tier": "LK_TICK_ACT_TIER",
    "note_floor":    "LK_NOTE_FLOOR",
    "sig_warmup":    "LK_SIG_WARMUP",
    "sig_k":         "LK_SIG_K",
    "sig_act_floor": "LK_SIG_ACT_FLOOR",
    # autonomy: reasoning loops (R1 slow loop + R2 elevation gate)
    "slow_loop":          "LK_SLOW_LOOP",
    "elevate_delta":      "LK_ELEVATE_DELTA",
    "elevate_max_per_min": "LK_ELEVATE_MAX_PER_MIN",
    "thinking":      "LK_THINKING",
    "searxng_url":   "LK_SEARXNG_URL",
    "ui_port":       "LK_UI_PORT",
    "events_port":   "LK_UI_EVENTS_PORT",
    "proactive_interval": "LK_PROACTIVE_INTERVAL",
}


# ── preferences (lk.json) ─────────────────────────────────────────────────────

def load() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save(cfg: dict[str, Any]) -> Path:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return CONFIG_PATH


def memory_layers() -> list[dict] | None:
    """Custom memory-tier shape from lk.json, or None to use the default 3 tiers.

    Shape: ``{"memory": {"layers": [ {layer}, … ]}}`` where each layer is
    ``{"name", "file"?, "compact_ratio", "promote_to"|null, "header"?,
       "summary_cap"?, "char_budget"?, "compact_role"?, "is_raw"?}`` ordered
    bottom→top (first = raw). The store validates and falls back to its
    DEFAULT_LAYERS on anything malformed, so a bad config never wedges memory.
    """
    mem = load().get("memory")
    if isinstance(mem, dict):
        layers = mem.get("layers")
        if isinstance(layers, list) and layers:
            return layers
    return None


def set_value(key: str, value: str) -> dict[str, Any]:
    cfg = load()
    if value == "":
        cfg.pop(key, None)
    else:
        cfg[key] = value
    save(cfg)
    return cfg


# ── secrets (~/.lawrence/secrets.env) ─────────────────────────────────────────

def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def load_secrets() -> dict[str, str]:
    """Read secrets into the environment (setdefault — a real env var wins).
    Returns the keys that were applied."""
    secrets = _parse_env_file(SECRETS_PATH)
    applied: dict[str, str] = {}
    for k, v in secrets.items():
        if v and k not in os.environ:
            os.environ[k] = v
            applied[k] = "(set)"
    return applied


def set_secret(key: str, value: str) -> Path:
    """Upsert KEY=value into ~/.lawrence/secrets.env (created 0700/0600)."""
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(SECRETS_DIR, 0o700)
    except OSError:
        pass
    existing = _parse_env_file(SECRETS_PATH)
    existing[key] = value
    lines = ["# LAWRENCE secrets — confidential, NOT in git. Managed by `lk secrets`.\n"]
    lines += [f"{k}={v}\n" for k, v in existing.items()]
    SECRETS_PATH.write_text("".join(lines), encoding="utf-8")
    try:
        os.chmod(SECRETS_PATH, 0o600)
    except OSError:
        pass
    return SECRETS_PATH


def secret_keys() -> list[str]:
    """Names present in the secrets file (never the values)."""
    return sorted(_parse_env_file(SECRETS_PATH))


# Friendly provider name → the env var its key lives in. So a user types
# `lk secrets set gemini` and pastes the key; they never see GEMINI_API_KEY.
_SECRET_ALIASES = {
    "gemini": "GEMINI_API_KEY", "google": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY", "gpt": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY", "claude": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "poe": "POE_API_KEY",
    "brave": "BRAVE_API_KEY",
}


def resolve_secret_name(name: str) -> str:
    """A friendly provider alias → its env var; anything else is taken literally."""
    return _SECRET_ALIASES.get(name.strip().lower(), name.strip())


def secret_providers() -> list[str]:
    """Friendly names you can `lk secrets set <name>`."""
    return ["gemini", "openai", "anthropic", "openrouter", "poe", "brave"]


# ── backend resolution ────────────────────────────────────────────────────────

def _resolve_spec(name_or_cfg: Any, cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve a provider name (or inline {kind,...} dict) to a concrete backend
    spec with the API key filled in from the environment/secrets. Returns None
    if the named provider needs a key that isn't available."""
    if isinstance(name_or_cfg, dict):
        spec = dict(name_or_cfg)
        prov = PROVIDERS.get(str(spec.get("provider", "")), {})
        for k, v in prov.items():
            spec.setdefault(k, v)
    else:
        name = str(name_or_cfg or "local").strip().lower()
        if name not in PROVIDERS:
            # treat unknown as an OpenAI-compatible base URL set elsewhere
            return None
        spec = dict(PROVIDERS[name])
    kind = spec.get("kind", "local")
    if kind == "local":
        return {"kind": "local"}
    key_env = str(spec.get("key_env", "") or "")
    api_key = os.environ.get(key_env) if key_env else None
    if kind in ("api", "anthropic") and key_env and not api_key:
        return None   # configured provider but no key yet
    # allow per-role model override via cfg["models"][provider]
    return {
        "kind": kind,
        "base_url": spec.get("base_url", ""),
        "model": str(spec.get("model", "")) or None,
        "api_key": api_key,
    }


def apply_to_env() -> dict[str, str]:
    """Wire secrets, the default backend, per-role routing, and plain prefs.
    Call once, early, from each entry point. Env always wins over config."""
    applied: dict[str, str] = {}
    applied.update({k: "(secret)" for k in load_secrets()})

    cfg = load()

    # plain (non-backend) preferences → env vars
    for key, env in _ENV_MAP.items():
        if key in cfg and env not in os.environ:
            os.environ[env] = str(cfg[key])
            applied[env] = str(cfg[key])

    # default backend (query path). Set env vars (so model.backend_from_env and
    # the bridge's _profile agree) AND configure the backend directly, so the
    # default is authoritative immediately without anyone calling backend_from_env.
    default_name = cfg.get("backend", "local")
    spec = _resolve_spec(default_name, cfg)
    if spec and spec["kind"] == "anthropic":
        os.environ.setdefault("LK_BACKEND", "anthropic")
        if spec.get("model"):
            os.environ.setdefault("LK_API_MODEL", spec["model"])
        applied["backend"] = "anthropic"
    elif spec and spec["kind"] == "api":
        os.environ.setdefault("LK_API_BASE", spec["base_url"])
        if spec.get("model"):
            os.environ.setdefault("LK_API_MODEL", spec["model"])
        if spec.get("api_key"):
            os.environ.setdefault("LK_API_KEY", spec["api_key"])
        applied["backend"] = f"{default_name} (api)"
    # local → nothing to set

    try:
        from . import model as _model
        if spec and spec["kind"] != "local":
            _model.configure_backend(
                kind=spec["kind"], base_url=spec.get("base_url", ""),
                api_key=spec.get("api_key"), model=spec.get("model"),
            )
        # per-role routing (background work → fast API)
        for role, prov in (cfg.get("routing") or {}).items():
            rspec = _resolve_spec(prov, cfg)
            if rspec:
                _model.configure_routing(role, **rspec)
                applied[f"route:{role}"] = str(prov)
    except Exception:
        pass
    return applied


def provider_secret_status(provider: str) -> tuple[str, bool]:
    """For a named provider → (env var it needs, is that key available now).
    Providers that need no key (local/lmstudio) report ("", True)."""
    p = PROVIDERS.get(str(provider).strip().lower(), {})
    key_env = str(p.get("key_env", "") or "")
    if p.get("kind") == "local" or not key_env:
        return "", True
    # secrets file is loaded into os.environ by load_secrets(); also peek the file
    have = bool(os.environ.get(key_env)) or key_env in _parse_env_file(SECRETS_PATH)
    return key_env, have


def apply_preset(name: str) -> tuple[dict[str, Any], list[str]]:
    """Write a named preset into lk.json. Returns (cfg, missing) where ``missing``
    lists provider names whose API key isn't set yet (the preset still saves —
    routed calls fall back to local until the key is added)."""
    preset = PRESETS.get(str(name).strip().lower())
    if not preset:
        raise KeyError(name)
    cfg = load()
    backend = preset["backend"]
    if backend == "local":
        cfg.pop("backend", None)          # local is the built-in default
    else:
        cfg["backend"] = backend
    routing = preset.get("routing") or {}
    if routing:
        cfg["routing"] = dict(routing)
    else:
        cfg.pop("routing", None)
    save(cfg)
    # which providers does this preset rely on, and which lack a key?
    needed = {backend, *routing.values()}
    missing = sorted({
        prov for prov in needed
        if not provider_secret_status(prov)[1]
    })
    return cfg, missing


def configured_summary() -> dict[str, Any]:
    """For `lk status` / wizard — what's set, without leaking secret values."""
    cfg = load()
    return {
        "backend": cfg.get("backend", "local"),
        "routing": cfg.get("routing", {}),
        "secrets": secret_keys(),
        "providers_ready": [
            name for name, p in PROVIDERS.items()
            if p.get("kind") == "local" or not p.get("key_env")
            or os.environ.get(str(p.get("key_env", "")))
        ],
    }
