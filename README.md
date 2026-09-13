# Southeast Asia Air Quality Map

Fetches the latest PM2.5 readings from [WAQI](https://waqi.info) for Southeast
Asia (Myanmar, Thailand, Laos, Cambodia, Vietnam, Malaysia, Singapore,
Indonesia, Philippines, Brunei, Timor-Leste), spatially interpolates them
(inverse-distance weighting), and renders a pannable/zoomable Leaflet map as a
single HTML file.

The map is automatically rebuilt and published to **GitHub Pages** every few
hours by a GitHub Actions workflow, and can also be refreshed manually.

## PM2.5 caveat

WAQI's public feed exposes the PM2.5 *AQI sub-index* value (`iaqi.pm25.v`),
which is the value nearly all public AQI dashboards built on WAQI use — not
always a raw lab µg/m³ reading. The map and legend label this as "PM2.5 (WAQI
index)" accordingly, using the standard US EPA AQI color bands (Good /
Moderate / Unhealthy for Sensitive Groups / Unhealthy / Very Unhealthy /
Hazardous).

## One-time setup for GitHub Pages hosting

1. Get a free WAQI API token: https://aqicn.org/data-platform/token/
2. In this repo, go to **Settings → Secrets and variables → Actions → New
   repository secret**, name it `WAQI_TOKEN`, and paste the token.
3. Go to **Settings → Pages** and set **Source** to **GitHub Actions**.
4. The `Update SEA Air Quality Map` workflow will now run on its schedule
   (every 3 hours) and publish to your repo's Pages URL. You can also trigger
   it immediately from the **Actions** tab → *Update SEA Air Quality Map* →
   **Run workflow**.

## Running locally

```bash
pip install -r requirements.txt

# Live data (needs a WAQI token):
WAQI_TOKEN=xxxx python fetch_and_map.py
# or
python fetch_and_map.py --token xxxx --output output/map.html

# Offline dry run, no token/network needed (uses bundled synthetic data):
python fetch_and_map.py --offline sample_data/sample_stations.json --output output/test_map.html
```

Open the generated HTML file in a browser to pan and zoom the map.

### CLI options

| Flag | Default | Description |
| --- | --- | --- |
| `--token` | `$WAQI_TOKEN` | WAQI API token |
| `--offline PATH` | — | Load stations from a local JSON file instead of the API |
| `--output PATH` | `output/southeast_asia_aq_map.html` | Where to write the HTML map |
| `--grid-res` | `0.25` | Interpolation grid resolution, in degrees |
| `--max-distance-km` | `300` | Grid cells farther than this from the nearest station are left transparent, so the map doesn't imply data over areas with no nearby monitor |
