"""
RocketWidget
------------
Embeds a Three.js 3D rocket scene in a QWebEngineView.
Telemetry data is pushed to the JS scene via a QWebChannel bridge.

The JS scene (web/rocket.html) handles:
  - Rocket geometry with 4 swept fins
  - 4 airbrake panels that animate open/closed via pivot rotation
  - Engine plume effect during motor burn
  - Starfield background
  - OrbitControls (drag to rotate / scroll to zoom)
"""

import json
from pathlib import Path

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Signal, Slot, QUrl

from .panel_base import PanelWidget


class _Bridge(QObject):
    """Registered as 'bridge' inside the rocket web page."""

    rocket_update = Signal(str)   # Python → JS

    @Slot(str)
    def js_ready(self, msg: str):
        pass


class RocketWidget(PanelWidget):
    def __init__(self, parent=None):
        super().__init__("ROCKET  3D", parent)

        self._web    = QWebEngineView()
        self._chan   = QWebChannel()
        self._bridge = _Bridge()

        self._chan.registerObject("bridge", self._bridge)
        self._web.page().setWebChannel(self._chan)

        # Allow local file:// pages to load CDN scripts (Three.js, etc.)
        settings = self._web.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        html = Path(__file__).parent.parent / "web" / "rocket.html"
        self._web.setUrl(QUrl.fromLocalFile(str(html.resolve())))
        self._web.loadFinished.connect(self._on_load)

        self.content_layout.addWidget(self._web)
        self.set_status("LOADING", ok=False)

    def _on_load(self, ok: bool):
        self.set_status("LIVE" if ok else "ERROR", ok=ok)

    def update_state(self, data: dict):
        payload = json.dumps({
            "airbrake": int(data.get("airbrake", 0)),
            "alt":      float(data.get("alt",      0)),
            "spd":      float(data.get("spd",      0)),
            "t":        float(data.get("t",         0)),
        })
        self._bridge.rocket_update.emit(payload)
