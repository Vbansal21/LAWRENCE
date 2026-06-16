"""WS-K capability routing (NEXT_WORK_CHECKLIST §4) — resolver buckets + the
single-source-of-truth contract between the resolver and the model payload filter.

Pure/offline: no server, no network. Asserts that the requested decoding config
splits into active/inactive/unavailable correctly per backend, that inactive
config is never sent, and that model._api_options_for_backend agrees with the
resolver (so the outgoing payload and the UI markers can never drift)."""
import sys

sys.path.insert(0, "services")

from lk import capabilities as C  # noqa: E402
from lk import model as M  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


# A representative request touching every dimension.
DEC = {
    "temperature": 0.3, "topP": 0.9, "topK": 40, "minP": 0.05,
    "mirostat": 2, "mirostatTau": 5.0, "repeatPenalty": 1.1, "seed": 7,
    "stopSequences": ["END"],
    "epsilonCutoff": 0.0004, "etaCutoff": 0.0007, "grammarSchema": '{"type":"object"}',
    # unset knobs must be ignored entirely:
    "typicalP": None, "tfsZ": "", "dryMultiplier": None,
}


def keys(bucket):
    return {row["key"] for row in bucket}


# ── local llama.cpp: full sampler set active ──────────────────────────────────
loc = C.resolve_config(DEC, kind="local", provider="local")
check("local activates local samplers (top_k/min_p/mirostat/repeat)",
      {"topK", "minP", "mirostat", "mirostatTau", "repeatPenalty"} <= set(loc.active))
check("local activates common samplers (temperature/topP/seed/stop)",
      {"temperature", "topP", "seed", "stopSequences"} <= set(loc.active))
check("local has no inactive samplers", loc.inactive == [], str(loc.inactive))

# ── unavailable bucket is backend-independent (no provider config anywhere) ────
for prof in (loc, C.resolve_config(DEC, kind="api", provider="openai"),
             C.resolve_config(DEC, kind="anthropic", provider="anthropic",
                              model="claude-haiku-4-5")):
    check(f"unavailable = epsilon/eta/grammar ({prof and 'profile'})",
          keys(prof.unavailable) == {"epsilonCutoff", "etaCutoff", "grammarSchema"},
          str(keys(prof.unavailable)))
    check("every unavailable row carries a suggestion",
          all(r.get("suggestion") for r in prof.unavailable))

# ── unset knobs are neither applied nor flagged ───────────────────────────────
all_flagged = set(loc.active) | keys(loc.inactive) | keys(loc.unavailable)
check("unset knobs (typicalP/tfsZ/dryMultiplier) are ignored",
      not ({"typicalP", "tfsZ", "dryMultiplier"} & all_flagged), str(all_flagged))

# ── unknown OpenAI-compatible API: only conservative common fields active ──────
api = C.resolve_config(DEC, kind="api", provider="api")
check("api activates common fields (temperature/topP/seed/stop)",
      {"temperature", "topP", "seed", "stopSequences"} <= set(api.active))
check("api deactivates llama-only samplers (top_k/min_p/mirostat/repeat)",
      {"topK", "minP", "mirostat", "mirostatTau", "repeatPenalty"} <= keys(api.inactive),
      str(set(api.active)))
check("api inactive samplers are NOT in the active dict",
      not ({"topK", "minP", "mirostat"} & set(api.active)))
check("api inactive rows carry a reason", all(r.get("reason") for r in api.inactive))

# ── Gemini: top_p active, local samplers inactive, schema relax stays in adapter ─
gem = C.resolve_config(DEC, kind="api", provider="gemini")
check("gemini activates temperature/topP", {"temperature", "topP"} <= set(gem.active))
check("gemini deactivates top_k/min_p/mirostat",
      {"topK", "minP", "mirostat"} <= keys(gem.inactive))
check("gemini does not activate seed (restricted)", "seed" not in gem.active)

