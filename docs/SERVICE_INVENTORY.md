# LAWRENCE service inventory (N-66)

| Node | Objective | Owns | Contract | Invariants |
|---|---|---|---|---|
| **S1 Perception / sensors** | Capture the live environment continuously and emit clean, timestamped perception events independently of the model. | sensor.py<br>obs/audio.py<br>obs/vision.py<br>obs/regions.py<br>obs/spool.py | obs/vision.py:VisionObserver<br>obs/audio.py:AudioObserver<br>sensor.py:main | SENSOR-DECOUPLE, LOCAL-FIRST, I4 |
| **S10 Notifications** | Be the single throttled, deduplicated choke point for surfacing notifications to the host. | notify.py | notify.py:notify | I4 |
| **S11 Policy / privacy / redaction** | Enforce the privacy/trust boundary on every cross-boundary payload before it leaves the local process. | policy.py | policy.py | LOCAL-FIRST, I4 |
| **S12 Capability resolution** | Resolve which capability layer/route handles a request and report each capability honestly. | capabilities.py | capabilities.py | I4 |
| **S13 Desktop UI bridge** | Bridge the desktop UI to the kernel over a stable HTTP+SSE contract (transport only, no business logic). | apps/desktop/scripts/ui_bridge.py<br>ui/connector.py | apps/desktop/scripts/ui_bridge.py:DesktopBridge<br>ui/connector.py:UIConnector | I5, I4 |
| **S14 Control plane / CLI** | Start, stop, configure, and inspect the running system from the operator surface. | cli.py<br>ctl.py<br>admin.py<br>config.py<br>logger.py | cli.py:main<br>ctl.py<br>admin.py<br>config.py | I6, I4 |
| **S2 Context gating + distillation** | Turn the raw perception stream into gated, deduplicated, distilled context with a graded significance score. | ctx/gate.py<br>ctx/significance.py<br>ctx/extract.py<br>ctx/distill.py | ctx/gate.py<br>ctx/significance.py:Grader<br>ctx/distill.py<br>ctx/extract.py | I4, LOCAL-FIRST |
| **S3 Cognitive kernel / proactive loop** | Orchestrate each turn and the proactive loop: assemble context, drive retrieval, and produce the answer or unprompted finding. | kernel/invoke.py<br>kernel/tick.py<br>kernel/elevate.py<br>kernel/refine.py<br>kernel/prompts.py<br>kernel/schemas.py<br>kernel/turncache.py | kernel/invoke.py:run_turn<br>kernel/invoke.py:run_proactive<br>kernel/tick.py | I3, I4 |
| **S4 Retrieval engine** | Return one fused, provenance-tagged evidence bundle over memory, documents, and the web for a query. | retrieval/engine.py<br>retrieval/pipeline.py<br>retrieval/ranker.py<br>retrieval/web.py<br>retrieval/ingest.py<br>retrieval/reindex.py<br>retrieval/db.py<br>retrieval/vectors.py<br>converters.py | retrieval/engine.py:RetrievalEngine<br>retrieval/reindex.py<br>retrieval/ingest.py | I3, I4, LOCAL-FIRST |
| **S5 Memory + notes graph** | Be the single durable writer and queryable store for tiered memory, chats, and the linked-note graph. | retrieval/memory.py<br>ctx/store.py<br>ctx/notes.py<br>ctx/chats.py<br>ctx/promote.py<br>memops.py | ctx/store.py:ContextStore<br>ctx/notes.py:NoteStore<br>ctx/chats.py:ChatStore<br>retrieval/memory.py:MemoryIndex<br>ctx/promote.py:promote_turn | I1, I4, LOCAL-FIRST |
| **S6 Journal (WS-J)** | Maintain the autonomous, first-person rolling-revision journal as durable episodic memory. | kernel/journal.py | kernel/journal.py | I1, I3, I4 |
| **S7 Model gateway + serving** | Be the one seam that turns a role request into tokens from a local-first, replaceable LLM provider. | model.py<br>server.py<br>profile.py | model.py:call_model<br>model.py:embed<br>server.py<br>profile.py:ModelProfile | I3, LOCAL-FIRST, I4 |
| **S8 Agency / effectors** | Propose state-changing actions and execute only the user-confirmed, allowlisted ones. | agency.py | agency.py | I4 |
| **S9 Scheduler / temporal intents** | Persist temporal intents (reminders/tasks) durably and fire them when due. | schedule.py<br>tasks.py | schedule.py<br>tasks.py | I4 |

> Generated from services/lk/services.py (N-66). Do not hand-edit; run `python3 -m lk.services`. Partition gate-guarded by services/lk/tests/test_services.py.
