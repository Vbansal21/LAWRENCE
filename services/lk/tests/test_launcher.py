"""Launcher registry + GUI + the /metrics contract (T3 + T4).

Pure checks (no Qt) always run: action-registry integrity, GUI↔console parity
through the ONE registry, the lifted-gate re-exports, and the honest
/metrics → front-view snapshot mapping. Qt + pyte checks run under the offscreen
platform when PySide6/pyte are installed, and are SKIPPED (not failed) otherwise,
so the gate stays green on headless CI without the [gui] extra. Config is pointed
at a temp path so building the window never touches the user's real lk.json.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "services")

FAILS = []
def check(name, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  :: {extra}" if (extra and not cond) else ""))
    if not cond:
        FAILS.append(name)
def section(t): print(f"\n=== {t} ===")

from lk import ctl
from lk.launcher import actions, console, metrics


section("A. action registry integrity (single source for both surfaces)")
ids = [a.id for a in actions.REGISTRY]
check("unique action ids", len(ids) == len(set(ids)), ids)
check("every action is argv XOR handler",
      all(bool(a.argv) != bool(a.handler) for a in actions.REGISTRY),
      [a.id for a in actions.REGISTRY if bool(a.argv) == bool(a.handler)])
check("tiers are within 1..4", all(1 <= a.tier <= 4 for a in actions.REGISTRY))
check("tier-1 front actions present",
      {a.id for a in actions.by_tier(1)} >= {"start", "ui", "stop", "restart"})
check("dropdown children resolve to real parents",
      all(actions.get(a.parent) is not None for a in actions.REGISTRY if a.parent))


section("B. ctl re-exports resolve to the registry (gate lifted, not duplicated)")
check("kind re-export", ctl.launcher_action_kind is actions.action_kind)
check("is_inspect re-export", ctl.launcher_action_is_inspect is actions.is_inspect)
check("can_preempt re-export", ctl.launcher_action_can_preempt is actions.can_preempt)
check("claim re-export", ctl.claim_launcher_action is actions.claim)
check("classification parity",
      actions.action_kind(["stop", "--all"]) == "stop-all"
      and actions.action_kind(["doctor"]) == "inspect"
      and actions.action_kind(["start"]) == "start")
check("inspect actions pass the gate purely (no lock/probe)",
      actions.claim(["status"]) == (True, "inspect", ""))


section("C. console renders from the registry (GUI ≡ console parity)")
for key, aid in console._CONSOLE_KEYS:
    check(f"console row {key}→{aid} resolves to an action", actions.get(aid) is not None)
console_handlers = {actions.get(aid).handler for _, aid in console._CONSOLE_KEYS
                    if actions.get(aid).handler}
check("every console handler is wired in the console",
      console_handlers <= set(console._HANDLERS),
      console_handlers - set(console._HANDLERS))


section("D. /metrics contract (T3): bridge route + honest snapshot mapping")
bridge_src = Path("apps/desktop/scripts/ui_bridge.py").read_text(encoding="utf-8")
check("bridge exposes a metrics() aggregator", "def metrics(self)" in bridge_src)
check("bridge routes GET /metrics",
      'path == "/metrics"' in bridge_src and "self.bridge.metrics()" in bridge_src)
for sub in ("model", "context", "preprocess", "web", "doc", "log", "journal", "mem", "sensors"):
    check(f"/metrics declares subsystem '{sub}'", f'"{sub}"' in bridge_src)
integ = Path("apps/desktop/INTEGRATION.md").read_text(encoding="utf-8")
check("INTEGRATION.md documents /metrics", "GET /metrics" in integ and "subsystems" in integ)

mx = {"subsystems": {
    "model": {"backend": "local", "modalities": "text"},
    "context": {"used": 10, "limit": 99, "l1": 2, "l2": 0, "l3": 0},
    "preprocess": {"pendingImages": 1, "pendingAudio": 0},
    "web": {"providers": {"a": {}}},
    "doc": None, "log": None, "journal": None, "mem": None,
    "sensors": {"vision": True, "audio": False}}}
health = {"modelHealth": True, "backend": "local",
          "observers": {"vision": True}, "jobs": {"queued": 0, "running": 1}}
snap = metrics.build_snapshot(health=health, metrics=mx,
                              lock_owner={"role": "bridge"}, config_summary={"backend": "local", "routing": {}})
d = snap["metrics_detailed"]
check("live subsystems mapped honestly",
      d.get("model") == "local · text" and d.get("context") == "L1 2 · L2 0 · L3 0", d)
check("null subsystems stay n/a (absent, never fabricated)",
      not any(k in d for k in ("doc", "log", "journal", "mem")), d)
check("kernel/bridge/model dots reflect live state",
      snap["kernel"] == "active" and snap["bridge"] == "active" and snap["model"] == "active")
off = metrics.build_snapshot(health=None, metrics=None, lock_owner=None, config_summary={})
check("offline → all off + no detailed rows",
      off["bridge"] == "off" and off["metrics_detailed"] == {})
desktopctl = Path("apps/desktop/scripts/desktopctl.sh").read_text(encoding="utf-8")
check("desktop children close the lifecycle lock descriptor",
      desktopctl.count("9>&- &") == 2)


section("E. Qt window + consoles offscreen [gated on PySide6/pyte]")
try:
    from lk import config
    config.CONFIG_PATH = Path(tempfile.mkdtemp()) / "lk.json"   # isolate from real config
    from lk.launcher import qt_app, qt_terminal
    from PySide6 import QtCore
    HAVE_QT = True
except Exception as exc:
    HAVE_QT = False
    print(f"  SKIP Qt checks — PySide6 unavailable ({exc.__class__.__name__}: {exc})")

if HAVE_QT:
    app, win = qt_app.build_window()
    titles = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    check("window builds every tab offscreen",
          titles == ["Home", "Configure", "Sampling", "Server",
                     "Memory", "Knowledge", "Diagnostics", "Consoles"], titles)
    check("home page is the live front view", win.pages["home"] is win.front)
    win.front.apply_snapshot(snap)
    check("front view reflects an applied snapshot",
          win.front._dots["model"].state() == "active"
          and win.front._detail_values["model"].text() == "local · text")
    check("keymap Ctrl-A → 0x01", qt_terminal.keymap(QtCore.Qt.Key_A, True, "") == b"\x01")
    check("keymap arrow-left → CSI D", qt_terminal.keymap(QtCore.Qt.Key_Left, False, "") == b"\x1b[D")
    win.install_single_instance("launcher-test-suite")
    app.processEvents()
    check("single-instance raise pings the running window",
          qt_app._raise_existing("launcher-test-suite") is True)
    if qt_terminal.pty_available():
        import pyte
        sc = pyte.Screen(10, 2); st = pyte.ByteStream(sc); st.feed(b"OK\r\nGO")
        check("pyte byte-stream renders to the screen grid",
              sc.display[0].startswith("OK") and sc.display[1].startswith("GO"), sc.display)
    else:
        print("  SKIP pyte unit — pyte/ptyprocess unavailable")


section("F. chat VCS viewer (N-75) — read-only variant/edit history + diffs (no Qt)")
from lk.launcher import chat_vcs
from lk.ctx.chats import ChatStore
_tmp = Path(tempfile.mkdtemp())
_cs = ChatStore(mem_dir=_tmp)
_cid = _cs.create_chat("vcs demo")["id"]
_q = _cs.append_message(_cid, "user", "explain merge sort")
_r = _cs.append_message(_cid, "assistant", "Merge sort splits then merges.")
_r2 = _cs.add_variant(_cid, _r, "assistant", "Merge sort is a divide-and-conquer sort.")
_cs.edit_message(_cid, _r2, "Merge sort is a stable divide-and-conquer sort.")
hist = chat_vcs.chat_history(_cid, store=_cs)
check("history lists every variant + edit node", len(hist["items"]) >= 4, f"items={len(hist['items'])}")
check("history flags the active path", any(it["on_path"] for it in hist["items"]))
check("history surfaces a stored diff for the edit", any(it["diff"] for it in hist["items"]))
text = chat_vcs.format_history(_cid, store=_cs)
check("formatted view marks on/off-path variants", "●" in text and "○" in text)
check("formatted view shows the edit diff inline", "@@" in text and "edit of" in text)
check("provider is read-only (no mutation of the log)",
      len(_cs.messages(_cid)) == len(hist["items"]))
import shutil as _sh; _sh.rmtree(_tmp, ignore_errors=True)


print()
if FAILS:
    print(f"  {len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("  ALL LAUNCHER CHECKS PASSED")
