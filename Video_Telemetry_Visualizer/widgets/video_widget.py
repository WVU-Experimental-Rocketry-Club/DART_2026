"""
VideoWidget
-----------
Displays live frames from a VideoWorker inside a PanelWidget.
Frames are scaled to fill the available area while preserving aspect ratio.
"""

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap

from .panel_base import PanelWidget


class VideoWidget(PanelWidget):
    def __init__(self, title: str, cam_index: int = 0, parent=None):
        super().__init__(title, parent)
        self.cam_index = cam_index

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._label.setStyleSheet(
            "background: #02020a; color: #1e3055; "
            "font-family: 'Consolas', monospace; font-size: 13px;"
        )
        self._label.setText(f"NO SIGNAL\n[Camera {cam_index}]")
        self.content_layout.addWidget(self._label)

        super().set_status("WAITING", ok=False)

    # ── Slots ──────────────────────────────────────────────────────────

    @Slot(QImage)
    def on_frame(self, img: QImage):
        size = self._label.size()
        if size.width() < 4 or size.height() < 4:
            return
        pix = QPixmap.fromImage(img).scaled(
            size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._label.setPixmap(pix)

    @Slot(str)
    def set_status(self, status: str):
        ok = (status.upper() == "OK")
        super().set_status(status, ok=ok)
        if not ok:
            self._label.clear()
            self._label.setText(f"NO SIGNAL\n[Camera {self.cam_index}]")
