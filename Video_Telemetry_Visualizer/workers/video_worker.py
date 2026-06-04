"""
VideoWorker
-----------
Captures frames from a camera/HDMI capture card using OpenCV and emits
them as QImage signals for display in the UI.

HDMI capture cards enumerate as standard video devices:
  Windows : DirectShow  → indices 0, 1, 2 …
  Linux   : V4L2        → /dev/video0, /dev/video1 … (pass as index or path)

Adjust TARGET_FPS and the cap.set() calls below to match your hardware.
"""

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage


class VideoWorker(QThread):
    """
    Runs in its own thread. Emits one frame_ready(QImage) per captured frame.
    Tries to reconnect automatically if the device disappears.
    """

    frame_ready    = Signal(QImage)   # RGB888 frame ready for display
    status_changed = Signal(str)      # "OK"  |  "NO SIGNAL"  |  "ERROR"

    TARGET_FPS = 30

    def __init__(self, device_index: int = 0, parent=None):
        super().__init__(parent)
        self.device_index = device_index
        self._running = False

    # ── Thread body ────────────────────────────────────────────────────

    def run(self):
        self._running = True
        frame_ms = max(1, int(1000 / self.TARGET_FPS))
        cap = self._open()

        while self._running:
            # Auto-reconnect if device was lost
            if cap is None or not cap.isOpened():
                self.msleep(500)
                cap = self._open()
                continue

            ret, frame = cap.read()
            if not ret:
                self.status_changed.emit("NO SIGNAL")
                self.msleep(frame_ms)
                continue

            # BGR → RGB → QImage (copy so the numpy buffer stays valid)
            rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            img  = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()
            self.frame_ready.emit(img)
            self.msleep(frame_ms)

        if cap and cap.isOpened():
            cap.release()

    def stop(self):
        self._running = False
        self.wait()

    # ── Helpers ────────────────────────────────────────────────────────

    def _open(self):
        """Try to open the capture device; return cap or None."""
        cap = cv2.VideoCapture(self.device_index, cv2.CAP_MSMF)
        if not cap.isOpened():
            self.status_changed.emit("NO SIGNAL")
            return None

        # Request 1080p30 — the driver will use the closest supported mode
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS,          self.TARGET_FPS)

        self.status_changed.emit("OK")
        return cap
