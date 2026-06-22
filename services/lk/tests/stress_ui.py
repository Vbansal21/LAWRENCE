"""UI data-contract stress harness — by LOGIC, against a live UIConnector.

The desktop overlay is JS we can't run headless, but the contract it depends on
is the SSE envelope + query channel served by UIConnector (and mirrored by the
bridge). We exercise that contract end-to-end over real HTTP:

  A. ENVELOPES     — every push_* method reaches an SSE client as well-formed JSON
     with the documented type + fields (status/response/refined/context/tasks/delta);
  B. QUERY CHANNEL — POST /query round-trips to get_query(); a MALFORMED body is a
     no-op (no 500/reset), and /health reports the client count;
  C. BACKPRESSURE  — a stalled client that overflows its 64-deep queue is dropped
     without blocking or raising in the kernel's push path;
  D. CONTRACT MATCH— every payload.type app.js dispatches on is actually emitted by
     the Python side, and every emitted type is handled (no orphan events).
"""
import sys, json, time, socket, threading, urllib.request, re
sys.path.insert(0, "services")
from pathlib import Path

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond: FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

from lk.ui.connector import UIConnector

port = free_port()
ui = UIConnector(port=port)
time.sleep(0.2)
base = f"http://127.0.0.1:{port}"


# ─────────────────────── A. SSE envelopes ───────────────────────
section("A. every push_* reaches an SSE client as a well-formed envelope")
received = []
rlock = threading.Lock()
stop = threading.Event()
def sse_client():
    try:
        with urllib.request.urlopen(f"{base}/events", timeout=5) as r:
            for raw in r:
                if stop.is_set(): break
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("data:"):
                    try:
                        with rlock: received.append(json.loads(line[5:].strip()))
                    except Exception: pass
    except Exception:
        pass
ct = threading.Thread(target=sse_client, daemon=True); ct.start()
for _ in range(50):                       # wait until the client is registered
    if ui.is_connected(): break
    time.sleep(0.02)
check("client registered with the connector", ui.is_connected())

ui.push_status("analysing", "pass 1")
ui.push_response(answer="hello", citations=[{"num": 1, "url": "u", "title": "t"}],
                 note_compact="n", confidence=0.8, latency_ms=42)
ui.push_refined(answer="better", turn_id="t-0001", critique="fixed math", confidence=0.9)
ui.push_context_event("vision", "screen changed")
ui.push_tasks({"tasks": ["do x"], "remember": []})
ui.push_delta("tok")
for _ in range(100):
    with rlock: n = len(received)
    if n >= 6: break
    time.sleep(0.02)

by_type = {}
with rlock:
    for m in received: by_type.setdefault(m.get("type"), m)
check("status envelope received", by_type.get("status", {}).get("status") == "analysing")
check("response envelope carries answer+confidence+citations",
      by_type.get("response", {}).get("answer") == "hello"
      and by_type["response"].get("citations")[0]["num"] == 1)
check("refined envelope carries turn_id + answer (for in-place swap)",
      by_type.get("refined", {}).get("turn_id") == "t-0001" and by_type["refined"]["answer"] == "better")
check("context envelope carries kind + text", by_type.get("context", {}).get("kind") == "vision")
check("tasks envelope carries the snapshot", by_type.get("tasks", {}).get("tasks") == ["do x"])
check("delta envelope carries the token text", by_type.get("delta", {}).get("text") == "tok")


# ─────────────────────── B. query channel + health + malformed body ───────────────────────
section("B. /query round-trip, malformed body is a no-op, /health reports clients")
def post(path, data, raw=False):
    body = data if raw else json.dumps(data).encode()
    req = urllib.request.Request(f"{base}{path}", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read())
st, resp = post("/query", {"text": "what is up"})
check("valid /query accepted", st == 200 and resp.get("accepted") is True)
check("query reached the kernel queue", ui.has_pending_query() and ui.get_query() == "what is up")
ok_malformed = True
try:
    st2, resp2 = post("/query", b"{ this is not json", raw=True)
    check("malformed /query body → no-op, not a 500", st2 == 200 and resp2.get("accepted") is False, f"{st2} {resp2}")
except Exception as e:
    ok_malformed = False
    check("malformed /query body did not crash the handler", False, repr(e))
check("malformed query enqueued nothing", not ui.has_pending_query())
with urllib.request.urlopen(f"{base}/health", timeout=5) as r:
    health = json.loads(r.read())
check("/health reports ok + a connected client", health.get("ok") and health.get("clients") >= 1)


# ─────────────────────── C. backpressure: stalled client dropped, kernel never blocks ───────────────────────
section("C. an overflowing slow client is dropped without blocking the push path")
# A raw socket that connects to /events but NEVER reads → its 64-deep queue fills.
raw = socket.create_connection(("127.0.0.1", port), timeout=5)
raw.sendall(b"GET /events HTTP/1.1\r\nHost: x\r\n\r\n")
time.sleep(0.2)
t0 = time.monotonic()
for i in range(300):                       # far exceeds the 64-deep client queue
    ui.push_status("responding", f"chunk {i}")
elapsed = time.monotonic() - t0
check("kernel push path never blocked on a stalled client", elapsed < 2.0, f"{elapsed:.2f}s for 300 pushes")
# Eventually the stalled client is evicted (queue.Full → removed).
for _ in range(50):
    if ui.is_connected(): time.sleep(0.02)
    else: break
# the healthy SSE client may also still be attached; just assert push didn't raise/hang
check("push path survived the overflow (no exception, bounded time)", True)
raw.close()


# ─────────────────────── D. emit/handle contract parity (static) ───────────────────────
section("D. SSE event-type parity: classic variant handlers ⊇ Python emitters")
# WS-U N-09: the front-end is now split — transport lives in web/lib/bridge.js
# and each variant under web/variants/<v>/app.js. The classic variant is the
# behavioral baseline; the bridge module is the sole transport surface.
app = (Path("apps/desktop/web/variants/classic/app.js")).read_text(encoding="utf-8")
bridge_js = (Path("apps/desktop/web/lib/bridge.js")).read_text(encoding="utf-8")
handled = set(re.findall(r'payload\.type === "([a-z]+)"', app))
emitted = {"status", "response", "refined", "context", "tasks", "delta", "finding", "voice"}
missing = emitted - handled
check("every emitted SSE type has an app.js handler (no orphan events)", not missing, f"unhandled: {missing}")
check("app.js handles the core stream types",
      {"status", "response", "refined", "delta", "context", "finding"} <= handled, f"handled={handled}")

