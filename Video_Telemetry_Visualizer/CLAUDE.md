# IREC Ground Station — Claude Code Context

Ground station viewer for the IREC 2026 live video challenge.
Rocket: **Mothman Avenged**, Saragosa TX launch site (31.0397°N, 103.5385°W).

## How to run

```bash
pip install -r requirements.txt
python main.py --demo          # simulated flight, no hardware
python main.py --cam-a 0 --cam-b 1 --port COM4 --baud 115200
```

See `SETUP.md` for full hardware setup. See `DEVELOPERS.md` for the programmer's guide.

---

## File map

```
ground station/
├── main.py                   entry point, QMainWindow, dark theme, tile server
├── download_tiles.py         run once at home to cache ESRI tiles offline
├── requirements.txt          pyside6, pyserial, opencv-python, pyqtgraph, numpy
├── config.json               launch site defaults reference (not loaded at runtime)
├── workers/
│   ├── video_worker.py       VideoWorker(QThread) — OpenCV HDMI capture
│   └── serial_worker.py      SerialWorker(QThread) + DemoWorker(QThread)
├── widgets/
│   ├── panel_base.py         PanelWidget base — dark header, status dot
│   ├── video_widget.py       VideoWidget(PanelWidget) — scaled QLabel frame display
│   ├── telemetry_widget.py   TelemetryWidget — big readouts + pyqtgraph plots
│   ├── map_widget.py         MapWidget — Python side of Leaflet QWebEngineView
│   └── rocket_widget.py      RocketWidget — Python side of Three.js QWebEngineView
└── web/
    ├── map.html              Leaflet.js satellite map + ground track
    └── rocket.html           Three.js r128 3D rocket + airbrake animation
```

---

## Architecture

```
Arduino (UART)              HDMI Capture Cards
     │                           │        │
     ▼                           ▼        ▼
SerialWorker / DemoWorker   VideoWorker A  VideoWorker B
  telemetry_updated signal    frame_ready signal
     │                           │
     ▼                           ▼
GroundStation._on_telemetry   VideoWidget.on_frame (QLabel pixmap)
     │
     ├──► TelemetryWidget.update()     — pyqtgraph plots + readouts
     ├──► MapWidget.update_position()  — QWebChannel → Leaflet JS
     └──► RocketWidget.update_state()  — QWebChannel → Three.js
```

Data flows one way: hardware workers emit Qt signals; the main window fans them out to
display widgets. No global state — each widget is self-contained.

The map and rocket panels each embed a `QWebEngineView` running a local HTML/JS page.
Python pushes JSON strings to JavaScript via `QWebChannel`.

---

## Layout

- **Top 60%**: `QSplitter(Horizontal)` — VideoWidget A | VideoWidget B (50/50)
- **Bottom 40%**: `QSplitter(Horizontal)` — TelemetryWidget | MapWidget | RocketWidget (33/33/33)
- Outer `QSplitter(Vertical)` with sizes [580, 380]

---

## Python ↔ JavaScript bridge pattern

Both `MapWidget` and `RocketWidget` use this pattern:

```python
# widgets/map_widget.py (and rocket_widget.py)
class _Bridge(QObject):
    map_update = Signal(str)       # Python → JS: emit JSON string

    @Slot(str)
    def js_ready(self, msg):       # JS → Python: called when page loads
        pass

# In widget __init__:
self._chan = QWebChannel()
self._bridge = _Bridge()
self._chan.registerObject("bridge", self._bridge)
self._web.page().setWebChannel(self._chan)

# REQUIRED — without this, file:// pages can't load CDN scripts (Leaflet, Three.js):
from PySide6.QtWebEngineCore import QWebEngineSettings
settings = self._web.page().settings()
settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
```

```javascript
// web/map.html (and rocket.html)
new QWebChannel(qt.webChannelTransport, function(channel) {
    var bridge = channel.objects.bridge;
    bridge.map_update.connect(function(jsonStr) {
        var d = JSON.parse(jsonStr);
        // use d ...
    });
    bridge.js_ready("ready");
});
```

---

## Telemetry data dict keys

All widgets receive the same raw dict from `_on_telemetry`:

| Key | Type | Unit | Source |
|-----|------|------|--------|
| `alt` | float | ft AGL | altimeter |
| `spd` | float | ft/s | IMU |
| `apogee` | float | ft | flight computer prediction |
| `airbrake` | int | 0 or 1 | airbrake controller |
| `lat` | float | decimal degrees | GPS |
| `lon` | float | decimal degrees | GPS (negative = West) |

Extra fields from the Arduino are silently passed through — no Python changes needed to
add new fields. See `DEVELOPERS.md` § "Adding a new telemetry field" to wire them up in
the display widgets.

---

## Arduino serial format (two accepted formats)

**JSON** (preferred):
```cpp
StaticJsonDocument<256> doc;
doc["alt"] = altFt;  doc["spd"] = spdFps;
doc["apogee"] = apogeeFt;  doc["airbrake"] = deployed ? 1 : 0;
doc["lat"] = gps.latitude();  doc["lon"] = gps.longitude();
serializeJson(doc, Serial);  Serial.println();
```

