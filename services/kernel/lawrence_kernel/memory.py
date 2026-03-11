from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from lawrence_kernel.config import RetentionConfig
from lawrence_kernel.models import DistillationRecord, FacetResult, TurnContextSnapshot
from lawrence_kernel.zettelkasten import ZettelkastenService


class MarkdownMemoryStore:
    def __init__(self, retention: RetentionConfig, vault_path: Path | None = None) -> None:
        self._retention = retention
        self._vault_path = vault_path or Path("memory/vault")
        self._vault_path.mkdir(parents=True, exist_ok=True)
        self.zettel = ZettelkastenService(self._vault_path)

    def write_distillation(self, snapshot: TurnContextSnapshot, facet_results: Iterable[FacetResult]) -> DistillationRecord:
        now = datetime.now(timezone.utc)

        links = [r.payload.get("note_link", "") for r in facet_results if r.payload.get("note_link")]
        entities = self._extract_entities(snapshot, facet_results)
        tags = ["context", "distilled", snapshot.trigger_type]
        summary = self._summary(snapshot)

        facet_lines = []
        for result in facet_results:
            facet_lines.append(f"- {result.facet_type.value}: {result.payload.get('summary', 'no summary')}")

        sections = {
            "Facet Signals": "\n".join(facet_lines) or "- no facet signals",
            "Next Actions": "- Review deferred reasoning output when available.\n- Confirm suggested tool actions before execution.",
        }

        note_path = self.zettel.create_note(
            note_type="context_log",
            title=f"Turn {snapshot.turn_id}",
            summary=summary,
            tags=tags,
            entities=entities,
            source_refs=[snapshot.turn_id],
            links=links,
            confidence=0.7,
            privacy_level="local",
            extra_sections=sections,
        )

        created_id = note_path.stem
        suggested = self.zettel.suggest_links(created_id, max_links=6)
        if suggested:
            self.zettel.update_links(created_id, suggested)

        expires_at = now + timedelta(minutes=self._retention.raw_ttl_minutes)
        return DistillationRecord(
            source_ref=snapshot.turn_id,
            distilled_into=str(note_path),
            retention_policy=f"raw_ttl_{self._retention.raw_ttl_minutes}m",
            expires_at=expires_at,
        )

    def list_notes(self, limit: int = 200) -> list[Path]:
        notes = sorted(self._vault_path.glob("*.md"), reverse=True)
        return notes[:limit]

    @staticmethod
    def _summary(snapshot: TurnContextSnapshot) -> str:
        query = snapshot.user_query or "(no explicit user query)"
        return f"Trigger `{snapshot.trigger_type}` at {snapshot.time_ref}. Query: {query}"

    @staticmethod
    def _extract_entities(snapshot: TurnContextSnapshot, facet_results: Iterable[FacetResult]) -> list[str]:
        entities = set()
        if snapshot.app_ref:
            entities.add(snapshot.app_ref)
        if snapshot.user_query:
            for token in snapshot.user_query.split():
                token = token.strip(".,!?;:").lower()
                if len(token) > 4:
                    entities.add(token)
        for result in facet_results:
            for ent in result.payload.get("entities", []):
                entities.add(str(ent).lower())
        return sorted(entities)[:20]
