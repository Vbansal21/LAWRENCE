"""Embedded terminals for the launcher: a read-only log tailer and a real PTY.

Three widgets:

  • ``LogView``      — read-only, scrollable tail of a log file (ANSI stripped). No
                       PTY needed; the right tool for server/bridge logs.
  • ``PtyTerminal``  — a genuine pseudo-terminal (ptyprocess) rendered through a
                       pyte VT screen, so curses/TUI programs (the chat REPL, nano)
                       draw correctly. Read-only by DEFAULT: keystrokes are ignored
                       until the per-console Interactive toggle is switched on.
  • ``GuidedEditor`` — opens ``$EDITOR`` (nano by default) on a specific file inside
                       a forced-interactive PtyTerminal, with a banner and a Cancel
                       button so you can never get lost; on exit it reads the file
                       back and hands it to an apply callback (Tier-4 capture loop).

If pyte/ptyprocess are unavailable, ``pty_available()`` is False and callers fall
back to a non-embedded run — the launcher still works, just without live consoles.
"""
from __future__ import annotations

import os
import re
import signal

from PySide6 import QtCore, QtGui, QtWidgets

from . import qt_widgets as W

try:
    import pyte
    from ptyprocess import PtyProcess
    _HAS_PTY = True
except Exception:  # pragma: no cover - exercised only on hosts without the [gui] extra
    pyte = None
    PtyProcess = None
    _HAS_PTY = False

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def pty_available() -> bool:
    """True when a real embedded PTY console can be created on this host."""
    return _HAS_PTY


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def keymap(key: int, ctrl: bool, text: str) -> bytes | None:
    """Translate a key press into the bytes a PTY expects. Pure → unit-testable."""
    Q = QtCore.Qt
    specials = {
        Q.Key_Return: b"\r", Q.Key_Enter: b"\r", Q.Key_Backspace: b"\x7f",
        Q.Key_Tab: b"\t", Q.Key_Escape: b"\x1b",
        Q.Key_Up: b"\x1b[A", Q.Key_Down: b"\x1b[B",
        Q.Key_Right: b"\x1b[C", Q.Key_Left: b"\x1b[D",
        Q.Key_Home: b"\x1b[H", Q.Key_End: b"\x1b[F",
        Q.Key_Delete: b"\x1b[3~", Q.Key_PageUp: b"\x1b[5~", Q.Key_PageDown: b"\x1b[6~",
    }
    if key in specials:
        return specials[key]
    if ctrl and Q.Key_A <= key <= Q.Key_Z:
        return bytes([key - Q.Key_A + 1])  # Ctrl-A..Ctrl-Z → 0x01..0x1a
    if text:
        return text.encode("utf-8")
    return None


# ── read-only log tail ────────────────────────────────────────────────────────

