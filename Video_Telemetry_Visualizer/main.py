#!/usr/bin/env python3
"""
IREC Ground Station Viewer
--------------------------
Layout A:
  Top row  (60 %) : Video Feed A | Video Feed B
  Bottom row (40%): Telemetry HUD | Map / Ground Track | Rocket 3D

Usage:
  python main.py                          # real hardware (cam 0, cam 1, no serial)
  python main.py --demo                   # simulated flight, no hardware needed
  python main.py --cam-a 0 --cam-b 2 --port COM4 --baud 115200
"""

import sys
import argparse
import threading
import functools
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QSplitter, QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

from workers.video_worker import VideoWorker
from workers.serial_worker import SerialWorker, DemoWorker
from widgets.video_widget import VideoWidget
from widgets.telemetry_widget import TelemetryWidget
from widgets.map_widget import MapWidget
from widgets.rocket_widget import RocketWidget


# ---------------------------------------------------------------------------
# Local tile server — serves web/tiles/ at http://localhost:8765/tiles/
# Started automatically if the tiles folder exists (i.e. download_tiles.py
# has been run).  Falls back silently if the folder is absent (live CDN used).
# ---------------------------------------------------------------------------

TILE_PORT = 8765

def _start_tile_server():
    tiles_dir = Path(__file__).parent / "web" / "tiles"
    if not tiles_dir.exists():
        return   # no cached tiles — live CDN will be used instead

    handler = functools.partial(
        SimpleHTTPRequestHandler,
        directory=str(Path(__file__).parent / "web"),
    )
    # Suppress the per-request log lines
    handler.log_message = lambda *a: None   # type: ignore

    server = HTTPServer(("127.0.0.1", TILE_PORT), handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[tile server] serving web/ at http://127.0.0.1:{TILE_PORT}/")


# ---------------------------------------------------------------------------
# Dark mission-control palette
# ---------------------------------------------------------------------------

def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    bg      = QColor(10,  12,  22)
    surface = QColor(16,  20,  38)
    text    = QColor(235, 242, 255)    # near-white for glare visibility
    muted   = QColor(120, 150, 200)
    accent  = QColor(60,  130, 230)

    pal.setColor(QPalette.Window,          bg)
    pal.setColor(QPalette.WindowText,      text)
    pal.setColor(QPalette.Base,            surface)
    pal.setColor(QPalette.AlternateBase,   QColor(20, 24, 44))
    pal.setColor(QPalette.Text,            text)
    pal.setColor(QPalette.Button,          surface)
    pal.setColor(QPalette.ButtonText,      text)
    pal.setColor(QPalette.Highlight,       accent)
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.PlaceholderText, muted)
    pal.setColor(QPalette.ToolTipBase,     surface)
    pal.setColor(QPalette.ToolTipText,     text)
    app.setPalette(pal)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class GroundStation(QMainWindow):
    def __init__(self, args: argparse.Namespace):
        super().__init__()
        self.args = args
        self.setWindowTitle("IREC Ground Station  —  Mothman Avenged")
        self.setMinimumSize(1280, 800)
        self.resize(1600, 950)

        self._build_ui()
        self._start_workers()

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setSpacing(4)
        outer.setContentsMargins(4, 4, 4, 4)

        # Top row: two video feeds side-by-side
        self.video_a = VideoWidget("CAMERA A", cam_index=self.args.cam_a)
        self.video_b = VideoWidget("CAMERA B", cam_index=self.args.cam_b)

        top_split = QSplitter(Qt.Horizontal)
        top_split.addWidget(self.video_a)
        top_split.addWidget(self.video_b)
        top_split.setSizes([1, 1])          # equal 50 / 50

        # Bottom row: telemetry | map | rocket 3D
        self.telemetry = TelemetryWidget()
        self.map_view  = MapWidget()
        self.rocket    = RocketWidget()

        bot_split = QSplitter(Qt.Horizontal)
        bot_split.addWidget(self.telemetry)
        bot_split.addWidget(self.map_view)
        bot_split.addWidget(self.rocket)
        bot_split.setSizes([1, 1, 1])       # equal 33 / 33 / 33

        # Vertical split: 60 % video, 40 % data
        vsplit = QSplitter(Qt.Vertical)
        vsplit.addWidget(top_split)
        vsplit.addWidget(bot_split)
        vsplit.setSizes([580, 380])

        outer.addWidget(vsplit)

        # Status bar
        mode = "DEMO MODE" if self.args.demo else f"PORT {self.args.port or '(none)'}"
        self._status = QLabel(f"⬤  READY  |  {mode}")
        self._status.setStyleSheet(
            "color: #3a5a9a; font-family: monospace; font-size: 11px; padding: 2px 8px;"
        )
        self.statusBar().addPermanentWidget(self._status)
        self.statusBar().setStyleSheet("background: #06060f; border-top: 1px solid #1a2a4a;")

    # ── Worker start-up ────────────────────────────────────────────────

    def _start_workers(self):
        # Video capture threads
        self._worker_a = VideoWorker(self.args.cam_a)
        self._worker_a.frame_ready.connect(self.video_a.on_frame)
        self._worker_a.status_changed.connect(self.video_a.set_status)
        self._worker_a.start()

        self._worker_b = VideoWorker(self.args.cam_b)
        self._worker_b.frame_ready.connect(self.video_b.on_frame)
        self._worker_b.status_changed.connect(self.video_b.set_status)
        self._worker_b.start()

        # Telemetry / serial thread
        if self.args.demo:
            self._serial = DemoWorker()
        else:
            self._serial = SerialWorker(port=self.args.port, baud=self.args.baud)

        self._serial.telemetry_updated.connect(self._on_telemetry)
        self._serial.start()

    # ── Telemetry fan-out ──────────────────────────────────────────────

    def _on_telemetry(self, data: dict):
        self.telemetry.update(data)
        self.map_view.update_position(data)
        self.rocket.update_state(data)

        alt = data.get("alt", 0)
        spd = data.get("spd", 0)
        ab  = "AB ▼ DEPLOYED" if data.get("airbrake") else "AB — RETRACTED"
        self._status.setText(
            f"⬤  ALT {alt:>8,.0f} ft  |  SPD {spd:>6,.0f} ft/s  |  {ab}"
        )
        ok_color = "#22cc55" if alt > 0 or spd > 0 else "#3a5a9a"
        self._status.setStyleSheet(
            f"color: {ok_color}; font-family: monospace; font-size: 11px; padding: 2px 8px;"
        )

    # ── Clean shutdown ─────────────────────────────────────────────────

    def closeEvent(self, event):
        self._worker_a.stop()
        self._worker_b.stop()
        self._serial.stop()
        event.accept()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="IREC Ground Station Viewer")
    p.add_argument(
        "--demo", action="store_true",
        help="Simulate a full rocket flight — no hardware required",
    )
    p.add_argument("--cam-a", type=int, default=0,  metavar="INDEX",
                   help="Camera device index for Feed A (default: 0)")
    p.add_argument("--cam-b", type=int, default=1,  metavar="INDEX",
                   help="Camera device index for Feed B (default: 1)")
    p.add_argument("--port",  type=str, default="", metavar="PORT",
                   help="Serial port for Arduino telemetry (e.g. COM4 or /dev/ttyUSB0)")
    p.add_argument("--baud",  type=int, default=115200,
                   help="Serial baud rate (default: 115200)")
    return p.parse_args()


def main():
    args = parse_args()
    app  = QApplication(sys.argv)
    app.setApplicationName("IREC Ground Station")

    apply_dark_theme(app)
    _start_tile_server()

    win = GroundStation(args)
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
