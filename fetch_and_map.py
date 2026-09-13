#!/usr/bin/env python3
"""Fetch the latest PM2.5 readings for Southeast Asia from WAQI, interpolate
them onto a grid, and render a pannable/zoomable HTML map of the result.

Usage:
    WAQI_TOKEN=xxxx python fetch_and_map.py
    python fetch_and_map.py --token xxxx --output output/map.html
    python fetch_and_map.py --offline sample_data/sample_stations.json
"""
import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO

import folium
import numpy as np
import requests
from PIL import Image

# Southeast Asia bounding box: Myanmar, Thailand, Laos, Cambodia, Vietnam,
# Malaysia, Singapore, Indonesia, Philippines, Brunei, Timor-Leste.
SEA_BOUNDS = {"south": -11.0, "north": 29.0, "west": 92.0, "east": 141.5}

# US EPA PM2.5 AQI breakpoints: (value, RGBA color). Values between two
# breakpoints are linearly interpolated in color.
AQI_BREAKPOINTS = [
    (0, (0, 228, 0, 255)),      # Good - green
    (50, (255, 255, 0, 255)),   # Moderate - yellow
    (100, (255, 126, 0, 255)),  # Unhealthy for Sensitive Groups - orange
    (150, (255, 0, 0, 255)),    # Unhealthy - red
    (200, (143, 63, 151, 255)), # Very Unhealthy - purple
    (300, (126, 0, 35, 255)),   # Hazardous - maroon
    (500, (126, 0, 35, 255)),   # clamp
]

BAND_LABELS = [
    (0, 50, "Good", "#00e400"),
    (51, 100, "Moderate", "#ffff00"),
    (101, 150, "Unhealthy for Sensitive Groups", "#ff7e00"),
    (151, 200, "Unhealthy", "#ff0000"),
    (201, 300, "Very Unhealthy", "#8f3f97"),
    (301, 500, "Hazardous", "#7e0023"),
]

WAQI_BOUNDS_URL = "https://api.waqi.info/map/bounds/"
WAQI_FEED_URL = "https://api.waqi.info/feed/@{uid}/"


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_stations(token, bounds=SEA_BOUNDS, max_workers=10, timeout=15):
    """Query WAQI for stations in the bounding box, then pull each station's
    PM2.5 reading. Returns a list of dicts: uid, name, lat, lon, pm25, time."""
    latlng = f"{bounds['south']},{bounds['west']},{bounds['north']},{bounds['east']}"
    resp = requests.get(WAQI_BOUNDS_URL, params={"latlng": latlng, "token": token}, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "ok":
        raise RuntimeError(f"WAQI bounds request failed: {payload}")

    candidates = payload["data"]
    print(f"Found {len(candidates)} candidate stations in bounding box", file=sys.stderr)

    stations = []

    def fetch_one(station):
        uid = station.get("uid")
        try:
            r = requests.get(WAQI_FEED_URL.format(uid=uid), params={"token": token}, timeout=timeout)
            r.raise_for_status()
            body = r.json()
            if body.get("status") != "ok":
                return None
            data = body["data"]
            pm25 = data.get("iaqi", {}).get("pm25", {}).get("v")
            if pm25 is None:
                return None
            return {
                "uid": uid,
                "name": data.get("city", {}).get("name", station.get("station", {}).get("name", "Unknown")),
                "lat": data.get("city", {}).get("geo", [station.get("lat"), station.get("lon")])[0],
                "lon": data.get("city", {}).get("geo", [station.get("lat"), station.get("lon")])[1],
                "pm25": float(pm25),
                "time": data.get("time", {}).get("iso") or data.get("time", {}).get("s"),
            }
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(fetch_one, s) for s in candidates]
        for fut in as_completed(futures):
            result = fut.result()
            if result is not None:
                stations.append(result)

    print(f"Retrieved PM2.5 readings for {len(stations)} stations", file=sys.stderr)
    return stations