# ── Anthropic: llama-only samplers inactive; native schema ────────────────────
ant = C.resolve_config(DEC, kind="anthropic", provider="anthropic", model="claude-haiku-4-5")
check("anthropic activates temperature/topP", {"temperature", "topP"} <= set(ant.active))
check("anthropic deactivates top_k/min_p/mirostat/repeat",
      {"topK", "minP", "mirostat", "repeatPenalty"} <= keys(ant.inactive))

# ── Anthropic no-sampling model rejects ALL sampling params ───────────────────
ant0 = C.resolve_config(DEC, kind="anthropic", provider="anthropic", model="claude-opus-4-8")
check("claude-opus-4-8 marks temperature/topP inactive (no sampling)",
      {"temperature", "topP"} <= keys(ant0.inactive) and not ant0.active,
      str(set(ant0.active)))

# ── single source of truth: resolver agrees with model payload filter ─────────
# What the resolver calls "active" for an API backend == what _api_options_for_backend
# actually keeps in the outgoing payload (minus temperature, which is top-level).
for prov in ("openai", "openrouter", "lmstudio", "poe", "gemini", "api"):
    b = M.Backend(kind="api", provider=prov)
    # Mirror model.py's _opt dict — temperature is a top-level payload field, never
    # in the per-provider option filter, so exclude it here as call_model does.
    opts = {C._CAMEL_TO_SNAKE[k]: 1 for k in DEC
            if k in C._CAMEL_TO_SNAKE and C._has_value(DEC[k])
            and C._CAMEL_TO_SNAKE[k] != "temperature"}
    sent = set(M._api_options_for_backend(b, opts))
    res = C.resolve_config(DEC, kind="api", provider=prov)
    res_active_snake = {C._CAMEL_TO_SNAKE[k] for k in res.active if k in C._CAMEL_TO_SNAKE}
    # temperature is applied top-level, never through the option filter → exclude it.
    check(f"resolver↔payload agree ({prov})", sent == (res_active_snake - {"temperature"}),
          f"sent={sent} active={res_active_snake}")

# ── retrieval/agent config is not mixed into decoding buckets ─────────────────
mixed = C.resolve_config({"webDepth": "comprehensive", "citationMode": "required", "topP": 0.9},
                         kind="local", provider="local")
flagged = set(mixed.active) | keys(mixed.inactive) | keys(mixed.unavailable)
check("non-decoding keys (webDepth/citationMode) are not bucketed",
      flagged == {"topP"}, str(flagged))

# ── capability_summary shape for /health ──────────────────────────────────────
summ = C.capability_summary(kind="local", provider="local")
check("summary has backend/provider/sampling/schema/prefill keys",
      {"backend", "provider", "sampling", "schema", "prefill", "unavailable"} <= set(summ))
check("local summary advertises local sampler families",
      {"topK", "minP", "mirostat"} <= set(summ["sampling"]))
check("local schema strategy is grammar", summ["schema"] == "grammar")
asumm = C.capability_summary(kind="api", provider="poe")
check("poe summary excludes local samplers", "topK" not in asumm["sampling"])
check("poe summary lists unavailable keys",
      set(asumm["unavailable"]) == {"epsilonCutoff", "etaCutoff", "grammarSchema"})

# ── model layer re-exports the resolver (I3: bridge calls through model only) ──
check("model re-exports resolve_config/capability_summary/ResolvedConfig",
      all(hasattr(M, n) for n in ("resolve_config", "capability_summary",
                                  "ResolvedConfig", "resolve_active_config",
                                  "active_capability_summary", "active_backend_ident")))
ident = M.active_backend_ident()
check("active_backend_ident returns kind/provider/model",
      {"kind", "provider", "model"} <= set(ident), str(ident))

if FAILS:
    print(f"\n{len(FAILS)} FAILED: {FAILS}")
    sys.exit(1)
print("\nALL CAPABILITY CHECKS PASSED")