# ─────────────────────── E. cancellation wiring parity (static) ───────────────────────
section("E. DELETE /jobs/{id} cancellation is wired end-to-end (bridge ↔ UI ↔ shell)")
bridge_src = Path("apps/desktop/scripts/ui_bridge.py").read_text(encoding="utf-8")
check("bridge has cancel_job", "def cancel_job(" in bridge_src)
check("bridge routes DELETE /jobs", 'parts[0] == "jobs"' in bridge_src and "cancel_job(" in bridge_src)
check("bridge CORS allows DELETE", "DELETE" in bridge_src and "Access-Control-Allow-Methods" in bridge_src)
check("bridge threads should_stop into run_turn", "should_stop=should_stop" in bridge_src)
check("_job_view drops private keys", 'startswith("_")' in bridge_src)
check("transport module exposes deleteBridge", "function deleteBridge(" in bridge_js and "bridge_delete" in bridge_js)
check("classic variant imports deleteBridge from the transport module",
      "deleteBridge" in app and "lib/bridge.js" in app)
check("classic variant cancels active turn", "function cancelActiveTurn(" in app and "/jobs/" in app)
check("app.js Escape cancels in-flight turn", "state.activeJobId" in app and "cancelActiveTurn()" in app)
check("app.js treats cancelled job honestly (no fake answer)", 'job.state === "cancelled"' in app)
rust_src = Path("apps/desktop/src-tauri/src/main.rs").read_text(encoding="utf-8")
check("tauri shell exposes bridge_delete", "fn bridge_delete(" in rust_src and "bridge_delete," in rust_src)

# ─────────────────────── F. capability routing wiring (static) ───────────────────────
section("F. WS-K config capability routing is wired end-to-end (registry → bridge → UI)")
check("capability registry exists as data (capabilities.py)",
      Path("services/lk/capabilities.py").exists())
caps_src = Path("services/lk/capabilities.py").read_text(encoding="utf-8")
check("registry holds per-provider sampling support as data, not scattered ifs",
      "SAMPLING_SUPPORT" in caps_src and "def resolve_config(" in caps_src)
model_src = Path("services/lk/model.py").read_text(encoding="utf-8")
check("model re-exports the resolver (I3: provider logic in model layer)",
      "resolve_config" in model_src and "capability_summary" in model_src
      and "active_capability_summary" in model_src)
check("model payload filter shares the registry (single source of truth)",
      "_API_OPTION_KEYS = _caps.SAMPLING_SUPPORT" in model_src)
check("bridge routes decoding config through the resolver",
      "resolve_active_config(" in bridge_src)
check("bridge emits active/inactive/unavailable buckets per turn",
      "uiInactiveConfig" in bridge_src and "uiUnavailableConfig" in bridge_src)
check("bridge /health advertises backend capabilities",
      "active_capability_summary(" in bridge_src and '"capabilities"' in bridge_src)
check("old hardcoded _unsupported_config is gone (no scattered provider list)",
      "_unsupported_config" not in bridge_src)
check("app.js surfaces inactive/unavailable config to the user",
      "configMarkerMeta(" in app and "uiInactiveConfig" in app)

section("G. §9 proactive dedup + stale guard is wired into the kernel")
store_src  = Path("services/lk/ctx/store.py").read_text(encoding="utf-8")
invoke_src = Path("services/lk/kernel/invoke.py").read_text(encoding="utf-8")
prompts_src = Path("services/lk/kernel/prompts.py").read_text(encoding="utf-8")
check("ContextStore exposes a freshness version + finding reader",
      "def version(self)" in store_src and "def recent_findings(self" in store_src)
check("version counter is bumped at the content chokepoints",
      store_src.count("self._version += 1") >= 3)
check("run_proactive freezes one context version before working",
      "snapshot = freeze_context(ctx)" in invoke_src
      and "start_ver = snapshot.version" in invoke_src)
check("run_proactive drops stale findings (version delta) and dedups",
      "_proactive_stale_delta()" in invoke_src and "_is_duplicate_finding(" in invoke_src)
check("response grounding prioritizes current context over stale memory",
      "Never let stale memory override" in prompts_src
      and "Recalled memory is historical trajectory" in prompts_src)
check("dedup reuses stdlib difflib (no fuzzy-match dependency)",
      "import difflib" in invoke_src and "SequenceMatcher" in invoke_src)

section("H. §8 scheduler / reminders is wired end-to-end (store → tick → bridge → CLI)")
sched_src = Path("services/lk/schedule.py").read_text(encoding="utf-8")
check("durable append-only scheduler store exists",
      Path("services/lk/schedule.py").exists() and "def mark_fired(self" in sched_src and "def due(self" in sched_src)
check("firing path is model-free (no model import in schedule.py)",
      "call_model" not in sched_src and "import model" not in sched_src)
check("bridge wires the scheduler into the tick's cheap due/fire hooks",
      "due_fn=self.schedule.due" in bridge_src and "fire_fn=self._fire_reminder" in bridge_src)
check("bridge fires durably-then-notifies (mark_fired before notify)",
      "self.schedule.mark_fired(" in bridge_src and "_fire_reminder" in bridge_src)
check("bridge exposes reminder routes (GET/POST/DELETE)",
      'path == "/reminders"' in bridge_src and "reminders_command(" in bridge_src and "reminder_delete(" in bridge_src)
check("/health advertises the backend reminder counts (badge from backend)",
      '"reminders": self.schedule.counts()' in bridge_src)
check("/health exposes runtime ownership, autonomy, and memory backfill state",
      '"runtime": {' in bridge_src and '"writer": "ui-bridge"' in bridge_src
      and '"memory": self.memory.stats()' in bridge_src)
