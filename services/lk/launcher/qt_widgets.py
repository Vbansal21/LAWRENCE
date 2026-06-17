"""Shared Qt widgets + dark theme for the launcher window.

The palette is lifted from the desktop popup (`apps/desktop/web/styles.css`) so the
launcher and the overlay read as one product. Everything here is import-safe only
when PySide6 is installed — callers reach it lazily through `qt_app`, never on the
fast `lk` control path.
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


# ── design tokens (popup styles.css → solid Qt colors) ────────────────────────
TOKENS: dict[str, str] = {
    "bg": "#0e1210",       # window background (popup --bg, flattened)
    "bar": "#161c19",      # panels / selected tab / buttons (popup --bar)
    "raise": "#1b231f",    # hovered surface
    "sink": "#0b0f0d",     # inputs / consoles (recessed)
    "line": "#2a332d",     # borders (popup --line, flattened)
    "line2": "#3a463d",    # stronger border on hover
    "text": "#eef3ee",     # primary text (popup --text)
    "muted": "#a8b2aa",    # secondary text (popup --muted)
    "soft": "#78857c",     # tertiary / disabled (popup --soft)
    "accent": "#76d083",   # active / ok (popup --accent)
    "amber": "#d6ad55",    # processing / warn (popup --amber)
    "danger": "#e06c6c",   # blocked / conflict / destructive
}

# Status-dot semantics shared by the whole UI.
DOT_COLORS: dict[str, str] = {
    "active": TOKENS["accent"],
    "processing": TOKENS["amber"],
    "blocked": TOKENS["danger"],
    "off": TOKENS["soft"],
}


def build_qss(t: dict[str, str] = TOKENS) -> str:
    """The application stylesheet, parameterised by the token palette."""
    return f"""
    QWidget {{ background: {t['bg']}; color: {t['text']}; font-size: 13px; }}
    QMainWindow, QDialog {{ background: {t['bg']}; }}
    QToolTip {{ background: {t['bar']}; color: {t['text']}; border: 1px solid {t['line']};
               padding: 4px 6px; }}

    QTabWidget::pane {{ border: 1px solid {t['line']}; border-radius: 9px; top: -1px;
                       background: {t['bg']}; }}
    QTabBar::tab {{ background: transparent; color: {t['muted']}; padding: 7px 15px;
                   margin-right: 2px; border: 1px solid transparent;
                   border-top-left-radius: 8px; border-top-right-radius: 8px; }}
    QTabBar::tab:selected {{ color: {t['text']}; background: {t['bar']};
                            border: 1px solid {t['line']}; border-bottom-color: {t['bar']}; }}
    QTabBar::tab:hover:!selected {{ color: {t['text']}; }}

    QPushButton {{ background: {t['bar']}; color: {t['text']}; border: 1px solid {t['line']};
                  border-radius: 7px; padding: 7px 14px; }}
    QPushButton:hover {{ background: {t['raise']}; border-color: {t['line2']}; }}
    QPushButton:pressed {{ background: {t['sink']}; }}
    QPushButton:disabled {{ color: {t['soft']}; border-color: {t['line']}; background: {t['bg']}; }}
    QPushButton[accent="true"] {{ color: #dffbe6; border-color: rgba(118,208,131,0.55); }}
    QPushButton[accent="true"]:hover {{ background: rgba(118,208,131,0.12); }}
    QPushButton[danger="true"] {{ color: #ffdede; border-color: rgba(224,108,108,0.55); }}
    QPushButton[danger="true"]:hover {{ background: rgba(224,108,108,0.12); }}

    QToolButton {{ background: {t['bar']}; color: {t['text']}; border: 1px solid {t['line']};
                  border-radius: 7px; padding: 6px 8px; }}
    QToolButton:hover {{ background: {t['raise']}; border-color: {t['line2']}; }}
    QToolButton::menu-indicator {{ width: 0px; }}

    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
        background: {t['sink']}; color: {t['text']}; border: 1px solid {t['line']};
        border-radius: 7px; padding: 6px 8px; selection-background-color: rgba(118,208,131,0.35); }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {t['accent']}; }}

    QComboBox {{ background: {t['bar']}; color: {t['text']}; border: 1px solid {t['line']};
                border-radius: 7px; padding: 5px 10px; }}
    QComboBox:hover {{ border-color: {t['line2']}; }}
    QComboBox QAbstractItemView {{ background: {t['bar']}; color: {t['text']};
                border: 1px solid {t['line']}; selection-background-color: {t['raise']}; }}

    QMenu {{ background: {t['bar']}; color: {t['text']}; border: 1px solid {t['line']}; }}
    QMenu::item:selected {{ background: {t['raise']}; }}

    QLabel[muted="true"] {{ color: {t['muted']}; }}
    QLabel[soft="true"] {{ color: {t['soft']}; }}
    QLabel[head="true"] {{ color: {t['text']}; font-size: 15px; font-weight: 600; }}

    QFrame#card {{ background: {t['bar']}; border: 1px solid {t['line']}; border-radius: 11px; }}
    QFrame[hline="true"] {{ background: {t['line']}; max-height: 1px; min-height: 1px; border: none; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t['line2']}; border-radius: 5px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['soft']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {t['line2']}; border-radius: 5px; min-width: 24px; }}
    """


def apply_theme(app: QtWidgets.QApplication, t: dict[str, str] = TOKENS) -> None:
    """Apply the dark palette + stylesheet + base font to the whole application."""
    app.setStyle("Fusion")
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, QtGui.QColor(t["bg"]))
    pal.setColor(QtGui.QPalette.Base, QtGui.QColor(t["sink"]))
    pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(t["bar"]))
    pal.setColor(QtGui.QPalette.Text, QtGui.QColor(t["text"]))
    pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor(t["text"]))
    pal.setColor(QtGui.QPalette.Button, QtGui.QColor(t["bar"]))
    pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(t["text"]))
    pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(t["accent"]))
    pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(t["bg"]))
    pal.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(t["bar"]))
    pal.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(t["text"]))
    pal.setColor(QtGui.QPalette.PlaceholderText, QtGui.QColor(t["soft"]))
    app.setPalette(pal)
    base = QtGui.QFont("Inter")
    base.setStyleHint(QtGui.QFont.SansSerif)
    base.setPointSize(10)
    app.setFont(base)
    app.setStyleSheet(build_qss(t))


def mono_font(point_size: int = 10) -> QtGui.QFont:
    """A monospaced font for consoles / metrics / code, with sane fallbacks."""
    f = QtGui.QFont("JetBrains Mono")
    f.setStyleHint(QtGui.QFont.Monospace)
    f.setFamilies(["JetBrains Mono", "DejaVu Sans Mono", "Menlo", "Consolas", "monospace"])
    f.setPointSize(point_size)
    return f


# ── small reusable primitives ─────────────────────────────────────────────────

class StatusDot(QtWidgets.QWidget):
    """A painted status circle: active / processing / blocked / off."""

    def __init__(self, state: str = "off", diameter: int = 12, parent=None):
        super().__init__(parent)
        self._state = state if state in DOT_COLORS else "off"
        self._d = diameter
        self.setFixedSize(diameter + 4, diameter + 4)

    def set_state(self, state: str) -> None:
        state = state if state in DOT_COLORS else "off"
        if state != self._state:
            self._state = state
            self.update()

    def state(self) -> str:
        return self._state

    def paintEvent(self, _evt) -> None:  # noqa: N802 (Qt override)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        color = QtGui.QColor(DOT_COLORS[self._state])
        ring = QtGui.QColor(color)
        ring.setAlpha(70)
        cx, cy = self.width() / 2, self.height() / 2
        if self._state != "off":
            p.setBrush(ring)
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(QtCore.QPointF(cx, cy), self._d / 2 + 1.5, self._d / 2 + 1.5)
        p.setBrush(color)
        p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(QtCore.QPointF(cx, cy), self._d / 2, self._d / 2)
        p.end()


def card(*, layout: QtWidgets.QLayout | None = None) -> QtWidgets.QFrame:
    """A bordered panel frame; pass a layout or set one later."""
    f = QtWidgets.QFrame()
    f.setObjectName("card")
    if layout is not None:
        f.setLayout(layout)
    return f


def hline() -> QtWidgets.QFrame:
    f = QtWidgets.QFrame()
    f.setProperty("hline", True)
    f.setFrameShape(QtWidgets.QFrame.NoFrame)
    return f


def label(text: str, *, kind: str = "") -> QtWidgets.QLabel:
    """A QLabel tagged muted/soft/head for the stylesheet, or plain."""
    lab = QtWidgets.QLabel(text)
    if kind in ("muted", "soft", "head"):
        lab.setProperty(kind, True)
    return lab


def placeholder(text: str) -> QtWidgets.QWidget:
    """A centered 'coming next' stub for tabs not yet built."""
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setAlignment(QtCore.Qt.AlignCenter)
    lab = label(text, kind="muted")
    lab.setAlignment(QtCore.Qt.AlignCenter)
    lay.addWidget(lab)
    return w


class ActionButton(QtWidgets.QWidget):
    """A primary action button with an optional Tier-2 dropdown of child actions.

    The primary click and every menu entry call `on_run(action_id)`. The dropdown
    uses a native vector arrow (no glyph fonts → no tofu boxes, unlike the old
    tkinter launcher). `accent`/`danger` styling comes from the registry record.
    """

    def __init__(self, action, children, on_run, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self.primary = QtWidgets.QPushButton(action.short or action.label)
        if action.hint:
            self.primary.setToolTip(action.hint)
        if action.confirm:
            self.primary.setProperty("danger", True)
        elif action.id in ("start", "ui"):
            self.primary.setProperty("accent", True)
        self.primary.clicked.connect(lambda: on_run(action.id))
        lay.addWidget(self.primary)

        self.more = None
        if children:
            self.more = QtWidgets.QToolButton()
            self.more.setArrowType(QtCore.Qt.DownArrow)
            self.more.setPopupMode(QtWidgets.QToolButton.InstantPopup)
            self.more.setToolTip("more…")
            menu = QtWidgets.QMenu(self.more)
            for ch in children:
                act = menu.addAction(ch.short or ch.label)
                if ch.hint:
                    act.setToolTip(ch.hint)
                act.triggered.connect(lambda _checked=False, cid=ch.id: on_run(cid))
            self.more.setMenu(menu)
            lay.addWidget(self.more)
