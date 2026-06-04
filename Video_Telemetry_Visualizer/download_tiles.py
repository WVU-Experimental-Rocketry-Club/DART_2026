#!/usr/bin/env python3
"""
download_tiles.py — run this ONCE before the competition (with internet).

Downloads ESRI satellite tiles for the launch area and saves them to
web/tiles/{z}/{y}/{x}.jpg so the ground station works fully offline.

Usage:
    python download_tiles.py

Tweak LAUNCH_LAT / LAUNCH_LON / ZOOM_LEVELS / RADIUS_DEG below if needed.
"""

import math
import time
import os
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Configuration ────────────────────────────────────────────────────────────

LAUNCH_LAT  =  31.0397
LAUNCH_LON  = -103.5385

# Bounding box padding around the launch site (degrees).
# 0.15° ≈ 10 miles — enough to cover most flight tracks + landing zone.
# Increase to 0.30 if your rocket drifts far.
RADIUS_DEG  = 0.15

# Zoom levels to cache.
# 10-11 : overview / coast-to-coast context
# 12-13 : regional, good for tracking a drifting rocket
# 14-15 : close-up launch pad detail
ZOOM_LEVELS = range(10, 16)   # 10 through 15 inclusive

# Tile source — ESRI World Imagery (same as the live map)
TILE_URL    = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

# Output folder (relative to this script)
OUT_DIR     = Path(__file__).parent / "web" / "tiles"

# Download workers (be polite to the tile server)
WORKERS     = 4
DELAY_S     = 0.05   # seconds between requests per worker

# ── Tile math ─────────────────────────────────────────────────────────────────

def _tile_x(lon: float, z: int) -> int:
    return int((lon + 180.0) / 360.0 * (1 << z))

def _tile_y(lat: float, z: int) -> int:
    lr = math.radians(lat)
    return int((1.0 - math.log(math.tan(lr) + 1.0 / math.cos(lr)) / math.pi) / 2.0 * (1 << z))

def tiles_for_bbox(lat_min, lat_max, lon_min, lon_max, z):
    """Return list of (z, x, y) tuples covering the bounding box at zoom z."""
    x0 = _tile_x(lon_min, z);  x1 = _tile_x(lon_max, z)
    y0 = _tile_y(lat_max, z);  y1 = _tile_y(lat_min, z)   # y is flipped
    return [(z, x, y)
            for x in range(min(x0,x1), max(x0,x1)+1)
            for y in range(min(y0,y1), max(y0,y1)+1)]

# ── Downloader ────────────────────────────────────────────────────────────────

def download_tile(z: int, x: int, y: int) -> str:
    """Download one tile; skip if already on disk.  Returns status string."""
    dest = OUT_DIR / str(z) / str(y) / f"{x}.jpg"
    if dest.exists():
        return f"skip  {z}/{y}/{x}"

    dest.parent.mkdir(parents=True, exist_ok=True)
    url = TILE_URL.format(z=z, y=y, x=x)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "IREC-GroundStation/1.0 (offline tile cache)"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            dest.write_bytes(resp.read())
        time.sleep(DELAY_S)
        return f"ok    {z}/{y}/{x}"
    except Exception as e:
        return f"ERROR {z}/{y}/{x}: {e}"

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    lat_min = LAUNCH_LAT - RADIUS_DEG
    lat_max = LAUNCH_LAT + RADIUS_DEG
    lon_min = LAUNCH_LON - RADIUS_DEG
    lon_max = LAUNCH_LON + RADIUS_DEG

    all_tiles = []
    for z in ZOOM_LEVELS:
        batch = tiles_for_bbox(lat_min, lat_max, lon_min, lon_max, z)
        print(f"  zoom {z:2d} → {len(batch):>5} tiles")
        all_tiles.extend(batch)

    print(f"\nTotal tiles to download: {len(all_tiles)}  (skipping any already cached)")
    print(f"Output folder: {OUT_DIR}\n")

    done = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(download_tile, z, x, y): (z, x, y)
                for z, x, y in all_tiles}
        for fut in as_completed(futs):
            result = fut.result()
            done += 1
            if result.startswith("ERROR"):
                errors += 1
                print(result)
            elif done % 50 == 0 or done == len(all_tiles):
                pct = done / len(all_tiles) * 100
                print(f"  {pct:5.1f}%  ({done}/{len(all_tiles)})  errors={errors}")

    print(f"\nDone.  {done - errors} tiles saved, {errors} errors.")
    if errors:
        print("Re-run to retry failed tiles.")

if __name__ == "__main__":
    main()
