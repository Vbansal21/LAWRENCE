from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FacetType(str, Enum):
    context = "context"
    memory = "memory"
    journaling = "journaling"
    web = "web"
    tools = "tools"
    fast_reasoning = "fast_reasoning"
    slow_reasoning = "slow_reasoning"


class TurnInput(BaseModel):
    trigger_type: str = Field(default="user_query")
    user_query: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    force_web: bool = False


class TurnContextSnapshot(BaseModel):
    turn_id: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trigger_type: str
    user_query: str | None = None
    screen_ref: str | None = None
    audio_ref: str | None = None
    thread_ref: str | None = None
    app_ref: str | None = None
    time_ref: str
    reminder_ref: str | None = None
    latest_chat_refs: list[str] = Field(default_factory=list)
    policy_state: dict[str, Any] = Field(default_factory=dict)
    context_version: int = 1


class ToolActionProposal(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "low"
    requires_confirmation: bool = True
    policy_basis: str = "default"


class FacetResult(BaseModel):
    turn_id: str
    facet_type: FacetType
    confidence: float = 0.0
    latency_ms: int = 0
    payload_ref: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    actions: list[ToolActionProposal] = Field(default_factory=list)
    context_version: int


class MergeDecision(BaseModel):
    turn_id: str
    immediate_response: str
    deferred_allowed: bool = True
    deferred_response: str | None = None
    overlay_updates: list[str] = Field(default_factory=list)
    followups: list[str] = Field(default_factory=list)
    structured_outputs: dict[str, Any] = Field(default_factory=dict)


class DistillationRecord(BaseModel):
    source_ref: str
    distilled_into: str
    retention_policy: str
    expires_at: datetime | None = None


class TurnResponse(BaseModel):
    snapshot: TurnContextSnapshot
    merge_decision: MergeDecision
    facet_results: list[FacetResult]
    distillation_records: list[DistillationRecord]


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    providers: dict[str, str] = Field(default_factory=dict)


class NoteCreateRequest(BaseModel):
    note_type: str = "knowledge_note"
    title: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    confidence: float = 0.7
    privacy_level: str = "local"


class NoteSearchResponse(BaseModel):
    query: str
    tags: list[str] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)


class NoteGraphResponse(BaseModel):
    note_id: str
    max_hops: int
    nodes: list[dict[str, Any]] = Field(default_factory=list)


class ToolExecutionRequest(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = True
    confirmed: bool = False
    risk_level: str = "low"
    policy_basis: str = "n8n_agentic_loop"


class ToolExecutionResponse(BaseModel):
    ok: bool
    tool: str
    result: dict[str, Any] = Field(default_factory=dict)
    blocked_reason: str | None = None
