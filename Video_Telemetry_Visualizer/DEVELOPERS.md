# IREC Ground Station — Programmer's Guide

This document explains how the codebase is structured and how to extend it for the real rocket: connecting live telemetry, reshaping the 3D model, adding new data fields, and modifying the UI.

---

## Architecture Overview

```
Arduino (UART)                  HDMI Capture Cards
     │                               │        │
     ▼                               ▼        ▼
SerialWorker (QThread)       VideoWorker A   VideoWorker B
     │ telemetry_updated             │ frame_ready
     ▼                               ▼
GroundStation._on_telemetry     VideoWidget (QLabel)
     │
     ├──► TelemetryWidget.update()    → pyqtgraph plots + readouts
     ├──► MapWidget.update_position() → QWebChannel → Leaflet JS
     └──► RocketWidget.update_state() → QWebChannel → Three.js
```

Data flows in one direction: hardware workers emit Qt signals, the main window fans them out to display widgets. There is no global state — each widget is self-contained.

The map and rocket 3D panels each embed a `QWebEngineView` running a local HTML/JS page. Python pushes JSON strings to JavaScript via `QWebChannel`. This means the complex rendering logic (Leaflet, Three.js) lives in the HTML files and is easy to edit without touching any Python.

---

## Connecting Real Arduino Telemetry

### 1. Serial port and baud rate

Pass `--port` and `--baud` on the command line:

```
python main.py --port COM4 --baud 115200
```

On Linux the port is typically `/dev/ttyUSB0` or `/dev/ttyACM0`.

### 2. Wire up the Arduino sketch

The parser in `workers/serial_worker.py` (`_parse()` function) accepts two formats on every `Serial.println()` call.

**JSON** (preferred — easier to add fields later):
```cpp
void loop() {
    StaticJsonDocument<256> doc;
    doc["alt"]      = altimeter.getAltitudeFt();
    doc["spd"]      = imu.getSpeedFps();
    doc["apogee"]   = flightComputer.predictedApogeeFt();
    doc["airbrake"] = airbrakeDeployed ? 1 : 0;
    doc["lat"]      = gps.latitude();
    doc["lon"]      = gps.longitude();
    serializeJson(doc, Serial);
    Serial.println();
    delay(50);  // 20 Hz
}
```

**CSV** (no library needed):
```cpp
void loop() {
    Serial.print("ALT:");    Serial.print(alt_ft, 1);
    Serial.print(",SPD:");   Serial.print(spd_fps, 1);
    Serial.print(",APOGEE:");Serial.print(apogee_ft, 0);
    Serial.print(",AIRBRAKE:"); Serial.print(airbrakeDeployed ? 1 : 0);
    Serial.print(",LAT:");   Serial.print(lat, 6);
    Serial.print(",LON:");   Serial.print(lon, 6);
    Serial.println();
    delay(50);
}
```

### 3. Adding a new telemetry field

Say you want to add acceleration in G's.

**Arduino** — add `"accel_g"` to the JSON or CSV packet.

**Python fan-out** (`main.py` → `_on_telemetry`): no change needed — the raw `data` dict is passed to every widget unchanged.

**Display it** — pick one of:

- *New number in TelemetryWidget*: open `widgets/telemetry_widget.py`, add a `_big()` label in `__init__` and update it in the `update()` method, same pattern as `_alt_val` / `_spd_val`.
- *Pass it to the 3D rocket*: open `widgets/rocket_widget.py`, add the field to the `json.dumps({...})` call in `update_state()`, then read it in `rocket.html`'s `applyTelemetry()` function.
- *Show it on the map*: add it to the payload in `map_widget.py`'s `update_position()` and read `d.my_field` in `map.html`.

---

## Modifying the 3D Rocket Model

All 3D geometry lives in `web/rocket.html`. Open it in any editor — it's plain JavaScript using Three.js r128. You do **not** need to restart the Python app to iterate; just reload the web view (or restart the app) after saving the file.

### Coordinate system

The rocket is oriented vertically, nose pointing up (+Y). The origin is at the mid-body tube. Key Y positions (derived from real measurements):

| Part | Y position (model units) | Real position |
|------|--------------------------|---------------|
| Nose tip | +5.69 | 0" from nose |
| Body top / nose shoulder | +3.58 | 36.5" from nose |
| Colour band | +2.22 | 60" from nose |
| Body centre | 0 | 98.25" from nose |
| Airbrakes | −0.09 | 100" from nose |
| Body bottom | −3.58 | 160.5" from nose |
| Nozzle exit | −3.84 | 165" from nose |

