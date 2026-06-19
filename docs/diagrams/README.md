# System diagrams (N-68)

Two diagrams for **every LAWRENCE subsystem whose code runs in the live process** —
required MVP deliverable per [PLAN.md](../PLAN.md) **N-68** (§O).

## The two views (what each one is — and is NOT)

**1. `<subsystem>.granular.mmd` — systems architecture (generalized, yet granular).**
The real components as **generalized roles** (e.g. *relevance ranker*, *rank-fusion*,
*associative store* — **not** "BM25", "RRF", "MemoryIndex") and, crucially, **how the
subsystem meshes with the other subsystems** — the gears — with the **nature of each
coupling labelled on the edge** (realtime / transient / independent · temporally-atomic ·
async-decoupled · least-privilege model seam · proactive invocation · context-refined ·
single-writer · persist-before-act). It is *not* a transcription of source code (no `def`s
or signatures) and *not* generic `process`/`store` boxes. You could reimplement the
subsystem differently and the diagram still holds.

**2. `<subsystem>.n8n.mmd` — the same subsystem rebuilt in n8n's node library.**
Real n8n nodes (Schedule/Webhook/Execute-Workflow Trigger, Code, IF, Switch, Merge, Loop
Over Items, HTTP Request, Wait / Wait-for-Webhook, AI Agent, Basic LLM Chain + Output
Parser, Vector Store, Data store, Respond) honoring n8n's **real restrictions** — each
restriction that forces the shape is called out inline with an `n8n:` note. Recurring ones:
no realtime capture loop (sensors stay native, ingress via trigger); stateless per
execution (rolling/tier/window state lives in Static Data or an external store); loops only
via Loop-Over-Items cap or Execute-Workflow recursion; branch recombination needs an
explicit Merge; **no SSE / no token streaming** (the live UI event channel can't be n8n);
invariants like single-writer (I1) and the policy gate are convention (a shared
sub-workflow every caller must Execute), not enforced by the engine.

## Pipeline

Authoring is **mermaid.js** (`src/*.mmd`). Rendering + the legibility gate go through
**Graphviz `dot`** (its Sugiyama layered layout = topological layering + barycenter
crossing-minimization, the "graph algorithm for ordering"), which renders SVG headlessly:

```
python3 docs/diagrams/tools/mmd2svg.py build           # all src/*.mmd -> svg/ + lint table
python3 docs/diagrams/tools/mmd2svg.py build src/x.mmd
```

The lint reads real `dot -Tplain` geometry and fails the build if a diagram busts the
legibility budget (`crossings ≤ 12`, `widest_rank ≤ 9`, `nodes ≤ 40`, `overlaps == 0`) —
the signal to split it. `svg/*.svg` are generated artifacts; regenerate, don't hand-edit.

> **Sandbox note:** a headless raster *view* isn't available here (wrong-arch puppeteer
> chromium; no cairosvg/rsvg). The SVGs are valid and render in any browser / VSCode /
> GitHub; the `dot` geometry lint is the automated legibility gate in the meantime.

## Edge / shape legend

| Notation | Meaning |
|---|---|
| `-->` | synchronous / in-process flow |
| `==>` | hot / load-bearing path |
| `-.->` | async event, iteration feedback, or non-blocking dispatch (no synchronous return) |
| `<-->` | bidirectional coupling (query/response) |
| `---` | undirected association |
| `subgraph` | a grouping (independent-lifecycle set, or a fan-in/fan-out cluster) |
| `[box]` process · `{diamond}` decision · `([stadium])` terminal/actor · `[(cylinder)]` store · `>flag]` external note |

## The 14 subsystems

| # | Subsystem | granular | n8n | code |
|---|---|---|---|---|
| S1 | Perception / sensors | [✓](svg/sensors.granular.svg) | [✓](svg/sensors.n8n.svg) | `obs/` + `sensor.py` |
| S2 | Context gating + distillation | [✓](svg/context-gating.granular.svg) | [✓](svg/context-gating.n8n.svg) | `ctx/{gate,significance,extract,distill,store}.py` |
| S3 | Cognitive kernel / proactive loop | [✓](svg/kernel.granular.svg) | [✓](svg/kernel.n8n.svg) | `kernel/{tick,invoke,elevate}.py` |
| S4 | Retrieval engine | [✓](svg/retrieval.granular.svg) | [✓](svg/retrieval.n8n.svg) | `retrieval/engine.py` (§J) |
| S5 | Memory + notes graph | [✓](svg/memory.granular.svg) | [✓](svg/memory.n8n.svg) | `retrieval/memory.py`, `ctx/{notes,store,chats}.py` |
| S6 | Journal (WS-J) | [✓](svg/journal.granular.svg) | [✓](svg/journal.n8n.svg) | `kernel/journal.py` |
| S7 | Model gateway + serving | [✓](svg/model.granular.svg) | [✓](svg/model.n8n.svg) | `model.py`, `server.py` |
| S8 | Agency / effectors | [✓](svg/agency.granular.svg) | [✓](svg/agency.n8n.svg) | `agency.py` |
| S9 | Scheduler / temporal intents | [✓](svg/scheduler.granular.svg) | [✓](svg/scheduler.n8n.svg) | `schedule.py`, `tasks.py` |
| S10 | Notifications | [✓](svg/notify.granular.svg) | [✓](svg/notify.n8n.svg) | `notify.py` |
| S11 | Policy / privacy / redaction | [✓](svg/policy.granular.svg) | [✓](svg/policy.n8n.svg) | `policy.py` (D-33) |
| S12 | Capability resolution | [✓](svg/capabilities.granular.svg) | [✓](svg/capabilities.n8n.svg) | `capabilities.py` |
| S13 | Desktop UI bridge | [✓](svg/ui-bridge.granular.svg) | [✓](svg/ui-bridge.n8n.svg) | `apps/desktop/scripts/ui_bridge.py` |
| S14 | Control plane / CLI | [✓](svg/control-cli.granular.svg) | [✓](svg/control-cli.n8n.svg) | `cli.py ctl.py admin.py memops.py config.py` |

## Adding / changing a diagram
1. Edit `src/<name>.{granular,n8n}.mmd` (stay within the mermaid subset in `tools/mmd2svg.py`).
2. `python3 docs/diagrams/tools/mmd2svg.py build` — must print `OK`.
3. Update the table above. Regenerate `svg/`; never hand-edit it.
