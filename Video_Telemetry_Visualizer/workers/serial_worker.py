"""
Serial workers
--------------
SerialWorker   — reads telemetry lines from an Arduino over UART.
DemoWorker     — simulates a complete IREC flight (no hardware needed).

Telemetry packet format (either works):

  JSON  (preferred):
    {"alt":1234.5,"spd":123.4,"apogee":3048,"airbrake":0,"lat":32.9901,"lon":-106.9744}

  CSV key:value pairs:
    ALT:1234.5,SPD:123.4,APOGEE:3048,AIRBRAKE:0,LAT:32.9901,LON:-106.9744

All keys are case-insensitive. Units: altitude and apogee in feet, speed in ft/s.

Arduino sketch hint — print one line per loop at ~20 Hz:
  Serial.print("ALT:"); Serial.print(altitude_ft);
  Serial.print(",SPD:"); Serial.print(speed_fps);
  ... etc ...
  Serial.println();
"""

import json
import math
import random

from PySide6.QtCore import QThread, Signal

try:
    import serial
    _SERIAL_OK = True
except ImportError:
    _SERIAL_OK = False


# ---------------------------------------------------------------------------
# Packet parser (shared)
# ---------------------------------------------------------------------------

def _parse(line: str) -> dict | None:
    """
    Parse one telemetry line.  Returns a dict with lower-case keys, or None.
    """
    line = line.strip()
    if not line:
        return None

    # JSON
    if line.startswith("{"):
        try:
            return {k.lower(): v for k, v in json.loads(line).items()}
        except json.JSONDecodeError:
            return None

    # CSV  KEY:VALUE,KEY:VALUE,...
    try:
        data = {}
        for part in line.split(","):
            k, _, v = part.partition(":")
            k = k.strip().lower()
            v = v.strip()
            if k and v:
                data[k] = float(v)
        return data if data else None
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Real hardware reader
# ---------------------------------------------------------------------------

class SerialWorker(QThread):
    """Reads telemetry from an Arduino via pyserial."""

    telemetry_updated = Signal(dict)

    def __init__(self, port: str, baud: int = 115200, parent=None):
        super().__init__(parent)
        self.port = port
        self.baud = baud
        self._running = False

    def run(self):
        self._running = True
        ser = None

        while self._running:
            # Open or reopen port
            if ser is None or not ser.is_open:
                if not _SERIAL_OK:
                    # pyserial not installed — park quietly
                    self.msleep(5000)
                    continue
                if not self.port:
                    self.msleep(2000)
                    continue
                try:
                    ser = serial.Serial(self.port, self.baud, timeout=1.0)
                except Exception:
                    self.msleep(2000)
                    continue

            try:
                raw  = ser.readline().decode("utf-8", errors="replace")
                data = _parse(raw)
                if data:
                    self.telemetry_updated.emit(data)
            except Exception:
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                self.msleep(500)

        if ser:
            try:
                ser.close()
            except Exception:
                pass

    def stop(self):
        self._running = False
        self.wait()


# ---------------------------------------------------------------------------
# Demo / simulation (no hardware)
# ---------------------------------------------------------------------------

