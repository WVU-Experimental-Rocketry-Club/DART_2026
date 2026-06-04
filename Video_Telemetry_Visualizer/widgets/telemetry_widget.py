"""
TelemetryWidget
---------------
Live HUD panel showing:
  • Large numeric readouts: altitude, speed, expected apogee
  • Airbrake status banner
  • Scrolling altitude and speed plots (via pyqtgraph)

pyqtgraph is optional — if it is not installed the plots are simply
replaced with a plain text notice and the numeric readouts still work.
"""

import collections

from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt

from .panel_base import PanelWidget

try:
    import pyqtgraph as pg
    pg.setConfigOption("background", "#080a18")
    pg.setConfigOption("foreground", "#6080b0")
    _PG = True
except ImportError:
    _PG = False

MAX_PTS = 600   # ≈ 30 s at 20 Hz


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _big(text: str, colour: str = "#00e5ff") -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"color: {colour}; font-family: 'Consolas', 'Courier New', monospace; "
        f"font-size: 28px; font-weight: bold; background: transparent;"
    )
    return lbl


def _caption(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        "color: #7090c0; font-family: monospace; font-size: 9px; "
        "letter-spacing: 1.5px; background: transparent;"
    )
    return lbl


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class TelemetryWidget(PanelWidget):
    def __init__(self, parent=None):
        super().__init__("TELEMETRY", parent)

        self._alt_buf = collections.deque(maxlen=MAX_PTS)
        self._spd_buf = collections.deque(maxlen=MAX_PTS)

        root = QVBoxLayout()
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(4)
        self.content_layout.addLayout(root)

        # ── Numeric readouts ─────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(4)

        for attr, text, colour in [
            ("_alt_val", "0",  "#00e5ff"),   # bright cyan
            ("_spd_val", "0",  "#00ffc8"),   # bright teal-green
            ("_apo_val", "—",  "#ffcc00"),   # bright yellow
        ]:
            col = QVBoxLayout()
            col.setSpacing(1)
            val = _big(text, colour)
            setattr(self, attr, val)
            col.addWidget(val)
            stats_row.addLayout(col)

        # Captions sit below the numbers
        cap_row = QHBoxLayout()
        cap_row.setSpacing(4)
        for text in ("ALTITUDE  ft", "SPEED  ft/s", "EST. APOGEE  ft"):
            cap_row.addWidget(_caption(text))

        root.addLayout(stats_row)
        root.addLayout(cap_row)

        # ── Airbrake banner ──────────────────────────────────────────
        self._ab = QLabel("AIRBRAKES  RETRACTED")
        self._ab.setAlignment(Qt.AlignCenter)
        self._ab.setFixedHeight(26)
        self._set_ab(False)
        root.addWidget(self._ab)

        # ── Plots ────────────────────────────────────────────────────
        if _PG:
            self._build_plots(root)
        else:
            note = QLabel("pip install pyqtgraph  to enable live plots")
            note.setAlignment(Qt.AlignCenter)
            note.setStyleSheet("color: #2a3a5a; font-size: 11px; background: transparent;")
            root.addWidget(note, stretch=1)

        self.set_status("WAITING", ok=False)

    # ── Plots ──────────────────────────────────────────────────────────

    def _build_plots(self, parent: QVBoxLayout):
        def make_plot(colour: str) -> tuple:
            pw = pg.PlotWidget()
            pw.showGrid(x=False, y=True, alpha=0.12)
            pw.getAxis("bottom").hide()
            pw.getAxis("left").setStyle(tickFont=None)
            pw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            pw.setMenuEnabled(False)
            pw.setMouseEnabled(x=False, y=False)
            curve = pw.plot(pen=pg.mkPen(colour, width=2))
            return pw, curve

        self._alt_plot, self._alt_curve = make_plot("#00e5ff")
        self._spd_plot, self._spd_curve = make_plot("#00ffc8")

        self._alt_plot.setLabel("left", "ALT ft",   color="#6080b0")
        self._spd_plot.setLabel("left", "SPD ft/s", color="#6080b0")

        parent.addWidget(self._alt_plot, stretch=3)
        parent.addWidget(self._spd_plot, stretch=2)

    # ── Public update ──────────────────────────────────────────────────

    def update(self, data: dict):
        alt      = data.get("alt",      0)
        spd      = data.get("spd",      0)
        apogee   = data.get("apogee",   0)
        airbrake = bool(data.get("airbrake", 0))

        self._alt_val.setText(f"{alt:>9,.0f}")
        self._spd_val.setText(f"{abs(spd):>6,.0f}")
        self._apo_val.setText(f"{apogee:>9,.0f}" if apogee else "  —")
        self._set_ab(airbrake)

        self._alt_buf.append(float(alt))
        self._spd_buf.append(float(abs(spd)))

        if _PG:
            self._alt_curve.setData(list(self._alt_buf))
            self._spd_curve.setData(list(self._spd_buf))

        self.set_status("LIVE", ok=True)

    # ── Airbrake banner helper ─────────────────────────────────────────

    def _set_ab(self, deployed: bool):
        if deployed:
            self._ab.setText("▼  AIRBRAKES  DEPLOYED  ▼")
            self._ab.setStyleSheet(
                "background: #1a3300; color: #ccff00; "
                "font-family: 'Consolas', monospace; font-size: 12px; "
                "font-weight: bold; letter-spacing: 2px; border: 1px solid #88cc00;"
            )
        else:
            self._ab.setText("AIRBRAKES  RETRACTED")
            self._ab.setStyleSheet(
                "background: #0a0c1c; color: #5070a0; "
                "font-family: 'Consolas', monospace; font-size: 11px; "
                "letter-spacing: 2px; border: 1px solid #2a3a5a;"
            )