def load_offline_stations(path):
    with open(path) as f:
        return json.load(f)


def idw_interpolate(stations, bounds, grid_res, power=2, max_distance_km=300):
    """Inverse-distance-weighted interpolation of station PM2.5 values onto a
    regular lat/lon grid. Cells farther than max_distance_km from the nearest
    station are marked as NaN (rendered transparent)."""
    lats = np.arange(bounds["south"], bounds["north"] + grid_res, grid_res)
    lons = np.arange(bounds["west"], bounds["east"] + grid_res, grid_res)

    station_lats = np.array([s["lat"] for s in stations])
    station_lons = np.array([s["lon"] for s in stations])
    station_vals = np.array([s["pm25"] for s in stations])

    grid = np.full((len(lats), len(lons)), np.nan)

    # Rough km-per-degree conversion, adjusted for longitude by latitude.
    for i, lat in enumerate(lats):
        km_per_lon_deg = 111.32 * math.cos(math.radians(lat))
        for j, lon in enumerate(lons):
            dlat_km = (station_lats - lat) * 111.32
            dlon_km = (station_lons - lon) * km_per_lon_deg
            dist_km = np.sqrt(dlat_km ** 2 + dlon_km ** 2)

            nearest = dist_km.min()
            if nearest > max_distance_km:
                continue

            if nearest < 1e-6:
                grid[i, j] = station_vals[dist_km.argmin()]
                continue

            weights = 1.0 / (dist_km ** power)
            grid[i, j] = np.sum(weights * station_vals) / np.sum(weights)

    return lats, lons, grid


def value_to_color(value):
    for k in range(len(AQI_BREAKPOINTS) - 1):
        v0, c0 = AQI_BREAKPOINTS[k]
        v1, c1 = AQI_BREAKPOINTS[k + 1]
        if v0 <= value <= v1:
            t = 0 if v1 == v0 else (value - v0) / (v1 - v0)
            return tuple(int(c0[i] + t * (c1[i] - c0[i])) for i in range(4))
    return AQI_BREAKPOINTS[-1][1]


def rasterize(lats, lons, grid, alpha=170):
    """Render the grid to an RGBA PNG (in-memory) aligned to (south,west)-(north,east)."""
    height, width = len(lats), len(lons)
    img = np.zeros((height, width, 4), dtype=np.uint8)
    for i in range(height):
        for j in range(width):
            v = grid[i, j]
            if np.isnan(v):
                continue
            r, g, b, _ = value_to_color(v)
            img[i, j] = (r, g, b, alpha)

    # Image rows must go north -> south (top -> bottom) for ImageOverlay.
    img = np.flipud(img)
    pil_img = Image.fromarray(img, mode="RGBA")
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def band_for(value):
    for lo, hi, label, color in BAND_LABELS:
        if lo <= value <= hi:
            return label, color
    return BAND_LABELS[-1][2], BAND_LABELS[-1][3]


def parse_station_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_station_time(value):
    dt = parse_station_time(value)
    if dt is None:
        return value or "n/a"
    return dt.strftime("%Y-%m-%d %H:%M %z")


def compute_time_range(stations):
    parsed = [parse_station_time(s.get("time")) for s in stations]
    # Only timezone-aware timestamps can be safely compared/converted to UTC;
    # WAQI's `time.iso` field always includes an offset, so this only drops
    # entries with missing/malformed timestamps.
    utc_times = [dt.astimezone(timezone.utc) for dt in parsed if dt is not None and dt.tzinfo is not None]
    if not utc_times:
        return None
    return min(utc_times), max(utc_times), len(utc_times)


TIME_RANGE_HTML = """
<div style="
    position: fixed; top: 10px; left: 50px; z-index: 9999;
    background: white; padding: 8px 12px; border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.4); font-family: sans-serif; font-size: 13px;
    max-width: 320px;">
  {text}
</div>
"""