**CSV key:value**:
```
ALT:1234.5,SPD:123.4,APOGEE:3048,AIRBRAKE:0,LAT:31.0397,LON:-103.5385
```

---

## Offline map tiles

`download_tiles.py` caches ESRI satellite tiles for ±0.15° around the launch site
(zoom 10–15) into `web/tiles/{z}/{y}/{x}.jpg`.

`main.py` starts a local HTTP server on port 8765 serving `web/` if the tiles folder
exists. `map.html` loads ESRI CDN as the base layer and the local server as an overlay.

**Tile layer architecture in map.html** (important — do not revert):
```javascript
// Layer 1 — ESRI satellite (base, always present, fails silently offline)
L.tileLayer(ESRI_TILES, { ... }).addTo(map);
// Layer 2 — local cache (transparent tile on miss → ESRI shows through)
L.tileLayer(LOCAL_TILES, { maxZoom: 15 }).addTo(map);
// Layer 3 — ESRI labels overlay
L.tileLayer(ESRI_LABELS, { opacity: 0.65 }).addTo(map);
```

---

## Rocket model dimensions (Mothman Avenged)

Baked into `web/rocket.html` as constants at the top of the `<script>` block.
Scale factor `S = 0.057787 units/inch` keeps body radius = 0.18 model units.

| Dimension | Real | Constant |
|-----------|------|----------|
| Total length | 165" | `BODY_LEN + NOSE_LEN + NOZZLE_LEN` |
| Body diameter | 6.23" OD | `R = 0.18` |
| Nose cone (Von Kármán) | 36.5" | `NOSE_LEN` |
| Body tube | 124" | `BODY_LEN` |
| Nozzle stub | 4.5" | `NOZZLE_LEN` |
| Fin root / tip / span / LE sweep | 15" / 3" / 7.75" / 10" | `FIN_ROOT / FIN_TIP / FIN_SPAN / FIN_SWEEP` |
| Airbrake panels (×4, 3"×3") | at 100" from nose | `AB_SIZE / AB_Y` |

Fins are 4× swept, `ExtrudeGeometry` with depth 0.025. Nose is `LatheGeometry` with
Von Kármán profile. No boat tail.

---

## Bugs fixed — do not re-introduce

### 1. `TypeError: VideoWidget.set_status() got unexpected keyword argument 'ok'`
`VideoWidget` overrides `set_status(self, status: str)` as a `@Slot(str)` (single string,
no kwargs). Calling `self.set_status("WAITING", ok=False)` from `__init__` hit the
override instead of the base class.
**Fix**: use `super().set_status("WAITING", ok=False)` in `VideoWidget.__init__`.

### 2. Map and rocket panels rendering black
Qt security blocks `file://` pages from loading remote CDN URLs by default.
**Fix**: set `LocalContentCanAccessRemoteUrls = True` on `self._web.page().settings()` in
both `map_widget.py` and `rocket_widget.py`. Already in place — do not remove.

### 3. Map showing wrong location (Spaceport America instead of Saragosa TX)
`DemoWorker` had `LAUNCH_LAT = 32.9901, LAUNCH_LON = -106.9744` (Spaceport America).
**Fix**: `LAUNCH_LAT = 31.0397, LAUNCH_LON = -103.5385` in `serial_worker.py`.
Also set in `map.html` and `download_tiles.py`.

### 4. Leaflet `errorTileUrl` does not substitute `{z}/{y}/{x}`
`errorTileUrl` is a **literal string** — Leaflet does not template-substitute it.
Using the ESRI tile template URL as `errorTileUrl` meant every failed local tile
requested a broken literal URL, silently showing nothing (only the labels layer).
**Fix**: two-layer stack (ESRI base + local overlay), no `errorTileUrl` on the local layer.

### 5. Map initialising at wrong zoom level
Leaflet sometimes measures a zero-size container in a QWebEngineView before Qt finishes
laying out the splitter. The map rendered at an incorrect zoom.
**Fix**: in the `QWebChannel` callback in `map.html`, call
`map.invalidateSize()` and `map.setView([LAUNCH_LAT, LAUNCH_LON], 14, {animate:false})`
before sending `js_ready`. Already in place.

### 6. Airbrake panels vertical / hinging wrong direction
`BoxGeometry(AB_SIZE, AB_SIZE, 0.040)` made a tall vertical slab.
Retracted rotation `+MAX_PIVOT` folded panels toward the nose; they deployed by
rotating downward instead of upward.
**Fix**:
- Geometry: `BoxGeometry(AB_SIZE, 0.040, AB_SIZE)` — thin in Y, horizontal when deployed
- Initial rotation: `pivotGroup.rotation.z = -Math.PI * 0.48` — folds aft
- Animation: `pivotAngle = -(1.0 - deployLevel) * MAX_PIVOT` — sweeps upward on deploy

---

## Extending the project

See `DEVELOPERS.md` for detailed guides on:
- Wiring in a new Arduino telemetry field
- Modifying 3D rocket geometry (all dimensions are constants, not magic numbers)
- Adding a new display panel widget
- Map customisation (zoom, track colour, landing zone overlay)
- Full QWebChannel bridge boilerplate
- Video worker colour format alternatives (YUV capture cards)
