CRPA Demo — Multi-hazard Risk Assessment
========================================

This demo shows the Climate Risk Portfolio Assessor running with uv-managed dependencies.

## Quick Start

```bash
# Windows
uv venv --python 3.11
.venv\Scripts\activate
uv pip sync requirements-dev.txt
.venv\Scripts\streamlit run app\dashboard.py

# Linux/macOS
uv venv --python 3.11
. .venv/bin/activate
uv pip sync requirements-dev.txt
.venv/bin/streamlit run app/dashboard.py
```

## Demo: Sample Hazard Values at Asset Locations

Run the test script:

```bash
.venv\Scripts\python.exe scripts\find_valid_flood_points.py
```

Output: 100 valid flood-depth pixels with coordinates and metric values.

```bash
.venv\Scripts\python.exe scripts\test_european_hazards.py
```

Output: Raw hazard values for northern Europe assets (flood RP20/RP100/RP500 + wildfire severity).

## Architecture

- **FastAPI** (`api/`) — async backend with uvicorn, background job processing
- **Streamlit** (`app/`) — interactive dashboard, UI/UX Pro Max design
- **Rasterio** — GeoTIFF reading, block-wise processing for memory efficiency
- **Pandas/Numpy** — data manipulation and statistical calculations
- **Pydantic** — input validation and configuration management

## Hazards Supported

| Hazard | Source | Status |
|--------|--------|--------|
| Flood | JRC Global FloodMap RP20/100/500 | Source-backed |
| Wildfire | EFFIS severity 2025 | Source-backed |
| Wind | Open-Meteo ERA5 gusts | API (no key required) |
| Heat | Open-Meteo max temp | API (no key required) |

## Data Sources & Licensing

- **JRC Global FloodMap** — open data, CC BY 4.0
- **EFFIS wildfire severity** — proprietary, requires download
- **Open-Meteo** — free API, no key required for historical reanalysis
- **OpenTopography COP30** — API key optional for global 30m elevation

## Methodology

1. **Ingestion** — CSV asset validation, coordinate normalization
2. **Hazards** — raster sampling at asset locations, API fallbacks
3. **Fragility** — HAZUS-inspired sigmoid curves (uncalibrated defaults)
4. **Risk** — survival model: P(any) = 1 - Π(1 - p_i), scaled by criticality
5. **Expected loss** — probability × loss ratio × replacement value (scenario-based)

## Synthetic vs Source-Backed

- Confidence < 0.3 → synthetic/demo data warning displayed
- All results record source label and confidence metric
- AI report fails gracefully → deterministic report shown instead

## Repository

- **Age** — 14-week thesis project (Oct 2026 start)
- **Codebase** — ~40 Python source files, ~17K lines
- **Dependencies** — 61 packages (uv: 58 resolved in lockfile)
- **License** — proprietary commercial

## Performance

- 10-asset portfolio: ~2-5 seconds
- 50-asset portfolio: ~10-15 seconds  
- 100+ assets — block-wise raster sampling keeps memory < 1GB
- Wildfire raster: 247B pixels — never load whole; use windowed sampling