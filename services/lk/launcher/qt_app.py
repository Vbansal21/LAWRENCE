"""The native Qt launcher window (PySide6).

This is the primary launcher surface when a display exists. It renders the shared
action registry (`lk.launcher.actions`) across a four-tier information architecture:
a front view (Tier 1/2), advanced tabs (Tier 3), and terminal-only flows (Tier 4).
Qt6 handles HiDPI scaling automatically, which fixes the font/scale problems of the
old tkinter launcher for free.

Import is lazy: nothing here is pulled onto the fast `lk` control path — only when
`lk launcher` actually opens the window (or a headless test builds it). Phases land
incrementally; tabs not yet built show a small placeholder.
"""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6 import QtCore, QtNetwork, QtWidgets

from . import actions, qt_tabs, qt_widgets as W

APP_TITLE = "LAWRENCE — launcher"
SINGLE_INSTANCE = "lawrence-launcher"   # QLocalServer name (one window per machine)

# Advanced tabs (Tier 3). The front view is the first, always-visible page.
TAB_SPECS: tuple[tuple[str, str], ...] = (
    ("home", "Home"),
    ("configure", "Configure"),
    ("sampling", "Sampling"),
    ("server", "Server"),
    ("memory", "Memory"),
    ("knowledge", "Knowledge"),
    ("diagnostics", "Diagnostics"),
    ("consoles", "Consoles"),
)

# Subsystem dots in the front-view header, in display order.
HEADER_DOTS: tuple[tuple[str, str], ...] = (
    ("kernel", "kernel"),
    ("bridge", "bridge"),
    ("model", "model"),
    ("sensors", "sensors"),
)

# Per-subsystem rows for the Detailed metrics view. Values are filled live (Q4);
# anything unpublished stays "n/a" — the launcher never fabricates a number.
DETAIL_ROWS: tuple[tuple[str, str], ...] = (
    ("model", "Model"),
    ("context", "Context (L1/L2/L3)"),
    ("preprocess", "Pre-processing"),
    ("web", "Web retrieval"),
    ("doc", "Doc retrieval"),
    ("log", "Log"),
    ("journal", "Journal"),
    ("mem", "Memory"),
    ("sensors", "Sensors"),
)

# Tier-1 front-view actions, left to right.
FRONT_ACTION_IDS: tuple[str, ...] = ("start", "ui", "stop", "restart", "quit")


def _default_snapshot() -> dict:
    """An honest empty snapshot: everything off / n/a until the poller fills it."""
    snap = {name: "off" for name, _ in HEADER_DOTS}
    snap["config"] = {"backend": "?", "routes": "—", "keys": "none"}
    snap["metrics_regular"] = "metrics unavailable — start the bridge"
    snap["metrics_detailed"] = {}
    snap["busy"] = ""
    return snap