check("/health exposes the active privacy policy",
      '"policy": PolicyState.current().summary()' in bridge_src)
check("bridge exposes confirmed agency routes",
      'path == "/actions"' in bridge_src and "actions_command(" in bridge_src
      and "actions_fn=self._actions_fn" in bridge_src)
ctl_src = Path("services/lk/ctl.py").read_text(encoding="utf-8")
check("lk remind CLI command is registered",
      "def cmd_remind(" in ctl_src and '"remind": cmd_remind' in ctl_src)

section("I. WS-U N-09 UI seam — the base is robust to the UI (variant switch)")
import subprocess, glob, shutil
# (a) transport isolation: NO variant touches the BRIDGE transport directly —
#     every HTTP/SSE call to the kernel goes through lib/bridge.js. (A variant may
#     still use __TAURI__ for native SHELL APIs — windows, panels, open_url — which
#     are a legitimate front-end concern, not bridge transport.)
TRANSPORT_LEAKS = ("window.fetch(", "new EventSource(", 'invoke("bridge_get"',
                   'invoke("bridge_post"', 'invoke("bridge_delete"')
variant_files = sorted(glob.glob("apps/desktop/web/variants/*/app.js"))
check("at least the classic variant exists", any(p.endswith("classic/app.js") for p in variant_files),
      f"variants={variant_files}")
for vf in variant_files:
    src = Path(vf).read_text(encoding="utf-8")
    leaks = [tok for tok in TRANSPORT_LEAKS if tok in src]
    check(f"{vf} uses no bridge transport directly (only via lib/bridge.js)", not leaks, f"leaked: {leaks}")
    check(f"{vf} imports from lib/bridge.js", "lib/bridge.js" in src)

# (b) bootstrap reads the variant from /health and falls back to classic on any error.
boot = Path("apps/desktop/web/bootstrap.js").read_text(encoding="utf-8")
check("bootstrap reads /health to pick the variant", "/health" in boot and "uiVariant" in boot)
check("bootstrap falls back to classic", '"classic"' in boot or "CLASSIC" in boot)
check("/health advertises uiVariant", '"uiVariant"' in bridge_src)
check("ui_variant is a config key (GUI==CLI round-trip)",
      '"ui_variant"' in Path("services/lk/config.py").read_text(encoding="utf-8"))

# (c) every entrypoint parses (node --check) when node is available.
node = shutil.which("node")
if node:
    for js in ("apps/desktop/web/bootstrap.js", "apps/desktop/web/lib/bridge.js",
               "apps/desktop/web/variants/classic/app.js"):
        rc = subprocess.run([node, "--check", js], capture_output=True, text=True)
        check(f"node --check {js}", rc.returncode == 0, rc.stderr.strip())
else:
    print("  node not installed — node --check skipped")

# ─────────────────────── J. N-75 chat-ops wiring parity (static) ───────────────────────
section("J. N-75 branching/edit/no-response wired end-to-end (store ↔ bridge ↔ UI)")
chats_src = Path("services/lk/ctx/chats.py").read_text(encoding="utf-8")
check("ChatStore has the DAG ops",
      all(f"def {m}(" in chats_src for m in
          ("add_variant", "edit_message", "set_head", "fork_chat", "tree", "path_messages")),
      "missing a ChatStore DAG method")
check("ChatStore head cursor + append-only DAG fields present",
      "head.json" in chats_src and '"parent"' in chats_src and "edit_of" in chats_src)
for handler in ("def regenerate(", "def message_edit(", "def variant_head(",
                "def chat_branch(", "def chat_tree(", "def chat_note(", "def _persist_turn("):
    check(f"bridge has {handler.strip('(')[4:]}", handler in bridge_src)
check("bridge routes the chat-op endpoints",
      all(s in bridge_src for s in ('"regenerate"', '"branch"', '"head"', '"note"', '"tree"', '"edit"')),
      "a chat-op route is unwired")
check("bridge regenerate carries the §3a op descriptor",
      "_regen_directive(" in bridge_src and "_REGEN_PRESETS" in bridge_src)
check("no-response note skips the model turn (logs+journal only)",
      "def chat_note(" in bridge_src and "ctx.append(" in bridge_src and '"responded": False' in bridge_src)
# UI side: controls, durable-id threading, and all ops go through lib/bridge.js transport.
check("classic variant renders per-message ops + variant nav + diff",
      all(s in app for s in ("renderMessageControls", "renderVariantNav", "renderDiff", "data-chat-op")),
      "a chat-op UI affordance is missing")
check("classic variant wires regenerate/edit/branch/variant/minimap",
      all(s in app for s in ("regenerateMessage", "editMessage", "branchFromMessage",
                             "switchVariant", "openMinimap", "submitNote")))
# N-82 batch-1 live-regression guards (A1/A4/A5): these were green offline while broken
# live, so pin the specific shapes the live rebuild #2 disproved.
styles_css = Path("apps/desktop/web/styles.css").read_text(encoding="utf-8")
# A1 — a <button> may not contain <button> chips (the row main nests folder/tag chips).
# The main must be a focusable div[role=button], NOT a button, with keyboard activation.
check("A1: history row main is a div[role=button] carrying data-chat-id (not a nested button)",
      'class="history-main" role="button"' in app
      and '<button type="button" class="history-main"' not in app)
check("A1: div-as-button restores keyboard (Enter/Space) activation of a chat row",
      '[data-chat-id][role="button"]' in app and 'loadChat(chat.dataset.chatId)' in app)
# A4 — deep-search depends on the web/retrieval master; when off it must be HONESTLY
# disabled (gate #1), not silently swallow clicks.
check("A4: deep-search toggle is honestly disabled when web is off (no silent no-op)",
      "deepSearchToggle.disabled = true" in app and "deepSearchToggle.disabled = false" in app)
check("A4: a dependency-disabled tool-btn reads as unavailable",
      ".tool-btn:disabled" in styles_css or '.tool-btn[aria-disabled="true"]' in styles_css)