Body radius is **0.18 units** (= 3.115" × 0.057787 units/inch).

### Changing dimensions

All geometry is driven by constants at the top of the `<script>` block in `rocket.html`. Edit only these — everything else derives from them automatically:

```javascript
var S = 1.0 / (3.115 / 0.18);  // units per inch (change 3.115 to your real body radius in inches)
var R = 3.115 * S;              // body outer radius

var BODY_LEN   = 124.0 * S;    // main airframe tube (total − nose − nozzle)
var NOSE_LEN   =  36.5 * S;    // nose cone length (tip to shoulder)
var NOZZLE_LEN =   4.5 * S;    // nozzle stub below body

var FIN_ROOT  = 15.0 * S;      // fin root chord
var FIN_TIP   =  3.0 * S;      // fin tip chord
var FIN_SPAN  =  7.75 * S;     // fin semi-span (outward from body surface)
var FIN_SWEEP = 10.0 * S;      // leading-edge sweep (root LE → tip LE, measured aft)

var AB_SIZE = 3.0 * S;         // airbrake panel side length (panels are square)
var AB_Y    = BODY_TOP - (100.0 * S - NOSE_LEN);  // 100" from nose tip
```

> **BODY_LEN** = total_length − nose_length − nozzle_length. Currently 165 − 36.5 − 4.5 = 124".

### Nose cone shape

The nose is a Von Kármán LatheGeometry profile — already the correct shape. The profile formula is baked into `rocket.html`. If you want a different nose shape, replace the `pts` calculation in the `(function(){ … })()` nose block:

```javascript
// Tangent ogive (alternative to Von Kármán):
for (var i = 0; i <= N; i++) {
    var t = i / N;   // 0 = tip, 1 = base
    var r = R * Math.sqrt(1 - Math.pow(1 - t, 2));
    pts.push(new THREE.Vector2(r, NOSE_LEN * (1.0 - t)));
}

// Simple cone:
for (var i = 0; i <= N; i++) {
    var t = i / N;
    pts.push(new THREE.Vector2(R * t, NOSE_LEN * (1.0 - t)));
}
```

### Moving / resizing the airbrake panels

Find the `AIRBRAKES` construction loop (~line 210). The key values to tweak:

```javascript
var abAngle = (i / 4) * Math.PI * 2 + Math.PI / 4;  // angular position (offset from fins)

// Housing position — sits flush on body surface
Math.cos(abAngle) * 0.185,  // radial offset (match body radius + tiny gap)
0.30,                        // Y position along rocket body

// Panel geometry
new THREE.BoxGeometry(
    0.32,   // radial depth when deployed — make bigger for larger flaps
    0.30,   // height along rocket axis  — match your real flap chord
    0.042   // thickness
)
panelMesh.position.x = 0.16;  // half of radial depth (centres the panel on the hinge)
```

The deployment animation is driven by `deployLevel` (0 = retracted, 1 = deployed). The max pivot angle is:

```javascript
var MAX_PIVOT = Math.PI * 0.48;  // ~86 degrees — adjust for your flap travel
```

### Adding fins of a different shape

The current fins use `ExtrudeGeometry` with a hand-drawn `THREE.Shape`. To change the planform, edit the shape coordinates in the fin loop:

```javascript
var shape = new THREE.Shape();
shape.moveTo(0.0,  0.00);   // root aft corner (at body)
shape.lineTo(0.0,  0.55);   // root leading edge
shape.lineTo(0.40, 0.28);   // tip leading edge (controls sweep)
shape.lineTo(0.44, 0.00);   // tip aft corner
shape.closePath();
```

X = distance from body surface outward (fin span).  
Y = position along rocket body (upward).  
Larger X = wider span. Larger Y range = longer root chord.

### Changing rocket colours

```javascript
var MAT_BODY  = new THREE.MeshPhongMaterial({ color: 0xe2e2e2, ... }); // body tube colour
var MAT_NOSE  = new THREE.MeshPhongMaterial({ color: 0xcc2200, ... }); // nose + fins colour
var MAT_BAND  = new THREE.MeshPhongMaterial({ color: 0x0044cc, ... }); // colour band
```

Colours are standard hex RGB: `0xRRGGBB`. Change these to match your team's livery.

---

## Modifying the Map

The map is Leaflet.js in `web/map.html`. All the map logic is in the `<script>` block at the bottom.

### Change the default centre / zoom

```javascript
var LAUNCH_LAT =  31.0397;
var LAUNCH_LON = -103.5385;
// ...
}).setView([LAUNCH_LAT, LAUNCH_LON], 14);  // change 14 to adjust default zoom
```

### Change the track line colour or thickness

```javascript
var track = L.polyline([], {
    color: "#ff9500",   // orange — change to any CSS colour
    weight: 3,          // pixels wide
    opacity: 0.95,
}).addTo(map);
```

### Show predicted landing zone

In `map.html`'s `updatePosition()` function, you have access to `alt` (altitude). You could add a circle overlay for the predicted landing zone when the rocket is descending:

```javascript
var landingCircle = L.circle([LAUNCH_LAT, LAUNCH_LON], {
    radius: 500,   // metres
    color: "#ffcc00", fillOpacity: 0.1,
}).addTo(map);

function updatePosition(lat, lon, alt) {
    // ... existing code ...
    if (alt < 500 && alt > 0) {
        landingCircle.setLatLng([lat, lon]);
    }
}
```

### Add a second map layer (topo, roads, etc.)

```javascript
// Add before the existing L.tileLayer call and wrap both in L.control.layers()
var satellite = L.tileLayer(LOCAL_TILES, { ... });
var topo = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenTopoMap",
});
L.control.layers({ "Satellite": satellite, "Topo": topo }).addTo(map);
satellite.addTo(map);
```

---

## Adding a New Display Panel

Each panel is a `PanelWidget` subclass. To add a new panel (e.g. an acceleration meter):

### 1. Create the widget file

Copy `widgets/telemetry_widget.py` as a starting point. Strip it down to what you need:

```python
from .panel_base import PanelWidget
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

class AccelWidget(PanelWidget):
    def __init__(self, parent=None):
        super().__init__("ACCELERATION", parent)
        self._lbl = QLabel("0.0 G")
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setStyleSheet("color: #00e5ff; font-size: 32px; font-weight: bold;")
        self.content_layout.addWidget(self._lbl)

    def update(self, data: dict):
        g = data.get("accel_g", 0.0)
        self._lbl.setText(f"{g:.2f} G")
        self.set_status("LIVE", ok=True)
```

### 2. Add it to the layout in main.py

```python
from widgets.accel_widget import AccelWidget   # add to imports

# In _build_ui(), add to the bottom splitter:
self.accel = AccelWidget()
bot_split.addWidget(self.accel)
bot_split.setSizes([1, 1, 1, 1])   # now 4 equal columns

# In _on_telemetry():
self.accel.update(data)
```

---

## Adjusting the Simulated Demo Flight

`DemoWorker` in `workers/serial_worker.py` simulates the flight physics. Tweak these constants at the top of the `_simulate()` method to match your rocket's expected performance:

```python
THRUST_ACCEL    = 680.0    # ft/s²  net thrust acceleration during burn
BURN_TIME       = 3.0      # seconds
DRAG_K          = 6.5e-5   # quadratic drag constant (tune for target apogee)
AB_EXTRA_DRAG   = 2.2e-4   # added drag when airbrakes are deployed
AB_DEPLOY_SPD   = 750.0    # ft/s  — deploy airbrakes above this speed
AB_RETRACT_SPD  = 350.0    # ft/s  — retract on descent below this speed
```

To hit a specific target apogee, adjust `DRAG_K`: larger value = more drag = lower apogee.  
A rough starting point: run demo mode, note the peak altitude shown in the telemetry panel, then scale `DRAG_K` proportionally.

---

## Python ↔ JavaScript Bridge Reference

Both `MapWidget` and `RocketWidget` use `QWebChannel` to send data from Python to the browser. Here's the pattern if you want to add your own bridged widget:

**Python side** (`widgets/my_widget.py`):
```python
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Signal, Slot, QUrl
from .panel_base import PanelWidget

class _Bridge(QObject):
    data_ready = Signal(str)   # Python → JS: emit a JSON string

    @Slot(str)
    def js_ready(self, msg):   # JS → Python: called when page loads
        pass

class MyWidget(PanelWidget):
    def __init__(self, parent=None):
        super().__init__("MY PANEL", parent)
        self._web  = QWebEngineView()
        self._chan = QWebChannel()
        self._bridge = _Bridge()
        self._chan.registerObject("bridge", self._bridge)
        self._web.page().setWebChannel(self._chan)
        settings = self._web.page().settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self._web.setUrl(QUrl.fromLocalFile(...))
        self.content_layout.addWidget(self._web)

    def push_data(self, data: dict):
        import json
        self._bridge.data_ready.emit(json.dumps(data))
```

**JavaScript side** (`web/my_page.html`):
```html
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
if (typeof QWebChannel !== "undefined") {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        var bridge = channel.objects.bridge;

        // Receive data from Python
        bridge.data_ready.connect(function(jsonStr) {
            var data = JSON.parse(jsonStr);
            // do something with data
        });

        // Tell Python the page is ready
        bridge.js_ready("ready");
    });
}
</script>
```

The signal `data_ready` on the Python `_Bridge` object becomes a property of `bridge` in JavaScript that you can `.connect()` a callback to. Qt handles the serialisation and thread-safety automatically.

---

## Video Worker Notes

`workers/video_worker.py` uses OpenCV. The relevant constants are at the top of the class:

```python
TARGET_FPS = 30   # request this framerate from the driver
```

Inside `_open()`, the resolution request can be changed:
```python
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)   # request 1080p
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
```

The driver will silently fall back to the nearest mode it supports. If your capture card only does 720p, OpenCV will capture at 720p regardless of what you request here — the video will still display correctly.

If a camera produces frames with an unusual colour format (some HDMI cards output YUV), change the cvtColor call:
```python
# Currently:
rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
# If you see garbled colour, try:
rgb = cv2.cvtColor(frame, cv2.COLOR_YUV2RGB_YUYV)
# or:
rgb = cv2.cvtColor(frame, cv2.COLOR_YUV2RGB_NV12)
```