class FrontView(QtWidgets.QWidget):
    """Tier-1/2 front view: status dots, primary actions, config chip, metrics.

    `apply_snapshot()` is the one entry point the live poller (Q4) calls; the view
    itself holds no truth and fabricates nothing.
    """

    action_requested = QtCore.Signal(str)   # action id → run through the gate
    tab_requested = QtCore.Signal(str)       # switch to an advanced tab

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dots: dict[str, W.StatusDot] = {}
        self._detail_values: dict[str, QtWidgets.QLabel] = {}
        self._flash_timer = QtCore.QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self._flash.setText(""))

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(self._build_header())
        self._flash = W.label("", kind="muted")
        root.addWidget(self._flash)
        root.addWidget(self._build_actions())
        root.addWidget(self._build_metrics(), 1)

        self.apply_snapshot(_default_snapshot())

    # ── construction ──────────────────────────────────────────────────────────
    def _build_header(self) -> QtWidgets.QWidget:
        outer = QtWidgets.QVBoxLayout()
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        top = QtWidgets.QHBoxLayout()
        title = W.label("LAWRENCE", kind="head")
        sub = W.label("launcher · gateway", kind="soft")
        top.addWidget(title)
        top.addWidget(sub)
        top.addStretch(1)
        self._config_chip = QtWidgets.QPushButton("backend ? · —")
        self._config_chip.setToolTip("Open Configure")
        self._config_chip.clicked.connect(lambda: self.tab_requested.emit("configure"))
        top.addWidget(self._config_chip)
        outer.addLayout(top)

        dots = QtWidgets.QHBoxLayout()
        dots.setSpacing(16)
        for key, text in HEADER_DOTS:
            cell = QtWidgets.QHBoxLayout()
            cell.setSpacing(6)
            dot = W.StatusDot("off")
            self._dots[key] = dot
            cell.addWidget(dot)
            cell.addWidget(W.label(text, kind="muted"))
            wrap = QtWidgets.QWidget()
            wrap.setLayout(cell)
            dots.addWidget(wrap)
        dots.addStretch(1)
        outer.addLayout(dots)
        return W.card(layout=outer)

    def _build_actions(self) -> QtWidgets.QWidget:
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for aid in FRONT_ACTION_IDS:
            a = actions.get(aid)
            if a is None:
                continue
            children = actions.dropdown_children(aid)
            btn = W.ActionButton(a, children, self.action_requested.emit)
            row.addWidget(btn)
        row.addStretch(1)
        console_btn = QtWidgets.QPushButton("Open console ▸")
        console_btn.setToolTip("Live server / bridge / REPL consoles")
        console_btn.clicked.connect(lambda: self.tab_requested.emit("consoles"))
        row.addWidget(console_btn)
        wrap = QtWidgets.QWidget()
        wrap.setLayout(row)
        return wrap

    def _build_metrics(self) -> QtWidgets.QWidget:
        outer = QtWidgets.QVBoxLayout()
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        head = QtWidgets.QHBoxLayout()
        head.addWidget(W.label("Metrics", kind="head"))
        head.addStretch(1)
        self._btn_regular = QtWidgets.QPushButton("Regular")
        self._btn_detailed = QtWidgets.QPushButton("Detailed")
        for b in (self._btn_regular, self._btn_detailed):
            b.setCheckable(True)
        self._btn_regular.setChecked(True)
        grp = QtWidgets.QButtonGroup(self)
        grp.setExclusive(True)
        grp.addButton(self._btn_regular)
        grp.addButton(self._btn_detailed)
        self._btn_regular.clicked.connect(lambda: self._metrics_stack.setCurrentIndex(0))
        self._btn_detailed.clicked.connect(lambda: self._metrics_stack.setCurrentIndex(1))
        head.addWidget(self._btn_regular)
        head.addWidget(self._btn_detailed)
        outer.addLayout(head)
        outer.addWidget(W.hline())

        self._metrics_stack = QtWidgets.QStackedWidget()
        # 0: regular summary
        reg = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(reg)
        rl.setContentsMargins(0, 6, 0, 0)
        self._regular_label = W.label("", kind="muted")
        self._regular_label.setWordWrap(True)
        rl.addWidget(self._regular_label)
        rl.addStretch(1)
        self._metrics_stack.addWidget(reg)
        # 1: detailed per-subsystem grid
        det = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(det)
        grid.setContentsMargins(0, 6, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(7)
        for i, (key, text) in enumerate(DETAIL_ROWS):
            grid.addWidget(W.label(text, kind="muted"), i, 0)
            val = W.label("n/a", kind="soft")
            self._detail_values[key] = val
            grid.addWidget(val, i, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(len(DETAIL_ROWS), 1)
        self._metrics_stack.addWidget(det)
        outer.addWidget(self._metrics_stack, 1)
        return W.card(layout=outer)

    # ── live update ─────────────────────────────────────────────────────────────
    def apply_snapshot(self, snap: dict) -> None:
        for key, _ in HEADER_DOTS:
            self._dots[key].set_state(str(snap.get(key, "off")))
        cfg = snap.get("config") or {}
        self._config_chip.setText(f"backend {cfg.get('backend', '?')} · {cfg.get('routes', '—')}")
        self._regular_label.setText(str(snap.get("metrics_regular", "")))
        detailed = snap.get("metrics_detailed") or {}
        for key, val in self._detail_values.items():
            raw = detailed.get(key)
            val.setText("n/a" if raw in (None, "") else str(raw))
        busy = str(snap.get("busy") or "")
        if busy:
            self.flash(f"⚠ {busy}")

    def flash(self, message: str, ms: int = 4000) -> None:
        """Show a transient info/conflict message under the header."""
        self._flash.setText(message)
        if message:
            self._flash_timer.start(ms)


class _PollSignals(QtCore.QObject):
    ready = QtCore.Signal(dict)


class _PollTask(QtCore.QRunnable):
    """One off-thread probe of live state → emits a front-view snapshot."""

    def __init__(self, signals: "_PollSignals"):
        super().__init__()
        self._signals = signals

    def run(self) -> None:  # runs on a QThreadPool worker, never the GUI thread
        try:
            from . import metrics
            snap = metrics.collect()
        except Exception:
            snap = None
        if snap is not None:
            self._signals.ready.emit(snap)


class MetricsPoller(QtCore.QObject):
    """Polls live state on a timer, off the GUI thread, emitting snapshots.

    A single in-flight probe at a time (a slow bridge never stacks up polls); the
    HTTP work happens on a worker so the window stays responsive.
    """
    snapshot = QtCore.Signal(dict)

    def __init__(self, interval_ms: int = 2000, parent=None):
        super().__init__(parent)
        self._pool = QtCore.QThreadPool.globalInstance()
        self._signals = _PollSignals()
        self._signals.ready.connect(self._on_ready)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)
        self._busy = False

    def start(self) -> None:
        self._tick()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._pool.start(_PollTask(self._signals))

    def _on_ready(self, snap: dict) -> None:
        self._busy = False
        self.snapshot.emit(snap)


class LauncherWindow(QtWidgets.QMainWindow):
    """The launcher shell: a tabbed window over the action registry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(720, 520)
        self.resize(880, 600)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)   # kill the style's light tab-bar base line
        self.tabs.setMovable(False)
        self.setCentralWidget(self.tabs)

        self.front = FrontView()
        self.front.action_requested.connect(self._run_action)
        self.front.tab_requested.connect(self._show_tab)

        self.tab_ctx = qt_tabs.TabContext(
            run_in_console=self._run_in_console,
            show_tab=self._show_tab,
            flash=self.front.flash,
        )
        self.pages: dict[str, QtWidgets.QWidget] = {}
        for key, title in TAB_SPECS:
            page = self.front if key == "home" else self._build_page(key, title)
            self.pages[key] = page
            self.tabs.addTab(page, title)

        self.poller: MetricsPoller | None = None
        self._ipc: QtNetwork.QLocalServer | None = None

    def install_single_instance(self, name: str = SINGLE_INSTANCE) -> None:
        """Listen for a 'raise' ping from a second launch so it focuses this window."""
        server = QtNetwork.QLocalServer(self)
        if not server.listen(name):
            if server.serverError() == QtNetwork.QAbstractSocket.AddressInUseError:
                QtNetwork.QLocalServer.removeServer(name)   # stale socket → reclaim
                server.listen(name)
        server.newConnection.connect(self._on_raise_request)
        self._ipc = server

    def _on_raise_request(self) -> None:
        conn = self._ipc.nextPendingConnection() if self._ipc else None
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if conn is not None:
            conn.disconnectFromServer()

    def _build_page(self, key: str, title: str) -> QtWidgets.QWidget:
        """Build an advanced tab from the shared registry/data."""
        ctx = self.tab_ctx
        if key == "consoles":
            return self._build_consoles(ctx)
        builders = {
            "configure": lambda: qt_tabs.ConfigureTab(ctx),
            "sampling": lambda: qt_tabs.SamplingTab(ctx),
            "server": lambda: qt_tabs.build_server(ctx),
            "memory": lambda: qt_tabs.build_memory(ctx),
            "knowledge": lambda: qt_tabs.KnowledgeTab(ctx),
            "diagnostics": lambda: qt_tabs.build_diagnostics(ctx),
        }
        builder = builders.get(key)
        return builder() if builder else W.placeholder(f"{title} — coming in a later phase")

    def _build_consoles(self, ctx) -> QtWidgets.QWidget:
        from .. import ctl, config
        from .console import FRONT, REPO_ROOT
        runtime = REPO_ROOT / ".runtime"
        return qt_tabs.ConsolesTab(
            ctx, front_path=str(FRONT),
            server_log=str(ctl.SERVER_LOG),
            bridge_log=str(runtime / "desktop" / "bridge.log"),
            popup_log=str(runtime / "desktop" / "app.log"),
            embed_log=str(runtime / "lk-embed-server.log"),
            config_path=str(config.CONFIG_PATH),
        )

    def _show_tab(self, key: str) -> None:
        page = self.pages.get(key)
        if page is not None:
            self.tabs.setCurrentWidget(page)

    # ── action execution (shared gate → detached front-door) ────────────────────
    def _run_action(self, action_id: str) -> None:
        if action_id == "quit":
            QtWidgets.QApplication.quit()
            return
        if action_id == "quit_all":
            self._quit_all()
            return
        a = actions.get(action_id)
        if a is None or not a.argv:
            return  # other handler-only actions live in tabs/terminal, not the front view
        # Route through the console seam so the command's output is always visible
        # (front-view Start/Stop used to run with output sent to /dev/null).
        self._run_in_console(a.argv, "lk " + " ".join(a.argv))

    def _quit_all(self) -> None:
        """N-28 Quit-all: terminate every LAWRENCE process, then close this window."""
        resp = QtWidgets.QMessageBox.question(
            self, "Quit all — full stop",
            "Terminate EVERY LAWRENCE process — bridge, model server, popup, "
            "sensors and REPL — and close this launcher?\n\n"
            "Services will stop (this is the deliberate full stop).",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No)
        if resp != QtWidgets.QMessageBox.StandardButton.Yes:
            self.front.flash("quit all — cancelled")
            return
        from .. import ctl
        self.front.flash("quit all — stopping every LAWRENCE process…")
        try:
            survivors = ctl.quit_all()
        except Exception as exc:  # pragma: no cover - surfaced to the user
            QtWidgets.QMessageBox.critical(self, "Quit all failed", str(exc))
            return
        if survivors:
            QtWidgets.QMessageBox.warning(
                self, "Quit all — survivors",
                "Some processes resisted termination:\n\n" + ctl.format_processes(survivors))
        QtWidgets.QApplication.quit()

    def _spawn_front(self, argv: tuple[str, ...]) -> None:
        """Run an `lk` front-door command detached, so the event loop never blocks."""
        from .console import FRONT, REPO_ROOT
        try:
            subprocess.Popen(
                [sys.executable, str(FRONT), *argv], cwd=str(REPO_ROOT),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
        except Exception as exc:  # pragma: no cover - surfaced to the user
            self.front.flash(f"failed to launch: {exc}")

    def _run_in_console(self, argv: tuple[str, ...], title: str = "") -> None:
        """Run an `lk` command whose output belongs in a console.

        Preferred path streams the command into the embedded Output console; if no
        PTY is available it falls back to a detached run so the action still works.
        """
        ok, _kind, reason = actions.claim(list(argv))
        if not ok:
            self.front.flash(reason or "blocked")
            return
        consoles = self.pages.get("consoles")
        if isinstance(consoles, qt_tabs.ConsolesTab) and consoles.open_command(argv, title):
            self.front.flash(f"running: lk {' '.join(argv)}")
            self._show_tab("consoles")
            return
        self._spawn_front(argv)
        self.front.flash(f"running: lk {' '.join(argv)} — see Consoles")
        self._show_tab("consoles")

    # ── live polling ────────────────────────────────────────────────────────────
    def start_polling(self, interval_ms: int = 2000) -> None:
        if self.poller is None:
            self.poller = MetricsPoller(interval_ms, self)
            self.poller.snapshot.connect(self.front.apply_snapshot)
        self.poller.start()

    def stop_polling(self) -> None:
        if self.poller is not None:
            self.poller.stop()

    def closeEvent(self, evt) -> None:  # noqa: N802 (Qt override)
        self.stop_polling()
        super().closeEvent(evt)


def _select_qt_platform() -> None:
    """Pick a Qt platform plugin that actually shows a window here.

    Under WSLg both ``WAYLAND_DISPLAY`` and ``DISPLAY`` are set, so Qt auto-selects
    the ``wayland`` QPA plugin — but PySide6 ships no working wayland platform
    plugin (only the -egl/-generic shells), so the window silently never appears
    (``Could not find the Qt platform plugin "wayland"``). ``xcb`` works via WSLg's
    Xwayland. So whenever an X display exists we prefer ``xcb``; only fall back to
    wayland when there is no X server at all. An explicit ``QT_QPA_PLATFORM`` (incl.
    the ``offscreen`` used by headless tests) is always honoured.
    """
    if os.environ.get("QT_QPA_PLATFORM"):
        return
    if os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    elif os.environ.get("WAYLAND_DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "wayland"


def _ensure_app() -> QtWidgets.QApplication:
    """Return the running QApplication, creating + theming one if needed.

    HiDPI rounding must be configured before the QApplication is constructed; Qt6
    keeps high-DPI scaling always-on, so this is all the scaling setup we need.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        _select_qt_platform()         # before QApplication reads QT_QPA_PLATFORM
        QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
            QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QtWidgets.QApplication(sys.argv[:1])
        W.apply_theme(app)
    return app


def build_window() -> tuple[QtWidgets.QApplication, LauncherWindow]:
    """Construct (but do not exec) the app + window — used by headless tests too."""
    app = _ensure_app()
    win = LauncherWindow()
    return app, win


def _raise_existing(name: str = SINGLE_INSTANCE) -> bool:
    """If a launcher is already running, ping it to focus and report True."""
    sock = QtNetwork.QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(200):
        sock.write(b"raise")
        sock.flush()
        sock.waitForBytesWritten(200)
        sock.disconnectFromServer()
        return True
    return False


def run_gui() -> int:
    """Open the launcher window and run the Qt event loop.

    One window per machine: a second `lk launcher` raises the existing window and
    exits instead of opening a duplicate (replacing the old four-launcher sprawl).
    """
    _ensure_app()
    if _raise_existing():
        print("  launcher already open — raised it.")
        return 0
    app, win = build_window()
    win.install_single_instance()
    win.show()
    win.raise_()
    win.activateWindow()
    win.start_polling()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_gui())