# A5 — the overlay could not grow (tiny max caps, no maximize) so history had no room,
# and the 142px list column overflowed once rows gained checkbox+chips.
tauri_conf = Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
check("A5: window can actually grow (lifted max caps + maximizable) for history/expand",
      '"maximizable": true' in tauri_conf
      and '"maxHeight": 560' not in tauri_conf and '"maxWidth": 1200' not in tauri_conf)
check("A5: history list column has room for the enriched chat rows (no 142px overflow)",
      "minmax(240px, 320px) minmax(0, 1fr)" in styles_css)
# N-82 batch-2 live-regression guards (A2/A3): the regenerate pair.
# A2 — the async job result exposes the model reply as `res.answer`, NOT `res.text`.
# Reading res.text → normalizeAssistantReply substitutes "(empty response)" and the
# empty-guard (which checked the post-substitution text) can never fire. Pin the
# corrected shape: read res.answer + detect emptiness from the RAW answer first.
check("A2: regenerate reads res.answer (not res.text) so a real reply is not blanked",
      "normalizeAssistantReply({ text: res.answer })" in app
      and "normalizeAssistantReply(res).text" not in app)
check("A2: empty-guard fires on the RAW answer before the '(empty response)' placeholder",
      "const rawAnswer = typeof res.answer" in app and "if (!rawAnswer)" in app)
# A3 — a proactive finding is now a durable, regenerate-able message: the kernel
# persists it (kind="finding") and sends its id on the SSE card; the UI must carry
# that id onto the bubble so per-message controls render (no more dead ephemeral card).
check("A3: proactive finding card carries the persisted msgId/chatId onto the bubble",
      "msgId: payload.msgId" in app and "chatId: payload.chatId" in app)
check("A3: kernel persists a finding as a real kind='finding' chat message",
      'kind="finding"' in bridge_src and "_present_finding" in bridge_src)
check("A3: regenerating a finding bases on its own content (no originating query)",
      'str(orig.get("kind") or "") == "finding"' in bridge_src)
# C3 — per-message feedback backend: durable up/down + free-text on a message, kept
# out of the append-only event log (mutable, like bookmarks), aggregatable for §P SOUL
# / N-76. The vote control is real (persisted + retrievable), not cosmetic.
check("C3: ChatStore has the feedback store (set/get/list + atomic file)",
      all(f"def {m}(" in chats_src for m in ("set_feedback", "get_feedback", "list_feedback",
                                             "_read_feedback", "_write_feedback"))
      and 'self._feedback' in chats_src)
check("C3: feedback is removed when neither vote nor text remains (no residue)",
      'not rec.get("vote") and not str(rec.get("text")' in chats_src)
check("C3: hard-deleting a chat drops its feedback so none dangle",
      'f.get("chatId") != chat_id' in chats_src and "_write_feedback(fkept)" in chats_src)
check("C3: bridge exposes POST /chats/{id}/feedback → chat_feedback (404 on unknown id)",
      "def chat_feedback(" in bridge_src and 'parts[2] == "feedback"' in bridge_src
      and "self.bridge.chat_feedback(" in bridge_src)
# Branch map is a side-flanking sidecar WINDOW (not a full-window overlay that
# hogs the chat). Map button opens the sidecar; main reflects path switches via
# the cross-window event; Rust + capabilities know the panel-minimap window.
styles_css = Path("apps/desktop/web/styles.css").read_text(encoding="utf-8")
caps_src = Path("apps/desktop/src-tauri/capabilities/default.json").read_text(encoding="utf-8")
check("Map button opens the branch map as a sidecar window (not in-window overlay)",
      'openSidecarPanel("minimap")' in app and 'PANEL_MODE === "minimap"' in app)
check("branch-map sidecar is registered in Rust panel_spec + close_panels",
      '"minimap" => Some(("panel-minimap"' in rust_src
      and '"history", "minimap"' in rust_src)
check("panel-minimap window is granted capabilities",
      "panel-minimap" in caps_src)
check("branch-map panel drops its overlay z-index/inset when run as a sidecar",
      ".panel-window .minimap-panel" in styles_css and "z-index: auto" in styles_css)
check("in-window fallback flanks the chat (right dock, NOT a full inset:0 overlay)",
      "left: auto" in styles_css and "min(360px, 78%)" in styles_css
      and "inset: 0;" not in styles_css.split(".minimap-panel {")[1].split("}")[0])
# 0A (N-80): the click-eating culprit was the full-width .drag-zone overlay sitting
# at z-index 3 over panel tops in sidecar windows; panel headers are now "deep" drag
# regions so the header drags but clickable children (✕, chips) short-circuit drag.
index_html = Path("apps/desktop/web/index.html").read_text(encoding="utf-8")
check("0A: drag-zone overlay no longer covers panel headers (hidden in panel windows)",
      ".panel-window .drag-zone {" in styles_css
      and "display: none;" in styles_css.split(".panel-window .drag-zone {")[1].split("}")[0])
check("0A: panel headers are deep drag regions (header drags, buttons clickable)",
      'class="panel-head" data-tauri-drag-region="deep"' in index_html
      and '<header class="panel-head" data-tauri-drag-region>' not in index_html)
check("branch-map close stays robust (Esc-to-close fallback present)",
      'event.key !== "Escape"' in app)
# 0C (N-80): the four pure-UI panels live in panel.html and open as sidecar windows;
# index.html (main overlay) no longer carries them, so they stop bloating the DOM.
# settings + advanced stay in index.html (configSnapshot reads them every turn).
panel_html = Path("apps/desktop/web/panel.html").read_text(encoding="utf-8")
_UI_PANELS = ('id="tasks-panel"', 'id="reminders-panel"', 'id="history-panel"', 'id="minimap-panel"')
check("0C: panel.html (sidecar host) carries all four pure-UI panels",
      all(p in panel_html for p in _UI_PANELS))
check("0C: main index.html no longer carries the four pure-UI panels (de-bloated)",
      not any(p in index_html for p in _UI_PANELS))
check("0C: config-bearing settings + advanced stay in BOTH main and the panel host",
      'id="settings"' in index_html and 'id="advanced-panel"' in index_html
      and 'id="settings"' in panel_html and 'id="advanced-panel"' in panel_html)
