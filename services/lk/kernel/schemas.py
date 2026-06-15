"""JSON Schemas for the model's structured envelopes — constrained decoding.

llama.cpp / OpenAI-compatible backends receive these via response_format
(compiled to a grammar server-side); the Anthropic backend via
output_config.format. With a schema attached the model *cannot* emit invalid
JSON, so invoke._extract_json becomes a safety net instead of a prayer.

Two rules baked into these definitions:

1. Property ORDER matters. Grammar enforcement emits properties in declaration
   order, and invoke.AnswerTextStreamer streams the answer live by scanning for
   the first string value of "answer_text" — so it MUST be RESPONSE's first key.

2. MINIMAL required sets. Constraining every field as required forces the model
   to emit the entire envelope (note_full, tags, controls, tasks, …) on every
   turn — ~300 tokens, which at CPU speed (~4 tok/s) is ~75s per pass. Only the
   genuinely essential field is required; the rest are optional, so a short
   answer is short and fast. Both llama.cpp grammars and Anthropic structured
   outputs permit optional properties (the hard rule is additionalProperties:
   false, not all-required). All consumers already .get() with defaults.

   Other constraints (Anthropic rules): additionalProperties:false on every
   object, no recursion, no numeric/length bounds.
"""

ANALYSIS = {
    "type": "object",
    "properties": {
        "situation":       {"type": "string"},
        "intent":          {"type": "string"},
        "needs_retrieval": {"type": "boolean"},
        "queries":         {"type": "array", "items": {"type": "string"}},
        "capture_hires":   {"type": "boolean"},
    },
    "required": ["needs_retrieval"],
    "additionalProperties": False,
}

RESPONSE = {
    "type": "object",
    "properties": {
        # answer_text MUST stay first — see module docstring (live streaming).
        "answer_text":     {"type": "string"},
        "modalities_used": {"type": "array", "items": {"type": "string"}},
        "note_compact":    {"type": "string"},
        "note_full":       {"type": "string"},
        "context_tags":    {"type": "array", "items": {"type": "string"}},
        "confidence":      {"type": "number"},
        "expand_sources":  {"type": "array", "items": {"type": "integer"}},
        "controls": {
            "type": "object",
            "properties": {
                "vision": {"type": "string"},   # "hi" | "on" | "off" | "" (no-op)
                "audio":  {"type": "string"},   # "on" | "off" | "" (no-op)
            },
            "required": ["vision", "audio"],
            "additionalProperties": False,
        },
        "tasks": {
            "type": "array",
            "items": {
                "anyOf": [
                    {"type": "string"},
                    {
                        "type": "object",
                        "properties": {
                            "op":   {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["op", "text"],
                        "additionalProperties": False,
                    },
                ]
            },
        },
        "remember": {"type": "array", "items": {"type": "string"}},
    },
    # Only answer_text is required — everything else is optional so short
    # answers stay short (the model emits note/tags/tasks only when relevant).
    "required": ["answer_text"],
    "additionalProperties": False,
}

PROACTIVE = {
    "type": "object",
    "properties": {
        "needs_retrieval": {"type": "boolean"},
        "queries":         {"type": "array", "items": {"type": "string"}},
    },
    "required": ["needs_retrieval"],
    "additionalProperties": False,
}

# Extraction (WS-P/B1): one raw sensor slice → a clean, self-contained entry.
# `clean` first so a streaming/partial parse still yields the useful field. Lean:
# only `clean` is required so the call stays cheap on slow local hardware.
EXTRACT = {
    "type": "object",
    "properties": {
        "clean":        {"type": "string"},
        "significance": {"type": "number"},
        "tags":         {"type": "array", "items": {"type": "string"}},
    },
    "required": ["clean"],
    "additionalProperties": False,
}

PROACTIVE_BRIEF = {
    "type": "object",
    "properties": {
        "surface":  {"type": "boolean"},
        "headline": {"type": "string"},
        "insight":  {"type": "string"},
    },
    "required": ["surface"],
    "additionalProperties": False,
}

# Slow loop (WS-R/R1): the alter-ego critiques the fast answer and decides whether
# a better one is available. `better` first (cheap verdict streams first); only
# `better` is required so a "no improvement" verdict is one tiny token.
REFINE = {
    "type": "object",
    "properties": {
        "better":     {"type": "boolean"},
        "confidence": {"type": "number"},
        "critique":   {"type": "string"},
        "refined":    {"type": "string"},
    },
    "required": ["better"],
    "additionalProperties": False,
}
