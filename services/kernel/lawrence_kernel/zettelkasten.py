from __future__ import annotations

import math
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
WORD_RE = re.compile(r"[a-zA-Z0-9_\-]{3,}")


@dataclass
class ZettelRecord:
    note_id: str
    path: Path
    frontmatter: dict[str, Any]
    body: str


class ZettelkastenService:
    def __init__(self, vault_path: Path) -> None:
        self._vault = vault_path
        self._vault.mkdir(parents=True, exist_ok=True)

    def read_all(self, limit: int = 500) -> list[ZettelRecord]:
        out: list[ZettelRecord] = []
        for path in sorted(self._vault.glob("*.md"), reverse=True)[:limit]:
            record = self._read_note(path)
            if record:
                out.append(record)
        return out

    def create_note(
        self,
        *,
        note_type: str,
        title: str,
        summary: str,
        tags: list[str],
        entities: list[str],
        source_refs: list[str],
        links: list[str] | None = None,
        confidence: float = 0.7,
        privacy_level: str = "local",
        extra_sections: dict[str, str] | None = None,
    ) -> Path:
        note_id = self._new_note_id()
        path = self._vault / f"{note_id}.md"
        meta = {
            "id": note_id,
            "type": note_type,
            "created_at": self._iso_now(),
            "updated_at": self._iso_now(),
            "entities": sorted(set(e.lower() for e in entities if e)),
            "tags": sorted(set(t.lower() for t in tags if t)),
            "links": sorted(set(links or [])),
            "source_refs": source_refs,
            "confidence": round(float(confidence), 3),
            "privacy_level": privacy_level,
            "title": title,
        }

        lines = ["---", yaml.safe_dump(meta, sort_keys=False).strip(), "---", "", "## Summary", summary, ""]
        if extra_sections:
            for key, value in extra_sections.items():
                lines.append(f"## {key}")
                lines.append(value)
                lines.append("")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def update_links(self, note_id: str, links: list[str]) -> bool:
        record = self.get_note(note_id)
        if not record:
            return False
        meta = record.frontmatter
        merged = sorted(set(meta.get("links", []) + links))
        meta["links"] = merged
        meta["updated_at"] = self._iso_now()
        self._write_note(record.path, meta, record.body)
        return True

    def get_note(self, note_id: str) -> ZettelRecord | None:
        path = self._vault / f"{note_id}.md"
        return self._read_note(path)

    def search(self, query: str, tags: list[str] | None = None, top_k: int = 8) -> list[dict[str, Any]]:
        records = self.read_all(limit=500)
        tokens = self._tokenize(query)
        required_tags = set(t.lower() for t in (tags or []))
        ranked: list[tuple[float, ZettelRecord]] = []

        for rec in records:
            note_tags = set(str(t).lower() for t in rec.frontmatter.get("tags", []))
            if required_tags and not required_tags.issubset(note_tags):
                continue
            text = rec.body + "\n" + yaml.safe_dump(rec.frontmatter, sort_keys=False)
            lexical = self._lexical_score(tokens, text)
            vector = self._cosine_similarity(tokens, self._tokenize(text))
            tag_bonus = 0.2 if required_tags and required_tags & note_tags else 0.0
            score = lexical + vector + tag_bonus
            if score > 0:
                ranked.append((score, rec))

        ranked.sort(key=lambda item: item[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, rec in ranked[:top_k]:
            out.append(
                {
                    "note_id": rec.note_id,
                    "path": str(rec.path),
                    "score": round(score, 4),
                    "tags": rec.frontmatter.get("tags", []),
                    "title": rec.frontmatter.get("title", rec.note_id),
                    "links": rec.frontmatter.get("links", []),
                }
            )
        return out

    def suggest_links(self, note_id: str, max_links: int = 6) -> list[str]:
        target = self.get_note(note_id)
        if not target:
            return []
        query = self._note_vector_text(target)
        candidates = self.search(query=query, tags=None, top_k=20)
        linked = []
        for item in candidates:
            cid = item["note_id"]
            if cid == note_id:
                continue
            linked.append(cid)
            if len(linked) >= max_links:
                break
        return linked

    def multi_hop_neighbors(self, note_id: str, max_hops: int = 2, max_nodes: int = 20) -> list[dict[str, Any]]:
        start = self.get_note(note_id)
        if not start:
            return []

        visited: set[str] = {note_id}
        queue: deque[tuple[str, int]] = deque([(note_id, 0)])
        out: list[dict[str, Any]] = []

        while queue and len(out) < max_nodes:
            current_id, depth = queue.popleft()
            record = self.get_note(current_id)
            if not record:
                continue
            out.append(
                {
                    "note_id": current_id,
                    "depth": depth,
                    "title": record.frontmatter.get("title", current_id),
                    "tags": record.frontmatter.get("tags", []),
                    "links": record.frontmatter.get("links", []),
                }
            )
            if depth >= max_hops:
                continue
            for nxt in record.frontmatter.get("links", []):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, depth + 1))
        return out

    def _read_note(self, path: Path) -> ZettelRecord | None:
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = FRONTMATTER_RE.match(text)
        if not match:
            return None
        fm = yaml.safe_load(match.group(1)) or {}
        body = text[match.end():].strip()
        note_id = str(fm.get("id", path.stem))
        return ZettelRecord(note_id=note_id, path=path, frontmatter=fm, body=body)

    def _write_note(self, path: Path, frontmatter: dict[str, Any], body: str) -> None:
        lines = ["---", yaml.safe_dump(frontmatter, sort_keys=False).strip(), "---", "", body.strip(), ""]
        path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _tokenize(text: str) -> dict[str, float]:
        tokens: dict[str, float] = {}
        for token in WORD_RE.findall((text or "").lower()):
            tokens[token] = tokens.get(token, 0.0) + 1.0
        return tokens

    @staticmethod
    def _lexical_score(query_tokens: dict[str, float], text: str) -> float:
        if not query_tokens:
            return 0.0
        lowered = text.lower()
        score = 0.0
        for token, weight in query_tokens.items():
            if token in lowered:
                score += weight
        return score

    @staticmethod
    def _cosine_similarity(lhs: dict[str, float], rhs: dict[str, float]) -> float:
        if not lhs or not rhs:
            return 0.0
        dot = 0.0
        for token, val in lhs.items():
            dot += val * rhs.get(token, 0.0)
        norm_l = math.sqrt(sum(v * v for v in lhs.values()))
        norm_r = math.sqrt(sum(v * v for v in rhs.values()))
        if norm_l == 0.0 or norm_r == 0.0:
            return 0.0
        return dot / (norm_l * norm_r)

    @staticmethod
    def _note_vector_text(record: ZettelRecord) -> str:
        fields = [
            str(record.frontmatter.get("title", "")),
            " ".join(record.frontmatter.get("tags", [])),
            " ".join(record.frontmatter.get("entities", [])),
            record.body,
        ]
        return "\n".join(fields)

    @staticmethod
    def _new_note_id() -> str:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        return now.strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:6]

    @staticmethod
    def _iso_now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