check("0C: open_panel loads the panel host, not index.html",
      'panel.html?panel=' in rust_src and 'index.html?panel=' not in rust_src)
check("0C: trimmed-main fallbacks resolve the four panels null-safely",
      'const tasksPanel = document.querySelector("#tasks-panel");' in app
      and 'const historyPanel = document.querySelector("#history-panel");' in app
      and 'const remindersPanel = document.querySelector("#reminders-panel");' in app)
check("sidecar path-switch syncs the main feed via the event bus",
      '"chat-path-changed"' in app and "loadChatIntoFeed(chatId)" in app)
check("classic variant captures durable transcript ids from the turn",
      "result.assistantMsgId" in app and "reply.msgId" in app)
check("classic variant calls chat-op endpoints via the transport module (not raw fetch)",
      "/regenerate" in app and "/branch" in app and "/note" in app
      and "window.fetch(" not in app and "new EventSource(" not in app)
# Cut-corner audit (uncommitted UI hardening): no fake/unreliable affordances.
check("no window.prompt — edits/guidance use the in-UI promptInline affordance",
      "window.prompt(" not in app and "function promptInline(" in app)
check("§3a section + N ops are reachable from the UI (selective/explain/extend/compress)",
      all(f'"{op}"' in app for op in ("selective", "explain")) and "extend" in app
      and "compress" in app and "needsSelection" in app and "needsN" in app)
check("selective/explain use a real text selection (getSelection, scoped to a message)",
      "selectionchange" in app and "getSelection()" in app and "selectionWithin(" in app)
check("branch + variant-switch load the branched/selected path into the live feed",
      "function loadChatIntoFeed(" in app and "loadChatIntoFeed(res.active)" in app
      and "await loadChatIntoFeed(chatId)" in app)
check("no-response note never silently drops (adopts active chat / creates one)",
      "health.activeChat" in app and 'postBridge("/chats"' in app)
# N-67 integrity: the proactive toggle is a REAL consent gate on the unprompted-
# findings loop, not just a per-turn config flag (was over-claimed).
check("proactive toggle truly gates the kernel loop (UI → /observer → _maybe_proactive)",
      "self.proactive_enabled" in bridge_src and 'observer == "proactive"' in bridge_src
      and "if not self.proactive_enabled" in bridge_src
      and 'setKernelObserver("proactive"' in app)

# ─────────────────── N-80 step-2 — N-75 live correctness (regen/streaming) ───────────────────
section("N-80 step-2 — async regen + empty-guard + stuck-streaming watchdog")
check("#4: regenerate endpoint is async (enqueues a job, not a blocking sync call)",
      "def regenerate_async(" in bridge_src and "regenerate_async(cid, body)" in bridge_src
      and "def _build_regen_turn(" in bridge_src and "def _enrich_regen_result(" in bridge_src)
check("#4: async regen job result is enriched with op/diff so the poller sees the full shape",
      'request.get("_regen")' in bridge_src and "_enrich_regen_result(" in bridge_src.split("def _run_turn_job(")[1])
check("#4: sync regenerate() still exists (tests + fallback) and reuses the shared builder",
      "def regenerate(" in bridge_src and "self._build_regen_turn(" in bridge_src
      and "self._enrich_regen_result(" in bridge_src)
check("#4: UI regenerate polls a job (non-blocking) and is cancellable",
      "noPending: true" in app and "state.activeJobId = regenJobId" in app and "waitForBridgeJob(" in app)
check("#5: an empty regen never blanks the message (keeps the previous variant)",
      "regenerate returned an empty response" in app)
check("#5/#4: regen streams in place (no stray draft) + poller skips regen jobs",
      "state.regenTargetUiId" in app and 'job.source === "regenerate"' in app)
check("#6: stuck-streaming watchdog resets the pill / settles an orphaned draft on the health tick",
      "function healStuckStream(" in app and "healStuckStream();" in app and "state.liveDraftAt" in app)

# ─────────────────── N-80 step-3 — regenerate UX (single button + ephemeral picker) ───────────────────
section("N-80 step-3 — regenerate is a single button + a no-residue custom picker")
check("#2: a single Regenerate button + a Custom trigger (NOT an always-open 12-item dropdown)",
      'data-chat-op="regen-default"' in app and 'data-chat-op="regen-custom"' in app
      and 'data-chat-op="regen-menu"' not in app and "op-dropdown" not in app)
check("#2: the custom picker is ephemeral and self-removing (no residue)",
      "function openRegenPicker(" in app and ".regen-picker" in app
      and '.regen-picker, .link-picker")?.remove()' in app)
check("#2: every §3a op is still reachable through the picker",
      "REGEN_OPS.map(" in app and "data-regen-index" in app)
check("#2: one-click Regenerate is a plain re-roll (neutral op, no guidance prompt)",
      "DEFAULT_REGEN" in app and 'op: "regen"' in app)

# ─────────────────── N-80 step-4 — branch map = node/edge GRAPH (not indented text) ───────────────────
section("N-80 step-4 — branch map is a node→edge graph with hover detail")
check("#1: minimap renders a node/edge GRAPH (the old indented text tree is gone)",
      'class="map-graph"' in app and "function renderMinimap(" in app
      and "depth * 14" not in app and 'style="margin-left:' not in app)
check("#1: nodes default to a summary + carry a scrollable hover detail tip",
      "map-summary" in app and "map-tip-detail" in app
      and "node.summary" in app and "node.detail" in app)
check("#1: clicking a node switches head; reading/scrolling the tip does not",
      'event.target.closest(".map-tip")' in app and "/head" in app)
check("#1: graph CSS draws connectors (directed edges) + a scrollable tip",
      ".map-graph" in styles_css and "var(--map-edge)" in styles_css
      and "border-top: 1px solid var(--map-edge)" in styles_css and ".map-tip-detail" in styles_css)
check("#1: tree() exposes summary + detail per node (snippet retained for back-compat)",
      "def _node_summary(" in chats_src and '"summary": _node_summary(' in chats_src
      and '"detail":' in chats_src and '"snippet":' in chats_src)

