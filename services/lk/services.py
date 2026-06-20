"""Atomic service registry — N-66 (ATOMIC / nodal subsystems).

The single, machine-checkable source of truth for LAWRENCE's subsystem
*partition*: every subsystem that runs in the live process is declared here as a
**node** with exactly one objective, the modules it owns, its public contract,
the invariant it must preserve, and how it meshes (couples) with the other nodes.

This is the near-term half of N-66: atomize *now*, behind the existing in-process
calls, so the boundary is explicit, disjoint, and gate-guarded — then N-64 lifts
each node into the n8n graph later without re-discovering the seams.

Design rules (so this file stays honest, not decorative):
  * **Disjoint + total.** Every engine module under ``services/lk`` is owned by
    exactly one node (see ``EXEMPT`` for the small, reasoned shared-infra set).
    ``test_services.py`` fails the build if a new module appears unowned or two
    nodes claim the same file — keeping the partition atomic as the code evolves.
  * **One objective per node.** ``objective`` is a single sentence; a node that
    needs "X and Y" is two nodes.
  * **Couplings are typed.** Each edge to another node carries a coupling
    *nature* from ``ALLOWED_NATURES`` (the diagram legend vocabulary) so the mesh
    is inspectable and matches docs/diagrams.
  * **Invariants are declared.** A node that writes durable memory must declare
    ``I1`` (single-writer); a node that picks a model provider must declare
    ``I3`` (provider seam). The test enforces these.

Pure stdlib (I4). Importing this module has no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── vocabularies ────────────────────────────────────────────────────────────

# Coupling natures — the edge-label vocabulary from docs/diagrams/README.md.
ALLOWED_NATURES = {
    "realtime",            # always-on, pushes data continuously
    "transient",          # one-shot request/response
    "independent",        # decoupled lifecycle (no synchronous return)
    "temporally-atomic",  # grounded in a single timestamped event
    "async-decoupled",    # dispatched, result arrives later / out of band
    "least-privilege-model-seam",  # crosses the model.py provider seam only
    "proactive-invocation",        # invoked by the proactive/tick path, not a user turn
    "context-refined",    # consumes/refines assembled context
    "single-writer",      # write goes through the one owner (I1)
    "persist-before-act", # durably logged before any downstream effect
    "query-response",     # synchronous read query
}

# Invariants a node may have to preserve (subset of the project invariants).
ALLOWED_INVARIANTS = {
    "I1",            # single memory writer
    "I3",            # provider logic only behind model.py
    "I4",            # stdlib core + graceful degrade
    "I5",            # add endpoints, never rename
    "I6",            # never touch editor/.code-workspace config
    "LOCAL-FIRST",   # never default personal-data subsystems to a cloud API
    "SENSOR-DECOUPLE",  # model probes sensor data, never toggles sensor lifecycle
}

# Modules that are deliberately NOT owned by a single subsystem node, with the
# reason. The coverage test skips these. Keep this list short and justified.
EXEMPT = {
    "services.py": "this registry itself (meta, not a subsystem)",
    "lock.py": "shared cross-cutting primitive (single-instance file lock)",
    "debuglog.py": "shared cross-cutting primitive ([debug] logger + counters)",
}
# Directory prefixes whose modules are exempt wholesale (with reason).
EXEMPT_PREFIXES = {
    "tests/": "test harness, not runtime",
    "launcher/": "PySide6 desktop launcher GUI — a control surface that folds "
                 "conceptually into S14, not an engine subsystem node",
    "__init__.py": "package markers",
}


@dataclass(frozen=True)
class Coupling:
    target: str   # node id, e.g. "S4"
    nature: str   # one of ALLOWED_NATURES
    note: str = ""


@dataclass(frozen=True)
class ServiceNode:
    id: str
    title: str
    objective: str                 # ONE sentence — the single responsibility
    modules: tuple[str, ...]       # owned module paths, relative to services/lk
    inputs: str
    outputs: str
    contract: tuple[str, ...]      # public entrypoints (the stable call surface)
    couplings: tuple[Coupling, ...]
    invariants: tuple[str, ...]
    writes_memory: bool = False    # if True, must own the write and declare I1


def _n(*nodes: ServiceNode) -> dict[str, ServiceNode]:
    return {x.id: x for x in nodes}


# ── the 14 nodes (S1–S14), mirroring docs/diagrams/README.md ────────────────

SERVICES: dict[str, ServiceNode] = _n(
    ServiceNode(
        id="S1", title="Perception / sensors",
        objective="Capture the live environment continuously and emit clean, timestamped perception events independently of the model.",
        modules=("sensor.py", "obs/audio.py", "obs/vision.py", "obs/regions.py",
                 "obs/spool.py", "obs/winhost.py"),
        inputs="screen frames, microphone audio, active-window layout",
        outputs="OCR text, transcripts, window/region events (to S2)",
        contract=("obs/vision.py:VisionObserver", "obs/audio.py:AudioObserver", "sensor.py:main"),
        couplings=(
            Coupling("S2", "realtime", "perception events stream into context gating"),
            Coupling("S14", "independent", "user (not the model) toggles sensor lifecycle"),
        ),
        invariants=("SENSOR-DECOUPLE", "LOCAL-FIRST", "I4"),
    ),
    ServiceNode(
        id="S2", title="Context gating + distillation",
        objective="Turn the raw perception stream into gated, deduplicated, distilled context with a graded significance score.",
        modules=("ctx/gate.py", "ctx/significance.py", "ctx/extract.py", "ctx/distill.py"),
        inputs="perception events (S1), recent context tail (S5)",
        outputs="distilled context units + significance (to S3, S5)",
        contract=("ctx/gate.py", "ctx/significance.py:Grader", "ctx/distill.py", "ctx/extract.py"),
        couplings=(
            Coupling("S1", "realtime", "consumes the perception stream"),
            Coupling("S5", "single-writer", "writes distilled units via the memory store owner"),
            Coupling("S3", "context-refined", "significance gates the proactive trigger"),
        ),
        invariants=("I4", "LOCAL-FIRST"),
    ),
    ServiceNode(
        id="S3", title="Cognitive kernel / proactive loop",
        objective="Orchestrate each turn and the proactive loop: assemble context, drive retrieval, and produce the answer or unprompted finding.",
        modules=("kernel/invoke.py", "kernel/tick.py", "kernel/elevate.py",
                 "kernel/refine.py", "kernel/prompts.py", "kernel/schemas.py",
                 "kernel/turncache.py"),
        inputs="user query / proactive trigger, assembled context, retrieved bundle",
        outputs="answer + findings (to S13), durable turn record (to S5/S6)",
        contract=("kernel/invoke.py:run_turn", "kernel/invoke.py:run_proactive", "kernel/tick.py"),
        couplings=(
            Coupling("S4", "query-response", "drives the retrieval engine per turn"),
            Coupling("S7", "least-privilege-model-seam", "all generation via the model gateway"),
            Coupling("S5", "single-writer", "turn records persisted via the memory owner"),
            Coupling("S6", "async-decoupled", "hands turns to the journal"),
            Coupling("S2", "proactive-invocation", "significance gates run_proactive"),
        ),
        invariants=("I3", "I4"),
    ),
    ServiceNode(
        id="S4", title="Retrieval engine",
        objective="Return one fused, provenance-tagged evidence bundle over memory, documents, and the web for a query.",
        modules=("retrieval/engine.py", "retrieval/pipeline.py", "retrieval/ranker.py",
                 "retrieval/web.py", "retrieval/ingest.py", "retrieval/reindex.py",
                 "retrieval/db.py", "retrieval/vectors.py", "converters.py"),
        inputs="query + context discernment (S3)",
        outputs="ranked, cited results bundle (to S3)",
        contract=("retrieval/engine.py:RetrievalEngine", "retrieval/reindex.py", "retrieval/ingest.py"),
        couplings=(
            Coupling("S5", "query-response", "lexical+vector+graph arms read the memory index"),
            Coupling("S7", "least-privilege-model-seam", "query formulation / assessment via the gateway"),
            Coupling("S3", "context-refined", "discernment shapes the arms"),
        ),
        invariants=("I3", "I4", "LOCAL-FIRST"),
    ),
    ServiceNode(
        id="S5", title="Memory + notes graph",
        objective="Be the single durable writer and queryable store for tiered memory, chats, and the linked-note graph.",
        modules=("retrieval/memory.py", "ctx/store.py", "ctx/notes.py", "ctx/chats.py",
                 "ctx/promote.py", "memops.py"),
        inputs="distilled context (S2), turn records (S3), promotions",
        outputs="index rows + note edges (to S4), recall (to S3)",
        contract=("ctx/store.py:ContextStore", "ctx/notes.py:NoteStore", "ctx/chats.py:ChatStore",
                  "retrieval/memory.py:MemoryIndex", "ctx/promote.py:promote_turn"),
        couplings=(
            Coupling("S4", "query-response", "exposes the index the retrieval arms read"),
            Coupling("S6", "async-decoupled", "serves journal entry persistence on the writer discipline"),
        ),
        invariants=("I1", "I4", "LOCAL-FIRST"),
        writes_memory=True,
    ),
    ServiceNode(
        id="S6", title="Journal (WS-J)",
        objective="Maintain the autonomous, first-person rolling-revision journal as durable episodic memory.",
        modules=("kernel/journal.py",),
        inputs="closed turns / sessions (S3)",
        outputs="revised journal entries (to S5)",
        contract=("kernel/journal.py",),
        couplings=(
            Coupling("S3", "async-decoupled", "consumes closed turns off the turn path"),
            Coupling("S5", "single-writer", "entries persisted via the memory writer"),
            Coupling("S7", "least-privilege-model-seam", "revision drafted via the gateway"),
        ),
        invariants=("I1", "I3", "I4"),
    ),
    ServiceNode(
        id="S7", title="Model gateway + serving",
        objective="Be the one seam that turns a role request into tokens from a local-first, replaceable LLM provider.",
        modules=("model.py", "server.py", "profile.py"),
        inputs="role + prompt + sampling (any subsystem)",
        outputs="completion / embedding tokens",
        contract=("model.py:call_model", "model.py:embed", "server.py", "profile.py:ModelProfile"),
        couplings=(
            Coupling("S12", "transient", "capability resolution selects role routing"),
        ),
        invariants=("I3", "LOCAL-FIRST", "I4"),
    ),
    ServiceNode(
        id="S8", title="Agency / effectors",
        objective="Propose state-changing actions and execute only the user-confirmed, allowlisted ones.",
        modules=("agency.py",),
        inputs="proposed action (S3), user confirmation (S13)",
        outputs="audited, confirmed effect",
        contract=("agency.py",),
        couplings=(
            Coupling("S11", "transient", "every effect passes the policy gate"),
            Coupling("S13", "transient", "confirmation flows from the UI"),
        ),
        invariants=("I4",),
    ),
    ServiceNode(
        id="S9", title="Scheduler / temporal intents",
        objective="Persist temporal intents (reminders/tasks) durably and fire them when due.",
        modules=("schedule.py", "tasks.py"),
        inputs="reminder/task intents (S3/S13)",
        outputs="due events (to S3/S13)",
        contract=("schedule.py", "tasks.py"),
        couplings=(
            Coupling("S3", "async-decoupled", "due events surface through the kernel"),
        ),
        invariants=("I4",),
    ),
    ServiceNode(
        id="S10", title="Notifications",
        objective="Be the single throttled, deduplicated choke point for surfacing notifications to the host.",
        modules=("notify.py",),
        inputs="title+body (any subsystem)",
        outputs="host notification (gated)",
        contract=("notify.py:notify",),
        couplings=(
            Coupling("S3", "transient", "proactive findings surface here"),
        ),
        invariants=("I4",),
    ),
    ServiceNode(
        id="S11", title="Policy / privacy / redaction",
        objective="Enforce the privacy/trust boundary on every cross-boundary payload before it leaves the local process.",
        modules=("policy.py",),
        inputs="outbound payload + destination (S4/S7/S8)",
        outputs="redacted/allowed payload or refusal",
        contract=("policy.py",),
        couplings=(
            Coupling("S7", "least-privilege-model-seam", "gates payloads bound for any non-local provider"),
        ),
        invariants=("LOCAL-FIRST", "I4"),
    ),
    ServiceNode(
        id="S12", title="Capability resolution",
        objective="Resolve which capability layer/route handles a request and report each capability honestly.",
        modules=("capabilities.py",),
        inputs="request shape + provider/model facts",
        outputs="route decision + capability markers",
        contract=("capabilities.py",),
        couplings=(
            Coupling("S7", "transient", "feeds role routing decisions"),
        ),
        invariants=("I4",),
    ),
    ServiceNode(
        id="S13", title="Desktop UI bridge",
        objective="Bridge the desktop UI to the kernel over a stable HTTP+SSE contract (transport only, no business logic).",
        modules=("apps/desktop/scripts/ui_bridge.py", "ui/connector.py"),
        inputs="UI requests (HTTP), kernel events (SSE)",
        outputs="JSON responses + the SSE event stream",
        contract=("apps/desktop/scripts/ui_bridge.py:DesktopBridge", "ui/connector.py:UIConnector"),
        couplings=(
            Coupling("S3", "query-response", "turns/chat ops call the kernel"),
            Coupling("S5", "query-response", "chat/link reads go to the store owner"),
        ),
        invariants=("I5", "I4"),
    ),
    ServiceNode(
        id="S14", title="Control plane / CLI",
        objective="Start, stop, configure, and inspect the running system from the operator surface.",
        modules=("cli.py", "ctl.py", "admin.py", "config.py", "logger.py"),
        inputs="operator commands + config",
        outputs="process lifecycle, config, status",
        contract=("cli.py:main", "ctl.py", "admin.py", "config.py"),
        couplings=(
            Coupling("S1", "independent", "user toggles sensors here"),
            Coupling("S7", "transient", "starts/stops the model server"),
        ),
        invariants=("I6", "I4"),
    ),
)


# ── introspection + validation ──────────────────────────────────────────────

def owned_modules() -> dict[str, str]:
    """Map every owned module path -> owning node id."""
    out: dict[str, str] = {}
    for node in SERVICES.values():
        for m in node.modules:
            out[m] = node.id
    return out


def validate_registry() -> list[str]:
    """Return a list of structural problems; empty == the partition is sound.

    Pure declaration-level checks (no filesystem) so callers can use this as a
    cheap invariant guard; ``test_services.py`` adds the on-disk coverage check.
    """
    problems: list[str] = []

    # one objective = one sentence (no compound "and"-joined objectives)
    for node in SERVICES.values():
        obj = node.objective.strip()
        if not obj.endswith("."):
            problems.append(f"{node.id}: objective must be a single sentence ending in '.'")
        if obj.count(".") > 1:
            problems.append(f"{node.id}: objective looks like >1 sentence (atomicity)")

    # disjoint ownership
    seen: dict[str, str] = {}
    for node in SERVICES.values():
        for m in node.modules:
            if m in seen:
                problems.append(f"module {m} owned by both {seen[m]} and {node.id}")
            seen[m] = node.id

    # couplings reference valid nodes + use the allowed vocabulary
    for node in SERVICES.values():
        for c in node.couplings:
            if c.target not in SERVICES:
                problems.append(f"{node.id}: coupling to unknown node {c.target}")
            if c.target == node.id:
                problems.append(f"{node.id}: self-coupling is not a mesh edge")
            if c.nature not in ALLOWED_NATURES:
                problems.append(f"{node.id}->{c.target}: unknown coupling nature '{c.nature}'")

    # invariants from the allowed set
    for node in SERVICES.values():
        for inv in node.invariants:
            if inv not in ALLOWED_INVARIANTS:
                problems.append(f"{node.id}: unknown invariant '{inv}'")

    # a memory writer must own the write and declare I1
    for node in SERVICES.values():
        if node.writes_memory and "I1" not in node.invariants:
            problems.append(f"{node.id}: writes_memory but does not declare I1")
    writers = [n.id for n in SERVICES.values() if n.writes_memory]
    if len(writers) != 1:
        problems.append(f"exactly one memory-writer node expected, found {writers}")

    return problems


def inventory_markdown() -> str:
    """Render the service inventory as a Markdown table (for docs / --inventory)."""
    lines = ["# LAWRENCE service inventory (N-66)", "",
             "| Node | Objective | Owns | Contract | Invariants |",
             "|---|---|---|---|---|"]
    for nid in sorted(SERVICES):
        n = SERVICES[nid]
        owns = "<br>".join(n.modules)
        con = "<br>".join(n.contract)
        inv = ", ".join(n.invariants)
        lines.append(f"| **{n.id} {n.title}** | {n.objective} | {owns} | {con} | {inv} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    import sys
    probs = validate_registry()
    if probs:
        print("REGISTRY PROBLEMS:")
        for p in probs:
            print("  -", p)
        sys.exit(1)
    print(inventory_markdown())
