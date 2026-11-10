"""Small reusable widgets: path pickers, notices with actions, a drop area. Theme-aware (light and dark)."""
import os

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

TONES = {  # (light theme, dark theme) accent colours with WCAG-AA contrast against the window background
    "error": ("#b3261e", "#ffb4ab"),
    "warn": ("#7a4b00", "#ffcc80"),
    "ok": ("#1b5e20", "#a5d6a7"),
    "info": ("#0b57d0", "#a8c7fa"),
}


def soft(text):
    """Let long paths wrap after their separators when shown in a label (display only)."""
    return text.replace("\\", "\\​").replace("/", "/​")


def is_dark(w):
    return w.palette().color(QPalette.ColorRole.Window).lightness() < 128


def tone(w, kind):
    light, dark = TONES[kind]
    return dark if is_dark(w) else light


def label(text="", bold=False, scale=1.0, wrap=True, selectable=False):
    lab = QLabel(text)
    f = lab.font()
    f.setBold(bold)
    if scale != 1.0:
        f.setPointSizeF(f.pointSizeF() * scale)
    lab.setFont(f)
    lab.setWordWrap(wrap)
    if selectable:
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lab


def set_text(lab, text):
    """Set a label's text and hide it when empty, so empty lines take no space."""
    lab.setText(text or "")
    lab.setVisible(bool(text))


class PrimaryButton(QPushButton):
    """The one main action of a page: filled with the system accent colour, readable in light and dark themes,
    with a visible keyboard-focus ring."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("primary")
        self.setMinimumHeight(40)
        f = self.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 1.1)
        self.setFont(f)
        self._busy = False
        self._restyle()
        # style-sheeted widgets do not reliably receive PaletteChange: follow the system colour scheme directly
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._scheme_changed)

    def _scheme_changed(self, *_):
        QTimer.singleShot(0, self, self._restyle)      # after Qt has applied the new palette

    def _restyle(self):
        pal = self.palette()
        acc = pal.color(QPalette.ColorRole.Highlight)
        txt = pal.color(QPalette.ColorRole.HighlightedText)
        hover, down = acc.lighter(112), acc.darker(115)
        ring = pal.color(QPalette.ColorRole.WindowText)
        win, fg = pal.color(QPalette.ColorRole.Window), pal.color(QPalette.ColorRole.WindowText)
        off_bg = win
        off_fg = QColor(*(round(a * 0.5 + b * 0.5) for a, b in zip(fg.getRgb()[:3], win.getRgb()[:3])))  # muted
        self._busy = True
        try:
            self.setStyleSheet(
                f"QPushButton#primary {{ background-color: {acc.name()}; color: {txt.name()}; border: 2px solid "
                f"{acc.name()}; border-radius: 6px; padding: 6px 20px; }}"
                f"QPushButton#primary:hover {{ background-color: {hover.name()}; border-color: {hover.name()}; }}"
                f"QPushButton#primary:pressed {{ background-color: {down.name()}; border-color: {down.name()}; }}"
                f"QPushButton#primary:focus {{ border-color: {ring.name()}; }}"
                f"QPushButton#primary:disabled {{ background-color: {off_bg.name()}; color: {off_fg.name()}; "
                f"border: 1px solid {off_fg.name()}; }}")
        finally:
            self._busy = False

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.Type.PaletteChange and not self._busy:
            self._restyle()


class Notice(QFrame):
    """A short message with a coloured accent bar, optional action buttons and optional technical details."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("notice")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 4, 4, 4)
        lay.setSpacing(4)
        self.title = label(bold=True)
        self.body = label(selectable=True)
        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(0, 2, 0, 0)
        self.buttons = []
        self.toggle = QPushButton("Details")
        self.toggle.setFlat(True)
        self.toggle.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.toggle.clicked.connect(self._toggle)
        self.detail = label(selectable=True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse |
                                            Qt.TextInteractionFlag.TextSelectableByKeyboard)
        lay.addWidget(self.title)
        lay.addWidget(self.body)
        lay.addLayout(self.actions)
        lay.addWidget(self.detail)
        self.kind = None
        self._restyling = False
        self.hide()

    def _toggle(self):
        self.detail.setVisible(not self.detail.isVisible())
        self.toggle.setText("Hide details" if self.detail.isVisible() else "Details")

    def _style(self):
        c = tone(self, self.kind)
        self._restyling = True
        try:
            self.setStyleSheet(f"QFrame#notice {{ border: none; border-left: 3px solid {c}; }}")
            self.title.setStyleSheet(f"color: {c};")
        finally:
            self._restyling = False

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.Type.PaletteChange and self.kind and not self._restyling:
            self._style()            # Windows switched between light and dark

    def show_message(self, kind, title, text="", detail="", actions=()):
        """actions: [(button text, callback)]; the first one is the default action."""
        self.kind = kind
        self._style()
        self.title.setText(title)
        self.title.setVisible(bool(title))
        self.body.setText(text)
        self.body.setVisible(bool(text))
        while self.actions.count():                  # rebuild the button row
            item = self.actions.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.toggle:
                w.deleteLater()
        self.buttons = []
        for txt, cb in actions:
            b = QPushButton(txt)
            b.clicked.connect(cb)
            b.setAccessibleName(txt.replace("&", ""))
            self.actions.addWidget(b)
            self.buttons.append(b)
        if detail:
            self.actions.addWidget(self.toggle)
        self.toggle.setVisible(bool(detail))
        self.toggle.setText("Details")
        self.actions.addStretch(1)
        self.detail.setText(soft(detail))
        self.detail.hide()
        self.setAccessibleName(f"{title}. {text}")
        self.show()

    def clear(self):
        self.kind = None
        self.hide()