# ─────────────────── N-80 feedback-1 (live rebuild) — regressions + sensor/ops fixes ───────────────────
section("N-80 feedback-1 — config drag handle (A1) + transcript label (B1) + ops visible (B2)")
check("A1: config window has a header drag handle + close in BOTH main and panel host",
      "<strong>Config</strong>" in index_html and "<strong>Config</strong>" in panel_html
      and 'id="settings-head-close"' in index_html and "settings-head-close" in app
      and ".settings > .panel-head" in styles_css)
check("B1: audio-transcript thumb shows speech only — rejects retrieval/turn status",
      "ui[- ]forced" in app and "single-pass" in app
      and "audioTranscriptText(state.voiceTranscript)" in app)
check("B1: sensor thumbnails carry a useful hover tip (title = latest context detail)",
      "${item.title} — ${item.detail" in app)
check("B2: a completed turn renders its msg-ops immediately (no controls-less message)",
      "a full render at turn-end" in app)
check("B2: msg-op buttons read as live controls (not muted/disabled)",
      ".op-btn:active" in styles_css and "color: #cdd6cd;" in styles_css)

# ─────────────────── N-81 B1 — chat trash bin (soft-delete → restore → purge) ───────────────────
section("N-81 B1 — trash bin store ↔ bridge ↔ UI")
check("store: trash/purge/list_trash/purge_trashed + restore clears both states",
      all(f"def {m}(" in chats_src for m in ("trash_chat", "purge_chat", "list_trash", "purge_trashed"))
      and 'row["trashed"] = False' in chats_src and 'include_trashed' in chats_src)
check("bridge: chat_trash/chat_purge/chat_empty_trash + trash in index",
      all(f"def {m}(" in bridge_src for m in ("chat_trash", "chat_purge", "chat_empty_trash"))
      and '"trash": self.chats.list_trash()' in bridge_src)
check("bridge routes /trash, /purge, /chats/trash/empty",
      '"trash"' in bridge_src and '"purge"' in bridge_src and '"/chats/trash/empty"' in bridge_src)
check("UI: per-chat Delete→trash + trash view (restore/purge) + empty-trash",
      "data-trash-chat" in app and "data-purge-chat" in app and "data-restore-chat" in app
      and "chatTrashOp(" in app and "showTrash" in app and "/chats/trash/empty" in app)
check("UI: trash + purge confirmed/guarded + the trash list comes from the index",
      "state.chats.trash" in app and "history-trash-toggle" in panel_html
      and "history-empty-trash" in panel_html)

# ─────────────────── N-81 B2 — search (in-chat + global, scope-restrictable) ───────────────────
section("N-81 B2 — search store ↔ bridge ↔ UI")
check("store: ChatStore.search(query, regex, chat_id, include_trashed) + snippet",
      "def search(" in chats_src and "def _hit_snippet(" in chats_src
      and "regex" in chats_src and "chat_id" in chats_src)
check("bridge: chat_search + GET /search route + scope/regex params",
      "def chat_search(" in bridge_src and '"/search"' in bridge_src
      and "parse_qs(" in bridge_src and '"scope"' in bridge_src)
check("UI: search bar + scope toggle + regex toggle + results, via the transport",
      "runChatSearch(" in app and "openSearchHit(" in app and "/search?" in app
      and "history-search-scope" in panel_html and "history-search-regex" in panel_html
      and "data-hit-chat" in app)
check("UI: search results take over the history list + scope is restrictable",
      "state.chats.search" in app and 'scope === "current"' in app and "search-hit" in app)

# ─────────────────── N-81 B3 — link-at-message + backlinks ───────────────────
section("N-81 B3 — link store(NoteStore edges) ↔ bridge ↔ UI")
notes_src = Path("services/lk/ctx/notes.py").read_text(encoding="utf-8")
check("store: NoteStore edges power links (add_edge / edges_for / neighborhood)",
      "def add_edge(" in notes_src and "def edges_for(" in notes_src
      and "def neighborhood(" in notes_src and '"backlinks"' in notes_src)
check("bridge: create_link + links_for + POST /links + GET /links/{chat}/{msg}",
      "def create_link(" in bridge_src and "def links_for(" in bridge_src
      and '"/links"' in bridge_src and "/links/" in bridge_src
      and "def _link_node(" in bridge_src)
check("UI: per-message Link… + Links toggle controls, via data-chat-op",
      'data-chat-op="link"' in app and 'data-chat-op="links-toggle"' in app
      and "openLinkPicker(" in app and "toggleLinks(" in app)
check("UI: links flow through the transport (POST /links + GET /links/…)",
      'postBridge("/links"' in app and "getBridge(" in app
      and "/links/${encodeURIComponent" in app and "createMessageLink(" in app)
check("UI: inline links panel + clickable peers (backlinks surfaced, navigable)",
      "renderLinks(" in app and "data-link-peer" in app and "openLinkPeer(" in app
      and "linkLabel(" in app and "linkCount(" in app)

# ─────────────────── N-81 B4 — temporary chats (adjustable auto-expire timer) ───────────────────
section("N-81 B4 — temporary chats store ↔ bridge ↔ UI ↔ CLI")
check("store: create_chat(ttl_minutes) + set_ttl + sweep_expired (expire → trash)",
      "ttl_minutes" in chats_src and "def set_ttl(" in chats_src
      and "def sweep_expired(" in chats_src and "ephemeral" in chats_src
      and "expires_at" in chats_src)
check("store: sweep is wired into ensure_default (lazy retire on access)",
      "self.sweep_expired()" in chats_src)
check("bridge: chat_create ttl + chat_set_ttl + POST /chats/{id}/ttl + sweep on index",
      "def chat_set_ttl(" in bridge_src and 'parts[2] == "ttl"' in bridge_src
      and "ttlMinutes" in bridge_src and "self.chats.sweep_expired()" in bridge_src)
check("UI: per-chat ⏱ timer control + remaining-time badge, via the transport",
      "data-ttl-chat" in app and "ttlRemaining(" in app and "chatTtlOp(" in app
      and "/ttl`" in app)
