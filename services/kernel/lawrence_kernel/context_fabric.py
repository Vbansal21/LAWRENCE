from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from lawrence_kernel.models import TurnContextSnapshot, TurnInput


class ContextFabric:
    def __init__(self) -> None:
        self._version = 0

    def create_snapshot(self, turn: TurnInput) -> TurnContextSnapshot:
        self._version += 1
        now = datetime.now(timezone.utc)
        ctx = turn.context
        return TurnContextSnapshot(
            turn_id=f"turn-{uuid4().hex[:12]}",
            trigger_type=turn.trigger_type,
            user_query=turn.user_query,
            screen_ref=ctx.get("screen_ref"),
            audio_ref=ctx.get("audio_ref"),
            thread_ref=ctx.get("thread_ref"),
            app_ref=ctx.get("active_app"),
            time_ref=now.isoformat(),
            reminder_ref=ctx.get("reminder_ref"),
            latest_chat_refs=ctx.get("latest_chat_refs", []),
            policy_state={},
            context_version=self._version,
        )
