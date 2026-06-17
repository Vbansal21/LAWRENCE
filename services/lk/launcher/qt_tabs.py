"""Advanced (Tier-3) tab content for the launcher window.

Each tab renders truthful, cheap-to-read state (config, capabilities, the durable
schedule) with NO kernel dependency, and exposes its registry actions. Actions
that produce console output are handed to `ctx.run_in_console(...)`; in this phase
that runs the `lk` front-door through the shared gate and points the user at the
Consoles tab — Q5 upgrades the same seam to stream into the embedded PTY console.

Kept separate from `qt_app.py` (the window orchestrator) so each surface stays
readable. Import is lazy — only reached when the Qt window builds.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Callable

from PySide6 import QtCore, QtWidgets

from . import qt_terminal, qt_widgets as W
from .. import capabilities, config


@dataclass
class TabContext:
    """Callbacks the window hands to each tab (no tab owns global state)."""
    run_in_console: Callable[[tuple[str, ...], str], None]
    show_tab: Callable[[str], None]
    flash: Callable[[str], None]


# ── small helpers ─────────────────────────────────────────────────────────────

def _scroll(inner: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.NoFrame)
    area.setWidget(inner)
    return area


def _column(margins=(16, 16, 16, 16), spacing=12) -> tuple[QtWidgets.QWidget, QtWidgets.QVBoxLayout]:
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return w, lay


_MARKER_COLORS = {
    "active": ("#76d083", "active"),
    "inactive": ("#d6ad55", "inactive"),
    "unavailable": ("#78857c", "unavailable"),
}


def _marker(state: str) -> QtWidgets.QLabel:
    color, text = _MARKER_COLORS.get(state, _MARKER_COLORS["unavailable"])
    lab = QtWidgets.QLabel(text)
    lab.setStyleSheet(
        f"color:{color}; border:1px solid {color}; border-radius:6px;"
        f"padding:1px 7px; font-size:11px;"
    )
    return lab


def _action_buttons(ctx: TabContext, rows: list[tuple[str, tuple[str, ...]]]) -> QtWidgets.QWidget:
    """A wrap of buttons; each runs an `lk` argv in the console seam."""
    box = QtWidgets.QWidget()
    flow = QtWidgets.QHBoxLayout(box)
    flow.setContentsMargins(0, 0, 0, 0)
    flow.setSpacing(8)
    for label, argv in rows:
        btn = QtWidgets.QPushButton(label)
        btn.clicked.connect(lambda _=False, a=argv, t=label: ctx.run_in_console(a, t))
        flow.addWidget(btn)
    flow.addStretch(1)
    return box


# ── Configure ─────────────────────────────────────────────────────────────────

class ConfigureTab(QtWidgets.QWidget):
    """Backend, the 12-role routing matrix, secret-key names, and setup actions."""

    def __init__(self, ctx: TabContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.role_combos: dict[str, QtWidgets.QComboBox] = {}
        inner, col = _column()

        # backend row
        col.addWidget(W.label("Backend", kind="head"))
        brow = QtWidgets.QHBoxLayout()
        self.backend_combo = QtWidgets.QComboBox()
        self.backend_combo.addItems(list(config.PROVIDERS))
        brow.addWidget(self.backend_combo)
        apply_backend = QtWidgets.QPushButton("Apply backend")
        apply_backend.clicked.connect(self._apply_backend)
        brow.addWidget(apply_backend)
        brow.addStretch(1)
        col.addLayout(brow)

        # presets
        col.addWidget(W.hline())
        col.addWidget(W.label("Presets — backend + routing in one pick", kind="head"))
        prow = QtWidgets.QHBoxLayout()
        for name, spec in config.PRESETS.items():
            b = QtWidgets.QPushButton(name)
            b.setToolTip(spec.get("label", ""))
            b.clicked.connect(lambda _=False, n=name: self._apply_preset(n))
            prow.addWidget(b)
        prow.addStretch(1)
        col.addLayout(prow)

        # routing matrix (12 roles)
        col.addWidget(W.hline())
        col.addWidget(W.label("Routing — per-role backend", kind="head"))
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)
        options = ["(default)"] + list(config.PROVIDERS)
        for i, role in enumerate(config.ALL_ROLES):
            grid.addWidget(W.label(role, kind="muted"), i // 2, (i % 2) * 2)
            combo = QtWidgets.QComboBox()
            combo.addItems(options)
            self.role_combos[role] = combo
            grid.addWidget(combo, i // 2, (i % 2) * 2 + 1)
        col.addLayout(grid)
        apply_routing = QtWidgets.QPushButton("Apply routing")
        apply_routing.clicked.connect(self._apply_routing)
        col.addWidget(apply_routing, 0, QtCore.Qt.AlignLeft)

        # keys (names only — never values)
        col.addWidget(W.hline())
        col.addWidget(W.label("API keys — names only", kind="head"))
        self.keys_label = W.label("", kind="muted")
        self.keys_label.setWordWrap(True)
        col.addWidget(self.keys_label)
        actions_row = _action_buttons(self.ctx, [
            ("Add / manage keys (console)", ("secrets", "list")),
            ("Setup wizard", ("wizard",)),
            ("Doctor", ("doctor",)),
        ])
        col.addWidget(actions_row)
        col.addStretch(1)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(_scroll(inner))
        self._reload()

    def _reload(self) -> None:
        summary = config.configured_summary()
        backend = summary.get("backend", "local")
        idx = self.backend_combo.findText(backend)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        routing = summary.get("routing", {}) or {}
        for role, combo in self.role_combos.items():
            target = routing.get(role, "(default)")
            j = combo.findText(target)
            combo.setCurrentIndex(j if j >= 0 else 0)
        keys = summary.get("secrets", []) or []
        self.keys_label.setText("stored: " + (", ".join(keys) if keys else "none"))

    def _apply_backend(self) -> None:
        cfg = config.load()
        cfg["backend"] = self.backend_combo.currentText()
        config.save(cfg)
        self.ctx.flash(f"backend set to {cfg['backend']} — takes effect on next Start")

    def _apply_preset(self, name: str) -> None:
        cfg, missing = config.apply_preset(name)
        self._reload()
        msg = f"applied preset '{name}'"
        if missing:
            msg += f" — needs an API key for: {', '.join(missing)}"
        self.ctx.flash(msg)

    def _apply_routing(self) -> None:
        cfg = config.load()
        routing = {}
        for role, combo in self.role_combos.items():
            val = combo.currentText()
            if val and val != "(default)":
                routing[role] = val
        cfg["routing"] = routing
        config.save(cfg)
        self.ctx.flash(f"routing saved — {len(routing)} role(s) overridden")


# ── Sampling / Decoding (§4 capability markers) ───────────────────────────────

class SamplingTab(QtWidgets.QWidget):
    """Every sampler family marked active / inactive / unavailable for the
    configured backend, from the WS-K capability registry (one source of truth)."""

    def __init__(self, ctx: TabContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self._scroll_host = QtWidgets.QWidget()
        self.layout().addWidget(_scroll(self._scroll_host))
        self._render()

    def _backend_identity(self) -> tuple[str, str, str | None]:
        backend = config.configured_summary().get("backend", "local")
        prov = config.PROVIDERS.get(backend, {})
        kind = prov.get("kind", "local" if backend == "local" else "api")
        return kind, backend, prov.get("model")

    def _render(self) -> None:
        # clear any prior layout
        old = self._scroll_host.layout()
        if old is not None:
            QtWidgets.QWidget().setLayout(old)
        col = QtWidgets.QVBoxLayout(self._scroll_host)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(8)

        kind, provider, model = self._backend_identity()
        cap = capabilities.capability_summary(kind=kind, provider=provider, model=model)
        head = QtWidgets.QHBoxLayout()
        head.addWidget(W.label(f"Backend: {provider} ({kind})", kind="head"))
        head.addStretch(1)
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.clicked.connect(self._render)
        head.addWidget(refresh)
        col.addLayout(head)
        col.addWidget(W.label(
            f"schema: {cap['schema']}   ·   prefill: {'yes' if cap['prefill'] else 'no'}",
            kind="muted"))
        col.addWidget(W.hline())

        supported = capabilities.supported_sampling(kind, provider)
        no_sampling = capabilities._no_sampling_model(kind, model)
        for snake, camel in capabilities.SAMPLING_KEYS.items():
            if no_sampling:
                state, reason = "inactive", f"{model} rejects all sampling parameters"
            elif snake in supported:
                state, reason = "active", "applied to this backend"
            else:
                state, reason = "inactive", f"not honored by the {provider} backend"
            col.addWidget(self._row(camel, state, reason))
        for camel, reason in capabilities.UNAVAILABLE_KEYS.items():
            col.addWidget(self._row(camel, "unavailable", reason))
        col.addStretch(1)

    def _row(self, name: str, state: str, reason: str) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        lab = QtWidgets.QLabel(name)
        lab.setMinimumWidth(160)
        lab.setToolTip(reason)
        row.addWidget(lab)
        marker = _marker(state)
        marker.setToolTip(reason)
        row.addWidget(marker)
        row.addWidget(W.label(reason, kind="soft"), 1)
        return w


# ── lean tabs (truthful static data + console hand-off) ───────────────────────

def build_server(ctx: TabContext) -> QtWidgets.QWidget:
    from .. import ctl  # for the port constants only (cheap)
    inner, col = _column()
    col.addWidget(W.label("Model server — staged config", kind="head"))
    backend = config.configured_summary().get("backend", "local")
    prov = config.PROVIDERS.get(backend, {})
    rows = [
        ("backend", backend),
        ("model", prov.get("model", "(local gguf)")),
        ("llama-server port", str(ctl.LLAMA_PORT)),
        ("bridge port", str(ctl.UI_PORT)),
    ]
    grid = QtWidgets.QGridLayout()
    for i, (k, v) in enumerate(rows):
        grid.addWidget(W.label(k, kind="muted"), i, 0)
        grid.addWidget(W.label(str(v)), i, 1)
    grid.setColumnStretch(1, 1)
    col.addLayout(grid)
    col.addWidget(W.label("Live vs staged parameters appear here once the bridge is up.",
                          kind="soft"))
    col.addWidget(W.hline())
    col.addWidget(_action_buttons(ctx, [
        ("Start", ("start",)), ("Stop all", ("stop", "--all")), ("Restart", ("restart",)),
    ]))
    col.addStretch(1)
    return _scroll(inner)


def build_memory(ctx: TabContext) -> QtWidgets.QWidget:
    inner, col = _column()
    col.addWidget(W.label("Memory", kind="head"))
    layers = None
    try:
        layers = config.memory_layers()
    except Exception:
        layers = None
    if layers:
        col.addWidget(W.label(f"{len(layers)} configured tier(s)", kind="muted"))
    else:
        col.addWidget(W.label("default rolling + L1/L2/L3 tiers", kind="muted"))
    col.addWidget(W.hline())
    col.addWidget(_action_buttons(ctx, [
        ("Stats", ("memory", "stats")),
        ("Backup", ("memory", "backup")),
        ("Clear cache", ("memory", "clear-cache")),
        ("Clear rolling", ("memory", "clear-rolling")),
    ]))
    col.addStretch(1)
    return _scroll(inner)


class KnowledgeTab(QtWidgets.QWidget):
    """Notes/chats/links actions + a durable reminders panel (§8), read offline."""

    def __init__(self, ctx: TabContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        inner, col = _column()
        col.addWidget(W.label("Knowledge", kind="head"))
        col.addWidget(_action_buttons(ctx, [
            ("Notes", ("notes", "list")),
            ("Chats", ("chats", "list")),
            ("Links", ("links", "list")),
            ("Ingest…", ("ingest",)),
        ]))
        col.addWidget(W.hline())

        rhead = QtWidgets.QHBoxLayout()
        rhead.addWidget(W.label("Reminders — durable, fire-once (§8)", kind="head"))
        rhead.addStretch(1)
        add_btn = QtWidgets.QPushButton("Add reminder…")
        add_btn.clicked.connect(self._add_reminder)
        rhead.addWidget(add_btn)
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.clicked.connect(self._reload_reminders)
        rhead.addWidget(refresh)
        col.addLayout(rhead)

        self.rem_count = W.label("", kind="muted")
        col.addWidget(self.rem_count)
        self.rem_list = QtWidgets.QPlainTextEdit()
        self.rem_list.setReadOnly(True)
        self.rem_list.setMinimumHeight(160)
        col.addWidget(self.rem_list, 1)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(_scroll(inner))
        self._reload_reminders()

    def _reload_reminders(self) -> None:
        try:
            from .. import schedule
            sched = schedule.Schedule()
            counts = sched.counts()
            items = sched.list(include_terminal=False)
        except Exception as exc:
            self.rem_count.setText(f"reminders unavailable: {exc}")
            self.rem_list.setPlainText("")
            return
        self.rem_count.setText(
            f"pending {counts.get('pending', 0)} · fired {counts.get('fired', 0)} · "
            f"done {counts.get('done', 0)} · total {counts.get('total', 0)}")
        if not items:
            self.rem_list.setPlainText("(no pending reminders)")
            return
        lines = [f"{r.get('due', '?')}   {r.get('text', '')}   [{r.get('status', '?')}]"
                 for r in items]
        self.rem_list.setPlainText("\n".join(lines))

    def _add_reminder(self) -> None:
        when, ok = QtWidgets.QInputDialog.getText(
            self, "Add reminder", "When (ISO time or +30m / +2h / +1d):")
        if not ok or not when.strip():
            return
        text, ok = QtWidgets.QInputDialog.getText(self, "Add reminder", "Text:")
        if not ok or not text.strip():
            return
        try:
            from .. import schedule
            schedule.Schedule().add(text.strip(), when.strip(), source="launcher")
            self.ctx.flash("reminder added")
        except Exception as exc:
            self.ctx.flash(f"bad reminder: {exc}")
        self._reload_reminders()


def build_diagnostics(ctx: TabContext) -> QtWidgets.QWidget:
    inner, col = _column()
    col.addWidget(W.label("Diagnostics", kind="head"))
    col.addWidget(W.label(
        "Run a check; output streams in the Consoles tab.", kind="muted"))
    col.addWidget(W.hline())
    col.addWidget(_action_buttons(ctx, [
        ("Status", ("status",)),
        ("Doctor", ("doctor",)),
        ("Processes", ("processes",)),
        ("Logs", ("logs",)),
    ]))
    col.addStretch(1)
    return _scroll(inner)


# ── Consoles (Tier-4 + live output) ───────────────────────────────────────────

class ConsolesTab(QtWidgets.QWidget):
    """Embedded consoles: streaming command output, read-only log tails, an
    interactive REPL, and the guided Tier-4 file editor. Read-only by default;
    each PTY console has its own Interactive toggle + indicator."""

    def __init__(self, ctx: TabContext, *, front_path: str, server_log: str,
                 bridge_log: str, config_path: str, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._front = front_path
        self._config_path = config_path

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(W.label("Consoles", kind="head"))
        bar.addStretch(1)
        edit_btn = QtWidgets.QPushButton("Open editor on a file… (Tier 4)")
        edit_btn.clicked.connect(self._open_editor)
        edit_btn.setEnabled(qt_terminal.pty_available())
        bar.addWidget(edit_btn)
        lay.addLayout(bar)
        if not qt_terminal.pty_available():
            lay.addWidget(W.label(
                "embedded PTY unavailable — install lk[gui] (pyte); logs still tail.",
                kind="soft"))

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        lay.addWidget(self.tabs, 1)

        self.output = qt_terminal.PtyTerminal(title="command output")
        self.tabs.addTab(self.output, "Output")
        self.server = qt_terminal.LogView(server_log)
        self.tabs.addTab(self.server, "Server log")
        self.bridge = qt_terminal.LogView(bridge_log)
        self.tabs.addTab(self.bridge, "Bridge log")
        self.tabs.addTab(self._build_repl(), "REPL")
        self.server.start()
        self.bridge.start()

    def _build_repl(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        row = QtWidgets.QHBoxLayout()
        start = QtWidgets.QPushButton("Start REPL")
        start.setEnabled(qt_terminal.pty_available())
        self.repl_term = qt_terminal.PtyTerminal(title="lk repl")
        start.clicked.connect(self._start_repl)
        row.addWidget(start)
        row.addWidget(W.label("a real terminal chat — toggle Interactive to type", kind="soft"))
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(self.repl_term, 1)
        return w

    def _start_repl(self) -> None:
        if self.repl_term.spawn([sys.executable, self._front, "repl"]):
            self.repl_term.set_interactive(True)

    def open_command(self, argv: tuple[str, ...], title: str = "") -> bool:
        """Stream `lk <argv>` into the Output console. False if no PTY available."""
        if not qt_terminal.pty_available():
            return False
        ok = self.output.spawn([sys.executable, self._front, *argv])
        if ok:
            self.output.set_interactive(False)
            self.tabs.setCurrentWidget(self.output)
        return ok

    def _open_editor(self) -> None:
        path, ok = QtWidgets.QInputDialog.getText(
            self, "Open editor (Tier 4)", "File to edit:", text=self._config_path)
        if not ok or not path.strip():
            return
        editor = qt_terminal.GuidedEditor(path.strip(), on_apply=self._validate_after_edit)
        idx = self.tabs.addTab(editor, "Editor")
        self.tabs.setCurrentIndex(idx)
        editor.cancelled.connect(lambda e=editor: self._close_editor(e, "edit cancelled"))
        editor.applied.connect(lambda _c, e=editor: self._close_editor(e, "edit applied"))
        if not editor.start():
            self._close_editor(editor, "editor unavailable")

    def _close_editor(self, editor: QtWidgets.QWidget, message: str) -> None:
        i = self.tabs.indexOf(editor)
        if i >= 0:
            self.tabs.removeTab(i)
        editor.deleteLater()
        self.ctx.flash(message)

    def _validate_after_edit(self, content: str) -> None:
        if self._config_path and content and self._config_path.endswith(".json"):
            try:
                json.loads(content)
            except Exception as exc:
                self.ctx.flash(f"⚠ invalid JSON saved: {exc}")
