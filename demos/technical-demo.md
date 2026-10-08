CRPA Technical Demo — Quick Reference
=====================================

## One-Command Demo

```bash
# From project root (Windows)
uv venv --python 3.11
.venv\Scripts\activate
uv pip sync requirements-dev.txt
.venv\Scripts\streamlit run app\dashboard.py
```

Then open http://localhost:8502 and:
- Upload `data/templates/europe_demo_north.csv` (northern Europe assets)
- Select scenario "current"
- Toggle "Use AI report" on/off
- View risk scores, map, and AI-generated report

## Technical Overview

### Overall Architecture & Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI + uvicorn | Async HTTP API, background job processing |
| **Dashboard** | Streamlit + Plotly/PyDeck | Interactive UI, risk visualization |
| **Geospatial** | Rasterio + GDAL (CLI) | GeoTIFF reading, windowed sampling |
| **Data** | Pandas + NumPy | Asset table manipulation, statistics |
| **Validation** | Pydantic | Input schema, config management |
| **Dependency Mgmt** | uv + pyproject.toml + uv.lock | Reproducible environments, 58 resolved packages |

### Hazards Currently Supported

| Hazard | Source | Data Type | Sampling |
|--------|--------|-----------|----------|
| **Flood** | JRC Global FloodMap RP20/100/500 | GeoTIFF (binary depth in m) | Point-sample via rasterio |
| **Wildfire** | EFFIS severity 2025 | GeoTIFF (probability 0–100) | Point-sample via rasterio |
| **Wind** | Open-Meteo ERA5 gusts | API (global, no key) | Reanalysis historical |
| **Heat** | Open-Meteo max temp | API (global, no key) | Reanalysis historical |

### Data Sources & Licensing

| Source | Type | License | Notes |
|--------|------|---------|-------|
| JRC Global FloodMap | GeoTIFF | CC BY 4.0 | Open data; RP20/100/500yr return periods |
| EFFIS wildfire severity | GeoTIFF | Proprietary | Download required; ~247B pixels |
| Open-Meteo historical | API | Public domain | No key required for reanalysis |
| OpenTopography COP30 | API/GeoTIFF | Varies | Optional key for global 30m elevation |
| GADM administrative boundaries | Shapefile | Public domain | Used for AOI validation |

### Methodology

1. **Ingestion** — CSV validated for required columns (asset_id, name, lat, lon, state, asset_class, replacement_value). Schema checks: coordinate bounds, duplicate IDs, null-island detection.

2. **Hazards** — 
   - Rasterio point-sample at each asset (lon, lat) → flood depth (m), wildfire severity
   - Open-Meteo APIs for wind gust max (m/s) and max temperature (°C)
   - Fallback to synthetic demo values when APIs/rasters unavailable

3. **Fragility** — HAZUS-inspired sigmoid curves (uncalibrated defaults):
   ```
   p(damage) = 1 / (1 + exp(-k * (depth - x0)))
   ```
   Curves have `col`, `k`, `x0`, `max_loss`, `unit` parameters.

4. **RiskCalc** — Survival model combines hazards:
   ```
   P(any) = 1 - Π(1 - p_i)  [independence assumption]
   ```
   Scaled by asset-class criticality factor.

5. **Expected loss** — `probability × loss_ratio × replacement_value`
   - Scenario-based (not annual AAL)
   - Does not model deductibles, floor height, construction type

6. **Reporting** — 
   - AI call (NVIDIA API) → deterministic report on failure
   - Markdown + JSON output files
   - Confidence metric (< 0.3 → synthetic data warning)

### Synthetic/Demo vs Source-Backed

- **Confidence < 0.3** → warning: "Hazard data is mostly synthetic demo data"
- All results record: `source` label + `confidence` metric (0–1)
- AI failures gracefully degrade to deterministic report
- Users can configure API keys (NVIDIA, NOAA, NASA, OpenTopography) to improve coverage

### Repository & Development

| Metric | Value |
|--------|-------|
| **Project age** | 14-week thesis project (started Oct 2026) |
| **Source code** | ~40 Python files, ~17K lines |
| **Commit history** | Initial implementation through final phase |
| **Dependencies** | 61 packages (uv resolves 58 in lockfile) |
| **Deployment** | Streamlit Cloud / GitHub Pages compatible |
| **Environment** | Windows (primary), Linux/macosecondary |

### Key Third-Party Dependencies & Licenses

| Package | License | Purpose |
|---------|---------|---------|
| fastapi | MIT | Web framework |
| streamlit | Apache-2.0 | Dashboard UI |
| rasterio | MIT | GeoTIFF reading |
| geopandas | BSD-3 | Spatial operations |
| pandas | BSD-3 | Data manipulation |
| pydantic | MIT | Validation |
| numpy | BSD-3 | Numerical computing |
| plotly | MIT | Interactive charts |
| pydeck | BSD-3 | deck.gl maps |

### Performance & Scalability

| Asset Count | Approx. Time | Notes |
|-------------|-------------|-------|
| 10 assets | 2–5 s | Quick startup |
| 50 assets | 10–15 s | Moderate |
| 100+ assets | 30–60 s | Block-wise raster sampling; memory < 1GB |
| Wildfire raster (247B px) | Never loaded whole | Windowed sampling only; `gdal_translate -of GTiff -width 1000` for previews |