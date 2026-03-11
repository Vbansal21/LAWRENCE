from __future__ import annotations


class SpeechService:
    def describe_prosody(self, text: str | None) -> dict[str, str]:
        if not text:
            return {"pace": "unknown", "energy": "neutral", "tone_hint": "neutral"}
        if "!" in text:
            return {"pace": "fast", "energy": "high", "tone_hint": "urgent"}
        if "?" in text:
            return {"pace": "medium", "energy": "neutral", "tone_hint": "inquiring"}
        return {"pace": "medium", "energy": "low", "tone_hint": "calm"}

    def tts_style(self, prosody: dict[str, str]) -> str:
        hint = prosody.get("tone_hint", "neutral")
        if hint == "urgent":
            return "expressive_supportive"
        if hint == "inquiring":
            return "expressive_clear"
        return "neutral_reliable"
