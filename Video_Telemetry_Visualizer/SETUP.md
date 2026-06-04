# IREC Ground Station — Setup & Operations Guide

Ground station viewer for the IREC live video challenge.  
Displays two live HDMI video feeds, Arduino telemetry, a satellite map ground track, and a 3D rocket animation.

---

## Requirements

- Python 3.11 or newer
- Windows 10/11 **or** Linux (Ubuntu 22.04+)
- Internet connection for first-time install and offline tile download
- At least two HDMI capture cards (USB or PCIe)
- Arduino connected over USB serial

---

## Installation

### 1. Install Python packages

Open a terminal in the `ground station/` folder and run:

```
pip install -r requirements.txt
```

This installs PySide6, OpenCV, PySerial, pyqtgraph, and NumPy.

> **Linux extra step** — if the map and 3D panels don't appear, install the QtWebEngine system library:
> ```
> sudo apt install libqt6webenginewidgets6   # Debian / Ubuntu
> sudo dnf install qt6-qtwebengine          # Fedora / RHEL
> ```

### 2. Download offline map tiles (do this once, at home with internet)

```
python download_tiles.py
```

This downloads ESRI satellite imagery for a ~10-mile radius around the launch site at zoom levels 10–15 and saves them into `web/tiles/`. It takes 2–5 minutes. Re-running it safely skips tiles that are already cached.

To cover more area (e.g. if the rocket may drift far):  
Open `download_tiles.py` and increase `RADIUS_DEG` from `0.15` to `0.30` (≈ 20 miles) before running.

---

## Hardware Setup

### HDMI Capture Cards

The app uses OpenCV to capture from HDMI capture cards. Each card enumerates as a numbered video device:

| System | Device numbering |
|--------|-----------------|
| Windows | 0, 1, 2 … (DirectShow) |
| Linux | 0, 1, 2 … mapped from `/dev/video0`, `/dev/video1` … |

If you have a built-in laptop webcam, it likely claims index 0, pushing the capture cards to 1 and 2. Test which index is which by running:

```
python -c "import cv2; cap = cv2.VideoCapture(1); print(cap.isOpened()); cap.release()"
```

### Arduino Telemetry

Connect the Arduino via USB. The app reads one telemetry line per loop at whatever baud rate you configure (default 115200).

**Find the serial port:**
- Windows: open Device Manager → Ports (COM & LPT) — look for "Arduino" or "USB Serial Device", e.g. `COM4`
- Linux: usually `/dev/ttyUSB0` or `/dev/ttyACM0`

**Arduino serial format** — print one line per loop, either JSON or CSV:

```cpp
// JSON format (preferred):
Serial.println("{\"alt\":1234.5,\"spd\":123.4,\"apogee\":3048,\"airbrake\":0,\"lat\":31.0397,\"lon\":-103.5385}");

// CSV key:value format also works:
Serial.print("ALT:"); Serial.print(altitude_ft);
Serial.print(",SPD:"); Serial.print(speed_fps);
Serial.print(",APOGEE:"); Serial.print(apogee_ft);
Serial.print(",AIRBRAKE:"); Serial.print(airbrake_deployed ? 1 : 0);
Serial.print(",LAT:"); Serial.print(latitude, 6);
Serial.print(",LON:"); Serial.print(longitude, 6);
Serial.println();
```

**Recognised field names** (case-insensitive):

| Field | Unit | Description |
|-------|------|-------------|
| `alt` | feet | Current altitude AGL |
| `spd` | ft/s | Current speed (magnitude) |
| `apogee` | feet | Predicted apogee |
| `airbrake` | 0 or 1 | Airbrake deployment state |
| `lat` | decimal degrees | GPS latitude |
| `lon` | decimal degrees | GPS longitude (negative = West) |

Any extra fields are silently ignored, so you can add whatever else your flight computer sends.

---

## Running the App

### Demo mode (no hardware needed)

Simulates a complete IREC flight — motor burn, coast, airbrake deployment, apogee, descent, and repeat.  Great for testing at home or verifying the display before launch day.

```
python main.py --demo
```

### Real hardware

```
python main.py --cam-a 0 --cam-b 1 --port COM4 --baud 115200
```

Adjust `--cam-a`, `--cam-b`, and `--port` to match your hardware.

**All command-line options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--demo` | off | Run with simulated flight data |
| `--cam-a INDEX` | 0 | Camera device index for Feed A |
| `--cam-b INDEX` | 1 | Camera device index for Feed B |
| `--port PORT` | (none) | Serial port for Arduino telemetry |
| `--baud RATE` | 115200 | Serial baud rate |

If `--port` is omitted the telemetry panel stays in "WAITING" state but the rest of the app runs normally.

---

## Launch Day Checklist

1. **Power on** both HDMI capture cards and confirm feeds appear in the video panels. If a panel shows "NO SIGNAL", check `--cam-a` / `--cam-b` indices.
2. **Connect Arduino** and confirm the TELEMETRY panel shows "LIVE" status and numbers are updating.
3. **Check the map** — the satellite view should be centred on the launch pad. The marker drifts with GPS once telemetry is live.
4. **Confirm offline tiles** — the map should load instantly even without internet. If tiles are missing for a zoom level, those areas show grey until/unless internet is available.
5. **Verify airbrake animation** — in the ROCKET 3D panel the airbrake status reads "RETRACTED". When the Arduino reports `airbrake:1` the four orange panels will deploy.

---

## Troubleshooting

**Map panel is black / blank**  
The map needs `LocalContentCanAccessRemoteUrls` to be set — this is done automatically in `map_widget.py`. If it's still blank, check that PySide6's QtWebEngine is installed (see Linux note above).

**"NO SIGNAL" on a camera that's plugged in**  
Run the index test above to find the correct `--cam-a` / `--cam-b` number. Also check that the capture card's driver is installed (Windows may need a driver download from the card manufacturer).

**Telemetry panel stays at "WAITING"**  
- Confirm the serial port name is correct and no other app (Arduino IDE Serial Monitor, etc.) has it open.
- Check the baud rate matches what the Arduino is configured to print at.
- Verify the line format matches one of the two formats above.

**Map shows wrong location**  
The map follows live telemetry GPS coordinates. If in demo mode it should start at the Saragosa TX site. In real-hardware mode the map follows the Arduino's reported GPS position.

**Offline tiles show grey for some zoom levels**  
Re-run `python download_tiles.py` — it will fill in any gaps. Increase `RADIUS_DEG` if the grey area is outside the original download radius.

---

## File Layout

```
ground station/
├── main.py                  ← entry point — run this
├── download_tiles.py        ← run once before competition
├── requirements.txt
├── config.json              ← default settings reference
├── SETUP.md                 ← this file
├── DEVELOPERS.md            ← programmer's guide
├── workers/
│   ├── video_worker.py      ← OpenCV capture thread
│   └── serial_worker.py     ← Arduino UART + demo simulator
├── widgets/
│   ├── panel_base.py        ← shared dark panel chrome
│   ├── video_widget.py      ← video frame display
│   ├── telemetry_widget.py  ← HUD gauges and plots
│   ├── map_widget.py        ← Leaflet map (Python side)
│   └── rocket_widget.py     ← Three.js rocket (Python side)
└── web/
    ├── map.html             ← Leaflet map page
    ├── rocket.html          ← Three.js rocket page
    └── tiles/               ← offline tile cache (after download)
```
