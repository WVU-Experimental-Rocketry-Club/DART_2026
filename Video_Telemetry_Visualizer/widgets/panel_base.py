"""
PanelWidget
-----------
Base class for all display panels.  Each panel has:
  • A thin dark header bar with a title, a coloured status dot, and a status label.
  • A content area below that subclasses populate via self.content_layout.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
)


_FRAME_STYLE = """
QWidget#panel_frame {
    border: 1px solid #3a5a90;
    border-radius: 4px;
    background: #080a18;
}
QWidget#panel_header {
    background: #0e1530;
    border-bottom: 1px solid #3a5a90;
    border-radius: 0px;
}
"""


class PanelWidget(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("panel_frame")
        self.setStyleSheet(_FRAME_STYLE)

        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(1, 1, 1, 1)

        # ── Header bar ─────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("panel_header")
        header.setFixedHeight(26)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(8, 0, 8, 0)
        hlay.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #aac8ff; font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 11px; font-weight: bold; letter-spacing: 1.5px; "
            "background: transparent; border: none;"
        )
        hlay.addWidget(title_lbl)
        hlay.addStretch()

        self._dot = QLabel("●")
        self._dot.setStyleSheet("color: #2a4060; font-size: 9px; background: transparent; border: none;")
        hlay.addWidget(self._dot)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            "color: #2a4060; font-family: monospace; font-size: 10px; "
            "background: transparent; border: none;"
        )
        hlay.addWidget(self._status_lbl)

        outer.addWidget(header)

        # ── Content area — subclasses add to self.content_layout ───
        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self._body)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        outer.addWidget(self._body, stretch=1)

    def set_status(self, text: str, ok: bool = True):
        colour = "#22cc55" if ok else "#cc4422"
        self._dot.setStyleSheet(
            f"color: {colour}; font-size: 9px; background: transparent; border: none;"
        )
        self._status_lbl.setStyleSheet(
            f"color: {colour}; font-family: monospace; font-size: 10px; "
            f"background: transparent; border: none;"
        )
        self._status_lbl.setText(text)