class LogView(QtWidgets.QWidget):
    """A read-only, scrollable tail of a log file. Refreshes on a timer."""

    def __init__(self, path, *, interval_ms: int = 1000, parent=None):
        super().__init__(parent)
        self._path = os.fspath(path)
        self._pos = 0
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        head = QtWidgets.QHBoxLayout()
        head.addWidget(W.label(self._path, kind="soft"))
        head.addStretch(1)
        head.addWidget(W.label("read-only", kind="muted"))
        lay.addLayout(head)
        self._text = QtWidgets.QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(5000)
        self._text.setFont(W.mono_font(9))
        lay.addWidget(self._text, 1)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._pos = 0
        self._text.clear()
        self._poll()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        try:
            size = os.path.getsize(self._path)
        except OSError:
            return
        if size < self._pos:        # rotated/truncated → re-read from the top
            self._pos = 0
            self._text.clear()
        if size == self._pos:
            return
        try:
            with open(self._path, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(self._pos)
                chunk = fh.read()
                self._pos = fh.tell()
        except OSError:
            return
        if chunk:
            self._text.appendPlainText(strip_ansi(chunk).rstrip("\n"))
            bar = self._text.verticalScrollBar()
            bar.setValue(bar.maximum())


# ── PTY screen rendering ──────────────────────────────────────────────────────

class _ScreenView(QtWidgets.QWidget):
    """Paints a pyte screen in a monospace grid; reports a cell size to the owner."""

    def __init__(self, owner: "PtyTerminal"):
        super().__init__(owner)
        self._owner = owner
        self.setFont(W.mono_font(10))
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        fm = QtGui.QFontMetricsF(self.font())
        self._cw = max(1.0, fm.horizontalAdvance("M"))
        self._ch = max(1.0, fm.height())

    def cell(self) -> tuple[float, float]:
        return self._cw, self._ch

    def paintEvent(self, _evt) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(W.TOKENS["sink"]))
        screen = self._owner.screen
        if screen is None:
            p.end()
            return
        p.setFont(self.font())
        p.setPen(QtGui.QColor(W.TOKENS["text"]))
        for y, line in enumerate(screen.display):
            p.drawText(QtCore.QPointF(2, (y + 1) * self._ch - 2), line)
        if self._owner.interactive and self.hasFocus():
            cx = 2 + screen.cursor.x * self._cw
            cy = screen.cursor.y * self._ch
            cur = QtGui.QColor(W.TOKENS["accent"])
            cur.setAlpha(140)
            p.fillRect(QtCore.QRectF(cx, cy, self._cw, self._ch), cur)
        p.end()

    def keyPressEvent(self, evt: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._owner.handle_key(evt):
            evt.accept()
        else:
            super().keyPressEvent(evt)

    def resizeEvent(self, evt) -> None:  # noqa: N802
        self._owner.on_view_resized()
        super().resizeEvent(evt)


class PtyTerminal(QtWidgets.QWidget):
    """A real PTY child rendered via pyte. Read-only until Interactive is toggled."""

    finished = QtCore.Signal(int)

    def __init__(self, *, title: str = "", parent=None):
        super().__init__(parent)
        self.screen = None
        self._stream = None
        self._proc = None
        self._notifier = None
        self.interactive = False
        self._cols, self._rows = 80, 24

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        head = QtWidgets.QHBoxLayout()
        self._title = W.label(title, kind="muted")
        head.addWidget(self._title)
        head.addStretch(1)
        self._indicator = W.StatusDot("off")
        head.addWidget(self._indicator)
        self._mode = W.label("read-only", kind="soft")
        head.addWidget(self._mode)
        self._toggle = QtWidgets.QPushButton("Interactive")
        self._toggle.setCheckable(True)
        self._toggle.setEnabled(_HAS_PTY)
        self._toggle.toggled.connect(self.set_interactive)
        head.addWidget(self._toggle)
        lay.addLayout(head)

        self._view = _ScreenView(self)
        lay.addWidget(self._view, 1)
        if not _HAS_PTY:
            self._title.setText((title + "  ·  " if title else "")
                                + "embedded console unavailable — install lk[gui] (pyte)")

    # ── lifecycle ────────────────────────────────────────────────────────────
    def spawn(self, argv: list[str], *, env: dict | None = None, cwd: str | None = None) -> bool:
        if not _HAS_PTY:
            return False
        self.terminate()
        self._cols, self._rows = self._grid_size()
        self.screen = pyte.Screen(self._cols, self._rows)
        self._stream = pyte.ByteStream(self.screen)
        run_env = dict(os.environ)
        run_env["TERM"] = "xterm-256color"
        if env:
            run_env.update(env)
        self._proc = PtyProcess.spawn(
            list(argv), env=run_env, cwd=cwd,
            dimensions=(self._rows, self._cols))
        self._notifier = QtCore.QSocketNotifier(self._proc.fd, QtCore.QSocketNotifier.Read, self)
        self._notifier.activated.connect(self._on_readable)
        self._indicator.set_state("active")
        self._mode.setText("interactive" if self.interactive else "read-only")
        self._view.update()
        return True

    def terminate(self) -> None:
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier = None
        if self._proc is not None and self._proc.isalive():
            try:
                self._proc.kill(signal.SIGTERM)
            except Exception:
                pass
        self._proc = None

    def _on_readable(self) -> None:
        try:
            data = os.read(self._proc.fd, 65536)
        except OSError:
            data = b""
        if not data:
            self._on_exit()
            return
        self._stream.feed(data)
        self._view.update()

    def _on_exit(self) -> None:
        code = 0
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier = None
        if self._proc is not None:
            try:
                self._proc.wait()
                code = self._proc.exitstatus or 0
            except Exception:
                pass
        self._indicator.set_state("off")
        self._mode.setText("exited")
        self.finished.emit(int(code))

    # ── input ────────────────────────────────────────────────────────────────
    def set_interactive(self, on: bool) -> None:
        self.interactive = bool(on) and _HAS_PTY
        if self._toggle.isChecked() != self.interactive:
            self._toggle.setChecked(self.interactive)
        self._indicator.set_state("processing" if self.interactive else
                                  ("active" if self._proc is not None else "off"))
        self._mode.setText("interactive" if self.interactive else "read-only")
        if self.interactive:
            self._view.setFocus()
        self._view.update()

    def handle_key(self, evt: QtGui.QKeyEvent) -> bool:
        if not (self.interactive and self._proc is not None and self._proc.isalive()):
            return False
        data = keymap(int(evt.key()),
                      bool(evt.modifiers() & QtCore.Qt.ControlModifier),
                      evt.text())
        if data is None:
            return False
        try:
            self._proc.write(data)
        except Exception:
            return False
        return True

    # ── sizing ───────────────────────────────────────────────────────────────
    def _grid_size(self) -> tuple[int, int]:
        cw, ch = self._view.cell()
        cols = max(20, int(self._view.width() / cw))
        rows = max(5, int(self._view.height() / ch))
        return cols, rows

    def on_view_resized(self) -> None:
        if self.screen is None:
            return
        cols, rows = self._grid_size()
        if (cols, rows) == (self._cols, self._rows):
            return
        self._cols, self._rows = cols, rows
        try:
            self.screen.resize(rows, cols)
            if self._proc is not None and self._proc.isalive():
                self._proc.setwinsize(rows, cols)
        except Exception:
            pass


# ── guided Tier-4 editor ──────────────────────────────────────────────────────

class GuidedEditor(QtWidgets.QWidget):
    """Open $EDITOR on a file inside a PTY, then read it back and apply.

    Anti-getting-lost guard rails: a banner naming the file, a persistent Cancel
    that SIGTERMs the editor, and a scoped session (the terminal exists only for
    this edit). On a clean exit the file text is handed to ``on_apply``.
    """

    cancelled = QtCore.Signal()
    applied = QtCore.Signal(str)

    def __init__(self, path: str, *, on_apply=None, editor: str | None = None, parent=None):
        super().__init__(parent)
        self._path = os.fspath(path)
        self._on_apply = on_apply
        self._editor = editor or os.environ.get("EDITOR") or "nano"

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)
        banner = QtWidgets.QHBoxLayout()
        banner.addWidget(W.label(f"Editing: {self._path} · save & close to apply", kind="head"))
        banner.addStretch(1)
        cancel = QtWidgets.QPushButton("Cancel ←")
        cancel.setProperty("danger", True)
        cancel.clicked.connect(self._cancel)
        banner.addWidget(cancel)
        lay.addLayout(banner)

        self._term = PtyTerminal(title=self._editor)
        self._term.finished.connect(self._on_finished)
        lay.addWidget(self._term, 1)

    def start(self) -> bool:
        if not _HAS_PTY:
            return False
        ok = self._term.spawn([self._editor, self._path])
        if ok:
            self._term.set_interactive(True)
        return ok

    def _cancel(self) -> None:
        self._term.terminate()
        self.cancelled.emit()

    def _on_finished(self, _code: int) -> None:
        try:
            with open(self._path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            content = ""
        if self._on_apply is not None:
            try:
                self._on_apply(content)
            except Exception:
                pass
        self.applied.emit(content)