class PathPicker(QWidget):
    """Path field with Browse. Emits changed(path) when the path changes (typed, browsed or set)."""
    changed = Signal(str)

    def __init__(self, caption, mode="file", file_filter="All files (*)", parent=None, name="file",
                 placeholder=None):
        super().__init__(parent)
        self.caption, self.mode, self.filter = caption, mode, file_filter
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder or ("Choose a file" if mode == "file" else "Choose a folder"))
        self.edit.setAccessibleName(name)
        self.edit.editingFinished.connect(self._typed)
        self.browse = QPushButton("Browse…")
        self.browse.setAccessibleName(f"Browse for {name}")
        self.browse.clicked.connect(self._browse)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.browse)
        self._last = ""
        self.start_dir = ""

    def path(self):
        return self.edit.text().strip().strip('"')

    def set_path(self, p, emit=True):
        p = os.path.normpath(p) if p else ""
        self.edit.setText(p)
        self.edit.setCursorPosition(len(p))
        if emit and p != self._last:
            self._last = p
            self.changed.emit(p)
        elif not emit:
            self._last = p

    def _typed(self):
        p = self.path()
        if p != self._last:
            self.set_path(p)

    def _browse(self):
        start = self.path() or self.start_dir
        if self.mode == "file":
            p, _ = QFileDialog.getOpenFileName(self, self.caption, start, self.filter)
        else:
            p = QFileDialog.getExistingDirectory(self, self.caption, start)
        if p:
            self.set_path(p)


class DropArea(QWidget):
    """Accepts dropped files/folders; emits dropped(path) for the first local path. Highlights while dragging."""
    dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("drop")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._hover(False)

    def _hover(self, on):
        c = self.palette().color(QPalette.ColorRole.Highlight)
        self.setStyleSheet(f"QWidget#drop {{ border: 2px dashed {c.name()}; border-radius: 6px; }}" if on else
                           "QWidget#drop { border: 2px solid transparent; border-radius: 6px; }")

    @staticmethod
    def _first_path(e):
        md = e.mimeData()
        if md.hasUrls():
            for u in md.urls():
                if u.isLocalFile():
                    return u.toLocalFile()
        return None

    def dragEnterEvent(self, e):
        if self._first_path(e):
            e.acceptProposedAction()
            self._hover(True)
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._first_path(e):
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._hover(False)

    def dropEvent(self, e):
        self._hover(False)
        p = self._first_path(e)
        if p:
            e.acceptProposedAction()
            self.dropped.emit(os.path.normpath(p))