def build_time_range_banner(stations):
    time_range = compute_time_range(stations)
    if time_range is None:
        return TIME_RANGE_HTML.format(text="Data observed: unknown")

    min_dt, max_dt, n = time_range
    fmt = "%Y-%m-%d %H:%M"
    if min_dt == max_dt:
        text = f"Data observed: {min_dt.strftime(fmt)} UTC ({n} stations)"
    else:
        text = (
            f"Data observed between {min_dt.strftime(fmt)} and {max_dt.strftime(fmt)} UTC "
            f"({n} stations) &mdash; stations do not all update at the same time."
        )
    return TIME_RANGE_HTML.format(text=text)


LEGEND_HTML = """
<div style="
    position: fixed; bottom: 30px; left: 30px; z-index: 9999;
    background: white; padding: 10px 14px; border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.4); font-family: sans-serif; font-size: 13px;">
  <div style="font-weight: 600; margin-bottom: 6px;">PM2.5 (WAQI index)</div>
  {rows}
</div>
"""


def build_legend():
    rows = "\n".join(
        f'<div style="display:flex;align-items:center;margin:2px 0;">'
        f'<span style="width:14px;height:14px;background:{color};display:inline-block;'
        f'margin-right:6px;border-radius:2px;"></span>{lo}-{hi} {label}</div>'
        for lo, hi, label, color in BAND_LABELS
    )
    return LEGEND_HTML.format(rows=rows)


def build_map(stations, lats, lons, grid, bounds, output_path):
    center_lat = (bounds["south"] + bounds["north"]) / 2
    center_lon = (bounds["west"] + bounds["east"]) / 2
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles="OpenStreetMap")

    png_buf = rasterize(lats, lons, grid)
    png_data_uri = "data:image/png;base64," + __import__("base64").b64encode(png_buf.read()).decode()

    folium.raster_layers.ImageOverlay(
        image=png_data_uri,
        bounds=[[bounds["south"], bounds["west"]], [bounds["north"], bounds["east"]]],
        opacity=0.65,
        interactive=False,
        cross_origin=False,
    ).add_to(fmap)

    for s in stations:
        label, color = band_for(s["pm25"])
        popup = folium.Popup(
            html=(
                f"<b>{s['name']}</b><br>"
                f"PM2.5: {s['pm25']:.0f} ({label})<br>"
                f"Observed: {format_station_time(s.get('time'))}"
            ),
            max_width=250,
        )
        folium.CircleMarker(
            location=[s["lat"], s["lon"]],
            radius=5,
            color="black",
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=popup,
        ).add_to(fmap)

    fmap.get_root().html.add_child(folium.Element(build_legend()))
    fmap.get_root().html.add_child(folium.Element(build_time_range_banner(stations)))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fmap.save(output_path)
    print(f"Wrote map to {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", default=os.environ.get("WAQI_TOKEN"), help="WAQI API token (or set WAQI_TOKEN)")
    parser.add_argument("--offline", help="Path to a local JSON station list instead of calling the API")
    parser.add_argument("--output", default="output/southeast_asia_aq_map.html")
    parser.add_argument("--grid-res", type=float, default=0.25, help="Grid resolution in degrees")
    parser.add_argument("--max-distance-km", type=float, default=300.0)
    args = parser.parse_args()

    if args.offline:
        stations = load_offline_stations(args.offline)
    else:
        if not args.token:
            parser.error("A WAQI token is required (--token or WAQI_TOKEN env var), or use --offline")
        stations = fetch_stations(args.token)
        cache_path = os.path.join(os.path.dirname(args.output) or ".", "latest_stations.json")
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(stations, f, indent=2)

    if not stations:
        print("No station data available; aborting.", file=sys.stderr)
        sys.exit(1)

    lats, lons, grid = idw_interpolate(
        stations, SEA_BOUNDS, args.grid_res, max_distance_km=args.max_distance_km
    )
    build_map(stations, lats, lons, grid, SEA_BOUNDS, args.output)


if __name__ == "__main__":
    main()
