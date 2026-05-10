from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RollingContext:
    max_chars: int
    turns: list[tuple[str, str]] = field(default_factory=list)

    def add(self, user_text: str, assistant_text: str) -> None:
        self.turns.append((user_text, assistant_text))
        self._trim()

    def clear(self) -> None:
        self.turns.clear()

    def render(self) -> str:
        if not self.turns:
            return "(empty)"
        return " || ".join(f"User: {u} Assistant: {a}" for u, a in self.turns)

    def _trim(self) -> None:
        while len(self.render()) > self.max_chars and self.turns:
            self.turns.pop(0)

