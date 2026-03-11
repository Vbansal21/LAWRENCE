import asyncio

from lawrence_kernel.models import NoteCreateRequest, ToolExecutionRequest, TurnInput
from lawrence_kernel.routers import create_note, execute_tool, graph_neighbors, health, kernel, search_notes


def test_health() -> None:
    response = asyncio.run(health())
    assert response.status == "ok"
    assert response.providers


def test_turn_pipeline() -> None:
    turn = TurnInput(
        trigger_type="user_query",
        user_query="Find related context about project planning",
        context={"active_app": "editor", "thread_ref": "thread-1"},
    )
    response = asyncio.run(kernel.handle_turn(turn))

    assert response.snapshot.turn_id.startswith("turn-")
    assert response.merge_decision.immediate_response
    assert len(response.facet_results) > 0
    assert len(response.distillation_records) == 1


def test_zettelkasten_create_search_graph() -> None:
    create_resp = asyncio.run(
        create_note(
            req=NoteCreateRequest(
                note_type="knowledge_note",
                title="llama.cpp workflow integration",
                summary="Integrate n8n workflow with llama.cpp and zettel linking.",
                tags=["llamacpp", "n8n", "zettel"],
                entities=["lawrence", "llamacpp"],
                source_refs=["test:zettel"],
                links=[],
                confidence=0.82,
                privacy_level="local",
            )
        )
    )
    note_id = create_resp["note_id"]
    assert note_id

    search_resp = asyncio.run(search_notes(query="llama.cpp n8n zettel", tags="n8n", top_k=5))
    assert search_resp.results
    assert any(r["note_id"] == note_id for r in search_resp.results)

    graph_resp = asyncio.run(graph_neighbors(note_id=note_id, max_hops=2))
    assert graph_resp.nodes
    assert graph_resp.nodes[0]["note_id"] == note_id


def test_tool_execute_confirmation_gate() -> None:
    blocked = asyncio.run(
        execute_tool(
            req=ToolExecutionRequest(
                tool="local.command",
                args={"intent": "run dangerous command"},
                requires_confirmation=True,
                confirmed=False,
                risk_level="medium",
                policy_basis="test",
            )
        )
    )
    assert blocked.ok is False
    assert blocked.blocked_reason == "requires_confirmation_but_not_confirmed"