class DemoWorker(QThread):
    """
    Simulates a complete IREC flight for testing without hardware.

    Flight profile:
      0 – 3 s   : Motor burn, strong acceleration
      3 – ~20 s : Coast to apogee (~10 000 ft AGL)
      ~20 s     : Apogee, begin descent
      Descent   : Drogue/main deploy (not modelled explicitly),
                  airbrakes deploy during motor/coast phase when
                  speed exceeds threshold.
      Landing   : Brief pause, then next simulated flight.

    Coordinates are near Spaceport America, NM.
    """

    telemetry_updated = Signal(dict)

    # IREC launch site — 2FQ6+G98 Saragosa, TX
    LAUNCH_LAT =  31.0397
    LAUNCH_LON = -103.5385

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def run(self):
        self._running = True
        self._simulate()

    def stop(self):
        self._running = False
        self.wait()

    # ── Simulation loop ────────────────────────────────────────────────

    def _simulate(self):
        DT       = 0.05        # simulation step (s) → 20 Hz output
        STEP_MS  = int(DT * 1000)

        while self._running:
            # Reset state for each flight
            t       = 0.0
            alt     = 0.0      # ft AGL
            vel     = 0.0      # ft/s  (positive = upward)
            lat     = self.LAUNCH_LAT
            lon     = self.LAUNCH_LON
            heading = 5.0      # drift heading (degrees)
            max_alt = 0.0
            airbrake = 0

            # ── Physics constants ──────────────────────────────────
            G               = 32.174   # ft/s²
            THRUST_ACCEL    = 680.0    # ft/s²  (net thrust / mass)  during burn
            BURN_TIME       = 3.0      # s
            DRAG_K          = 6.5e-5   # quadratic drag:  a_drag = DRAG_K * v²
            AB_EXTRA_DRAG   = 2.2e-4   # added drag when airbrakes deployed
            AB_DEPLOY_SPD   = 750.0    # ft/s  — deploy threshold
            AB_RETRACT_SPD  = 350.0    # ft/s  — retract on descent

            while self._running:
                # ── Aerodynamics & kinematics ──────────────────────
                in_burn  = t < BURN_TIME and alt >= 0.0
                thrust   = THRUST_ACCEL if in_burn else 0.0
                ab_drag  = AB_EXTRA_DRAG if airbrake else 0.0
                drag     = (DRAG_K + ab_drag) * vel * abs(vel)   # signed
                accel    = thrust - G - drag

                vel += accel * DT
                alt += vel   * DT

                # ── Ground check ───────────────────────────────────
                if alt < 0.0:
                    alt = 0.0
                    vel = 0.0
                    # Emit landed packet, then pause before next flight
                    self.telemetry_updated.emit(self._packet(
                        t, alt, 0.0, 0.0, 0, lat, lon, accel
                    ))
                    # Wait 4 s at the pad
                    for _ in range(int(4000 / STEP_MS)):
                        if not self._running:
                            return
                        self.msleep(STEP_MS)
                    break   # inner loop — restart outer for next flight

                max_alt = max(max_alt, alt)

                # ── Airbrake logic ─────────────────────────────────
                if vel > AB_DEPLOY_SPD and alt > 100.0:
                    airbrake = 1
                elif vel < AB_RETRACT_SPD or alt < 50.0:
                    airbrake = 0

                # ── Expected apogee (energy method) ───────────────
                if vel > 0:
                    apogee_est = alt + (vel * vel) / (2.0 * G)
                else:
                    apogee_est = max_alt

                # ── GPS drift ──────────────────────────────────────
                ground_speed = max(0.0, vel) * 0.1  # 10 % of vertical = horiz
                lat += math.cos(math.radians(heading)) * ground_speed * DT * 1e-5
                lon += math.sin(math.radians(heading)) * ground_speed * DT * 1e-5

                # ── Emit ───────────────────────────────────────────
                self.telemetry_updated.emit(self._packet(
                    t, alt, vel, apogee_est, airbrake, lat, lon, accel
                ))

                t += DT
                self.msleep(STEP_MS)

    # ── Packet helper ──────────────────────────────────────────────────

    @staticmethod
    def _packet(t, alt, vel, apogee, airbrake, lat, lon, accel) -> dict:
        noise = lambda s: random.gauss(0, s)
        return {
            "t":        round(t, 2),
            "alt":      round(max(0.0, alt  + noise(0.8)), 1),
            "spd":      round(max(0.0, abs(vel) + noise(0.4)), 1),
            "apogee":   round(max(0.0, apogee), 0),
            "airbrake": airbrake,
            "lat":      round(lat, 6),
            "lon":      round(lon, 6),
            "accel_g":  round(accel / 32.174 + noise(0.02), 3),
        }
