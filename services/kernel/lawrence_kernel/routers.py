from __future__ import annotations

from fastapi import APIRouter, Query

from lawrence_kernel.models import (
    HealthResponse,
    NoteCreateRequest,
    NoteGraphResponse,
    NoteSearchResponse,
    ToolActionProposal,
    ToolExecutionRequest,
    ToolExecutionResponse,
    TurnInput,
    TurnResponse,
)
from lawrence_kernel.orchestrator import AssistantKernel

router = APIRouter()
kernel = AssistantKernel()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app="LAWRENCE",
        version="0.1.0",
        providers=kernel.llm.provider_health(),
    )


@router.post("/v1/turns", response_model=TurnResponse)
async def process_turn(turn: TurnInput) -> TurnResponse:
    return await kernel.handle_turn(turn)


@router.post("/v1/memory/notes")
async def create_note(req: NoteCreateRequest) -> dict[str, str]:
    note_path = kernel.memory.zettel.create_note(
        note_type=req.note_type,
        title=req.title,
        summary=req.summary,
        tags=req.tags,
        entities=req.entities,
        source_refs=req.source_refs,
        links=req.links,
        confidence=req.confidence,
        privacy_level=req.privacy_level,
    )
    note_id = note_path.stem
    suggested = kernel.memory.zettel.suggest_links(note_id, max_links=8)
    if suggested:
        kernel.memory.zettel.update_links(note_id, suggested)
    return {"note_id": note_id, "path": str(note_path)}


@router.get("/v1/memory/search", response_model=NoteSearchResponse)
async def search_notes(query: str = "", tags: str = "", top_k: int = Query(default=8, ge=1, le=30)) -> NoteSearchResponse:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    results = kernel.memory.zettel.search(query=query, tags=tag_list, top_k=top_k)
    return NoteSearchResponse(query=query, tags=tag_list, results=results)


@router.get("/v1/memory/graph/{note_id}", response_model=NoteGraphResponse)
async def graph_neighbors(note_id: str, max_hops: int = Query(default=2, ge=1, le=6)) -> NoteGraphResponse:
    nodes = kernel.memory.zettel.multi_hop_neighbors(note_id=note_id, max_hops=max_hops, max_nodes=50)
    return NoteGraphResponse(note_id=note_id, max_hops=max_hops, nodes=nodes)


@router.post("/v1/tools/execute", response_model=ToolExecutionResponse)
async def execute_tool(req: ToolExecutionRequest) -> ToolExecutionResponse:
    if req.requires_confirmation and not req.confirmed:
        return ToolExecutionResponse(
            ok=False,
            tool=req.tool,
            result={},
            blocked_reason="requires_confirmation_but_not_confirmed",
        )

    proposal = ToolActionProposal(
        tool=req.tool,
        args=req.args,
        risk_level=req.risk_level,
        requires_confirmation=req.requires_confirmation,
        policy_basis=req.policy_basis,
    )
    result = await kernel.tools.execute_action(proposal)
    return ToolExecutionResponse(ok=bool(result.get("ok", False)), tool=req.tool, result=result)