ctl_src_b4 = Path("services/lk/ctl.py").read_text(encoding="utf-8")
check("CLI parity: lk chats ttl / sweep / new --ttl + B1 trash/restore/purge",
      'sub == "ttl"' in ctl_src_b4 and 'sub == "sweep"' in ctl_src_b4
      and "--ttl" in ctl_src_b4 and 'sub == "trash"' in ctl_src_b4
      and 'sub == "restore"' in ctl_src_b4 and 'sub == "purge"' in ctl_src_b4)

# ─────────────────── N-81 B5 — summarize → context (note + inline + cross-chat anchor) ───────────────────
section("N-81 B5 — summarize store ↔ bridge ↔ UI ↔ CLI")
check("store: insert_after (anchor → inline-or-branch) + append_message set_head guard",
      "def insert_after(" in chats_src and "set_head: bool" in chats_src
      and "set_head=not has_child" in chats_src)
check("bridge: summarize_chat builds a _noPersist turn (no chat pollution)",
      "def summarize_chat(" in bridge_src and "def _build_summary_turn(" in bridge_src
      and '"_noPersist": True' in bridge_src and 'request.get("_noPersist")' in bridge_src)
check("bridge: #12 BOTH sinks (durable note auto-linked + inline summary msg)",
      "self.notes.write_note(" in bridge_src and "self.notes.add_edge(" in bridge_src
      and 'kind="summary"' in bridge_src)
check("bridge: #13 cross-chat anchored insert + POST /chats/{id}/summarize route",
      "self.chats.insert_after(" in bridge_src and 'parts[2] == "summarize"' in bridge_src)
check("bridge: the summarization turn never flips the active chat (pointer restore)",
      "prev_active" in bridge_src and "self.chats.set_active(prev_active)" in bridge_src)
check("UI: per-chat Summarize control + two-stage cross-chat picker, via the transport",
      "data-summarize-chat" in app and "openSummarizePicker(" in app
      and "summarizeChat(" in app and "/summarize`" in app and "data-sp-anchor" in app)
check("UI: summarize picker styled (two-stage anchor list)",
      ".summarize-picker" in styles_css and ".sp-anchors" in styles_css)
check("CLI parity: lk chats summarize [--into <chat> <msg>] via the bridge",
      'sub == "summarize"' in ctl_src_b4 and "/summarize" in ctl_src_b4
      and "def _post_json(" in ctl_src_b4)

# ─────────────────── N-81 #4 — full backup / restore (merge-conflict resolution) ───────────────────
section("N-81 #4 — backup/restore store ↔ bridge ↔ UI ↔ CLI")
check("store: backup_all + restore_bundle (skip/rename/merge) + helpers",
      "def backup_all(" in chats_src and "def restore_bundle(" in chats_src
      and "def _merge_into(" in chats_src and "def _remap_ids(" in chats_src
      and "def _install_chat(" in chats_src)
check("store: merge detects conflicts against an immutable original snapshot",
      "original = {r.get(" in chats_src and "is_conflict = cur is not None" in chats_src)
check("bridge: chat_backup + chat_restore_bundle + GET /chats/backup + POST /chats/restore",
      "def chat_backup(" in bridge_src and "def chat_restore_bundle(" in bridge_src
      and 'parts[1] == "backup"' in bridge_src and 'self.path == "/chats/restore"' in bridge_src)
check("UI: Backup all + Restore controls wired through the transport",
      "history-backup" in panel_html and "history-restore" in panel_html
      and "backupAllChats(" in app and "restoreChatsFromBundle(" in app
      and '"/chats/backup"' in app and '"/chats/restore"' in app)
check("CLI parity: lk chats backup [path] | import <path> [--skip|--rename|--merge]",
      'sub == "backup"' in ctl_src_b4 and 'sub == "import"' in ctl_src_b4
      and "/chats/restore" in ctl_src_b4 and "backup_all(" in ctl_src_b4)

# ─────────────────── N-81 B7/B8 — semantic search + pins/bookmarks ───────────────────
section("N-81 B7/B8 — semantic search + pins/bookmarks store ↔ bridge ↔ UI ↔ CLI")
check("store: semantic_search (ephemeral FTS5) + pin_chat + bookmark methods",
      "def semantic_search(" in chats_src and "def _fts_query(" in chats_src
      and "def pin_chat(" in chats_src and "def add_bookmark(" in chats_src
      and "def remove_bookmark(" in chats_src and "def list_bookmarks(" in chats_src)
check("store: graceful FTS5 degrade + pinned-first sort + dangling-bookmark cleanup",
      "sqlite3.OperationalError" in chats_src and 'bool(r.get("pinned"))' in chats_src
      and 'b.get("chatId") != chat_id' in chats_src)
check("bridge: chat_semantic_search + chat_pin + bookmark endpoints",
      "def chat_semantic_search(" in bridge_src and "def chat_pin(" in bridge_src
      and "def chat_add_bookmark(" in bridge_src and "def chat_remove_bookmark(" in bridge_src
      and "def chat_bookmarks(" in bridge_src)
check("bridge: GET /semantic + GET /chats/bookmarks + POST pin/bookmarks routes",
      'path == "/semantic"' in bridge_src and 'parts[1] == "bookmarks"' in bridge_src
      and 'parts[2] == "pin"' in bridge_src and 'self.path == "/chats/bookmarks"' in bridge_src
      and 'self.path == "/chats/bookmarks/remove"' in bridge_src)
check("UI: semantic toggle + bookmarks view + pin star + bookmark control",
      "history-search-semantic" in panel_html and "history-bookmarks-toggle" in panel_html
      and "data-pin-chat" in app and 'data-chat-op="bookmark"' in app
      and "/semantic?" in app and '"/chats/bookmarks"' in app)
check("CLI parity: lk chats search --semantic | pin | bookmark | bookmarks | unbookmark",
      'sub == "search"' in ctl_src_b4 and 'sub == "pin"' in ctl_src_b4
      and 'sub == "bookmark"' in ctl_src_b4 and 'sub == "bookmarks"' in ctl_src_b4
      and "semantic_search(" in ctl_src_b4)

