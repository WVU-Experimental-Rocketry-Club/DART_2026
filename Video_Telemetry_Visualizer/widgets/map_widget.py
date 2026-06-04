"""
MapWidget
---------
Embeds a Leaflet.js map in a QWebEngineView and pushes live GPS
coordinates to it via a QWebChannel bridge.

The map page (web/map.html) handles all rendering.
This file only manages the Python ↔ JS bridge and widget plumbing.
"""

import json
from pathlib import Path

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Signal, Slot, QUrl

from .panel_base import PanelWidget


class _Bridge(QObject):
    """Registered as 'bridge' inside the web page."""

    # Emitted from Python → received by JS
    map_update = Signal(str)

    @Slot(str)
    def js_ready(self, msg: str):
        """Called by JS when the page finishes setting up the channel."""
        pass


class MapWidget(PanelWidget):
    def __init__(self, parent=None):
        super().__init__("MAP  /  GROUND TRACK", parent)

        self._web    = QWebEngineView()
        self._chan   = QWebChannel()
        self._bridge = _Bridge()

        self._chan.registerObject("bridge", self._bridge)
        self._web.page().setWebChannel(self._chan)

        # Allow local file:// pages to load CDN scripts (Leaflet, etc.)
        settings = self._web.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        html = Path(__file__).parent.parent / "web" / "map.html"
        self._web.setUrl(QUrl.fromLocalFile(str(html.resolve())))
        self._web.loadFinished.connect(self._on_load)

        self.content_layout.addWidget(self._web)
        self.set_status("LOADING", ok=False)

    def _on_load(self, ok: bool):
        self.set_status("LIVE" if ok else "ERROR", ok=ok)

    def update_position(self, data: dict):
        lat = data.get("lat")
        lon = data.get("lon")
        if lat is None or lon is None:
            return
        payload = json.dumps({
            "lat": lat,
            "lon": lon,
            "alt": data.get("alt", 0),
        })
        self._bridge.map_update.emit(payload)
