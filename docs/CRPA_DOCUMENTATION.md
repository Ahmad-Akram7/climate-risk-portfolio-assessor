# Climate Risk Portfolio Assessor (CRPA)

Climate Risk Portfolio Assessor reads an asset CSV and produces multi-hazard screening scores, scenario loss estimates, a Streamlit dashboard, and a Markdown report. It runs locally and is distributed under a proprietary commercial license.

When no live layers or API keys are available, CRPA uses synthetic demo values. Each result records its source and confidence so demo values remain separate from values backed by a real dataset.

## Quick Start

### On Windows:
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\streamlit run app\dashboard.py
```

### On Linux/macOS:
```bash
./run.sh setup
./run.sh dashboard   # http://localhost:8502
./run.sh api         # http://localhost:8000/docs
```

The `run.bat` file starts the API and dashboard together.

### Input CSV format:
```text
asset_id,name,lat,lon,state,asset_class,replacement_value
```

Supported asset classes: office, industrial, retail, residential, hospital, data_center, infrastructure, hotel, and other. Values such as `50000000`, `$50,000,000`, `50M`, and `2.5k` are accepted. The default limit is 500 assets.

## How a Run Works

1. **Validation** (`src/ingestion.py`): Validates input CSV, checks schema, coordinates, duplicate IDs, null-island coordinates, state/coordinate mismatches, and coordinate precision. Invalid rows are dropped.

2. **Hazard Extraction** (`src/hazards.py`): Reads local rasters, uses free APIs (Open-Meteo, NOAA CDO, NASA FIRMS), or falls back to synthetic demo data. Every result carries a source label so the dashboard can show how much is real data vs synthetic.

3. **Fragility Application** (`src/fragility.py`): Applies HAZUS-inspired screening curves to calculate hazard scores and scenario loss.

4. **Reporting** (`src/reporting.py`): Calls the configured OpenAI-compatible LLM when available. If the call fails, a deterministic report is written instead.

Results are written below `outputs/<run-id>/`, including asset scores, GeoJSON, a portfolio summary, QA details, and the report.

## Data Sources and Provenance

| Hazard | Sources Used | Limitations |
|--------|-------------|-------------|
| Flood | Local FEMA NFHL GeoPackage (where present); Pakistan JRC flood raster | NFHL is US-only; global layers are screening resolution |
| Elevation | Local Copernicus DSM, OpenTopography, Open-Meteo | DSM and point elevation are not survey-grade first-floor elevation |
| Wind | Open-Meteo ERA5 or local raster | Reanalysis is not a property-level return-period wind model |
| Heat | Open-Meteo, NOAA CDO, or local raster | Operational heat effects need building HVAC and duration data |
| Wildfire | NASA FIRMS or local burn layer | Active-fire detections are not annual structure-loss probabilities |

**Seismic hazard**: GEM Global Seismic Hazard Map v2023.1, PGA on rock for a 475-year return period, 3 arc-minute grid. License: CC BY-NC-SA 4.0.

**Pakistan wildfire susceptibility**: 2023 annual P90 raster derived from public 2012–2023 Pakistan wildfire susceptibility dataset (CC BY-NC-SA 4.0). Requires attribution and compliance with share-alike terms.

API keys stay in `.env` and are never part of an assessment export. Use `.env.example` as the template.

## Limitations

CRPA results are screening estimates. They can support triage and data collection, but should not be presented as exact, insurance-grade, actuarial, or regulatory results.

**Current limitations include:**
- Incomplete building exposure attributes
- Coarse or modeled hazard layers
- Limited Pakistan-specific vulnerability observations
- No shared-event portfolio simulation
- No validated AAL/PML engine
- No full CMIP6 downscaling workflow

Synthetic inputs are explicitly labelled and should not be used for decisions.

## Model Card

### Current Release Tiers

- **DEMO**: Synthetic values used for offline demonstrations
- **SCREENING**: Current production path with available hazard data and documented fallback functions
- **ENHANCED**: Reserved for runs with meaningful building and financial exposure attributes
- **PROBABILISTIC**: Reserved for a future event-set and uncertainty engine

The output includes the tier, exposure completeness, data confidence, source counts, scenario, and quality gate.

**Upgrade path**: Return-period flood layers, building archetypes, first-floor elevation, hazard-specific damage states, event loss curves, Monte Carlo uncertainty, and regional validation data.

## Export and Deployment

### What's Included
- Application, API, tests, scripts, launchers, and dependency files
- Sample Pakistan portfolios and expected results
- Upload templates and data documentation
- `.env.example` only

### Deliberately Excluded
- `.env` and every API key (working keys remain locally)
- `.venv`, caches, generated reports, logs
- GeoTIFF/DEM hazard rasters and elevation tile bundles (too large for normal GitHub repo)
- FEMA NFHL GeoPackages (not present in this checkout)

### Publish Checklist
1. Copy `.env.example` to `.env` locally and fill keys on the deployment machine
2. Review each hazard source license and attribution before selling or redistributing derived data
3. Keep raw provider downloads outside Git history; commit only small fixtures or documented download scripts
4. Run `run.bat` (Windows) or `bash run.sh api`/`bash run.sh dashboard` (Linux/macOS)

This export contains no credentials by design.

## License

This repository is proprietary and all rights are reserved. Use, resale, redistribution, and derivative products require a written commercial license. Third-party datasets keep their own licenses and attribution requirements. See `LICENSE`.

**Pakistan wildfire susceptibility attribution**: Zhang Hongguo et al. (2026), *A dataset of wildfire susceptibility in Pakistan 2012–2023*, Science Data Bank, DOI: 10.57760/sciencedb.j00001.01624. CC BY-NC-SA 4.0.