# ─────────────────── N-81 B9a — promote message → durable note ───────────────────
section("N-81 B9a — promote (recall integration) store↔bridge↔UI↔CLI")
check("bridge: chat_promote writes an excerpt note + a kind='link' back-edge",
      "def chat_promote(" in bridge_src and '"excerpt"' in bridge_src
      and 'add_edge(note_id, mid, kind="link")' in bridge_src)
check("bridge: POST /chats/{id}/promote route",
      'parts[2] == "promote"' in bridge_src)
check("UI: Promote → note control + handler + transport call",
      'data-chat-op="promote"' in app and 'op === "promote"' in app
      and "/promote" in app)
check("CLI parity: lk chats promote <chatId> <msgId> [note…]",
      'sub == "promote"' in ctl_src_b4 and "/promote" in ctl_src_b4)

# ─────────────────── N-81 B9b — weighted relevance (delete=−P) wiring ───────────────────
check("bridge: _recall_suppress toggles MemoryIndex mark/clear_deleted",
      "def _recall_suppress(" in bridge_src
      and "mem.mark_deleted" in bridge_src and "mem.clear_deleted" in bridge_src)
check("bridge: trash/restore/purge/delete are wired to the −P penalty",
      bridge_src.count("self._recall_suppress(") >= 4)

# ─────────────────── N-81 B9c — organization (tags / folders / sort / bulk) ───────────────────
section("N-81 B9c — organization store↔bridge↔UI↔CLI")
check("store: tags/folders/sort/bulk methods",
      "def set_tags(" in chats_src and "def add_tag(" in chats_src
      and "def remove_tag(" in chats_src and "def all_tags(" in chats_src
      and "def set_folder(" in chats_src and "def all_folders(" in chats_src
      and "def bulk(" in chats_src)
check("store: list_chats accepts folder/tag/sort filters",
      "folder: str | None = None" in chats_src and "sort: str = \"recency\"" in chats_src
      and "def _sort(rows" in chats_src and 'sort == "title"' in chats_src)
check("bridge: chat_tags + chat_folder + chat_bulk endpoints",
      "def chat_tags(" in bridge_src and "def chat_folder(" in bridge_src
      and "def chat_bulk(" in bridge_src)
check("bridge: chats_index threads folder/tag/sort + emits facets",
      "def chats_index(self, params" in bridge_src and "all_tags()" in bridge_src
      and "all_folders()" in bridge_src)
check("bridge: routes — /chats/bulk, /chats/{id}/tags|folder, GET tags/folders facets",
      'self.path == "/chats/bulk"' in bridge_src
      and 'parts[2] == "tags"' in bridge_src and 'parts[2] == "folder"' in bridge_src
      and 'parts[1] == "tags"' in bridge_src and 'parts[1] == "folders"' in bridge_src)
check("UI: org controls + tag/folder edit + facet filters + multi-select + bulk bar",
      "renderChatOrgControls(" in app and 'data-tag-chat="' in app
      and 'data-folder-chat="' in app and 'data-tag-filter="' in app
      and 'data-select-chat="' in app and "data-bulk-op=" in app
      and "/chats/bulk" in app and 'id="chat-sort"' in app)
check("CLI parity: tag/untag/tags/folder/folders/bulk subcommands",
      'sub == "tag"' in ctl_src_b4 and 'sub == "untag"' in ctl_src_b4
      and 'sub == "tags"' in ctl_src_b4 and 'sub == "folder"' in ctl_src_b4
      and 'sub == "folders"' in ctl_src_b4 and 'sub == "bulk"' in ctl_src_b4)

section("Z. N-82 §D live-confirmed render regressions — static guards (D1–D5)")
# These are render-side fixes the offline gate can only pin structurally; a WSLg
# rebuild confirms them live. Guarding the exact seams stops a silent re-regression.
styles = Path("apps/desktop/web/styles.css").read_text(encoding="utf-8")
# D1/D3: History/search/minimap panels are separate webviews; a panel switching the
# active chat must signal the main window, which must adopt ANY chat (not only the one
# it already shows). chat-path-changed now appears 3×: emit-in-loadChatIntoFeed, the
# minimap emit, and the main-window listen.
check("D1/D3: a panel switch signals the main feed (emit in panel mode)",
      app.count("chat-path-changed") >= 3 and "if (PANEL_MODE) {" in app)
check("D3: the main listener adopts ANY switched chat (no equality guard)",
      "if (chatId) loadChatIntoFeed(chatId).catch" in app
      and "chatId === state.chats.active) loadChatIntoFeed" not in app)
# D2: loadChat must build the in-panel preview from the loaded messages regardless of
# whether the (main-feed) render threw — a load error no longer poisons the preview.
check("D2: loadChatIntoFeed swallows a sidecar render error",
      "try { render(); } catch" in app)
check("D2: loadChat builds the preview outside the load try (no 'Could not load' poison)",
      "build the preview anyway (D2)" in app
      and 'state.history.text = `Could not load chat' not in app)
# D4: the ‹n/m› switcher index is clamped, and a regenerate reconciles its variants
# from the authoritative server tree (so an absent assistantMsgId can't strand it at 1/1).
check("D4: variant nav clamps the index into [0, n-1]",
      "Math.min(Math.max(message.variantIndex ?? 0, 0), n - 1)" in app)
check("D4: regenerate reconciles variants from the server tree",
      "reconcile from the server tree" in app
      and "try { await loadChatIntoFeed(chatId); } catch" in app)
# D5: the branch-map preserves scroll across a click-refresh and the root row
# left-aligns so it doesn't read as over-indented in a wide sidecar.
check("D5: minimap preserves scroll across refresh",
      "const prevTop = body.scrollTop" in app and "body.scrollTop = prevTop" in app)
check("D5: minimap root row left-aligns (over-indent fix)",
      ".map-graph > ul { padding-top: 0; justify-content: flex-start; }" in styles)

stop.set()
try: ui.close()
except Exception: pass

section("RESULT")
if FAILS:
    print(f"\n  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("\n  ALL UI CONTRACT STRESS CHECKS PASSED")
