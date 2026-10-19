# Climate Risk Portfolio Assessor

A tool that scores physical climate risk for a portfolio of buildings and infrastructure. You give it a list of assets with a location and a replacement value. It returns a risk score, a severity tier and the main hazard for each asset, a map, and a report you can print or send to a client.

It covers flood, wind, wildfire, extreme heat, river flooding, drought and landslide. The first four feed a loss estimate. The last three are shown as hazard indicators only, because there is no defensible damage curve for them here.

## Quick start

You need Python 3.11 or newer.

```bash
pip install -r requirements.txt
streamlit run app/dashboard.py
```

The app opens with a demo portfolio, so you can press "Run assessment" straight away. The demo uses synthetic hazard values and says so on every screen and in the report. Nothing is scored as safe because data is missing: a hazard without data shows "No data" instead of "Low".

To run without any network access, set `CRPA_OFFLINE=1`.

## Getting your own assets in

The sidebar has three ways to load a portfolio.

Upload CSV takes a file in the format of `data/templates/portfolio_upload_template.csv`. You can download the template from the sidebar.

Enter manually gives you a form and an editable table. Type a place name and the app looks up its coordinates and region. Add assets one by one with the form, or edit the table directly, including adding rows at the bottom. Manual rows go through the same validation as an uploaded CSV, and a problem with a row is reported next to the form.

The demo portfolio is a small mixed set of US and Pakistan sites.

## Real data and where to get keys

Most of the real data comes from Open-Meteo and works without a key. The other services are optional and each one adds a hazard layer or a better input.

| Service | What it adds | Key |
| --- | --- | --- |
| Open-Meteo | Wind and heat extremes (ERA5), dry spells, GloFAS river discharge, CMIP6 climate change signal, elevation, place search | Not needed for non-commercial use. Paid plan at https://open-meteo.com/en/pricing |
| NOAA Climate Data Online | Station temperature records for the US | https://www.ncdc.noaa.gov/cdo-web/token |
| NASA FIRMS | Active fire detections from the last 10 days | https://firms.modaps.eosdis.nasa.gov/api/map_key/ |
| OpenTopography | 30 m Copernicus elevation | https://portal.opentopography.org/requestService?service=api |
| NVIDIA API catalog | Optional AI-written narrative in the report | https://build.nvidia.com |

Copy `.env.example` to `.env` and fill in what you have. You can also paste keys into the "API keys" panel in the sidebar. Those stay in memory for the session only.

If you have local files, the app also reads FEMA flood zone GeoPackages and WGS84 GeoTIFFs for wind, heat, wildfire, drought and landslide from `data/hazards/`. A raster is used only when it covers the asset.

## Climate scenarios

"Current climate" uses historical records. The CMIP6 option fetches a model projection for each site and uses the difference in mean annual maximum temperature and wind between 1991 to 2020 and 2021 to 2050. It uses one model (EC_Earth3P_HR) under high emissions, so it is one plausible future and not a forecast. If the request fails for a site, the app falls back to fixed regional numbers and records that in the `scenario_source` column.

## How a score is built

For the four damage hazards, a hazard intensity (flood depth, gust speed, fire score, peak temperature) goes through a sigmoid fragility curve to give a damage probability. The curves are inspired by HAZUS but are not calibrated, and they live in `src/fragility.py`. Probabilities combine as one minus the product of survival chances, scaled by a factor for the asset class. The scenario loss is probability times loss ratio times value. It is a scenario figure, not an annual expected loss. **Because the damage functions are experimental and lack empirical validation, monetary loss figures (including AAL/PML and portfolio totals) are withheld by default** across the dashboard, API, reports and exports. Hazard metrics and screening risk scores remain available.

For internal research only, `CRPA_ALLOW_EXPERIMENTAL_LOSSES=1` explicitly enables these figures and displays an experimental-model warning. Do not set this variable in production or client-facing deployments. The override does not change model validation status.

Severity is Low below 25, Medium 25 to 49, High 50 to 74, and Critical from 75. A Low rating is marked "verified" only when every damage hazard has real data and the source quality is at least 0.5. The score range shown beside each asset is a plus or minus 15 percent sensitivity on hazard intensity. It is not a confidence interval.

Colour identifies the hazard (flood blue, fire red, heat orange, wind slate, landslide purple, river cyan, drought yellow). Severity is shown as text and a segmented meter, so it never depends on colour alone.

## The report

Each run writes a standalone HTML report with a cover, headline numbers, two charts, the top assets, notes per hazard, data sources and attribution. It has no scripts and prints cleanly to PDF. Markdown, JSON and CSV versions are written alongside it.

## Selling or sharing reports

Three things matter before you charge for results.

The Open-Meteo free tier is for non-commercial use. If you sell reports that use its data, buy a plan and set `OPEN_METEO_API_KEY`. The code then switches to the paid hosts. That switch follows Open-Meteo's documented host naming but has not been tested against a live paid account.

The dashboard and report carry your branding when you set `CRPA_BRAND_NAME`, `CRPA_BRAND_TAGLINE`, `CRPA_BRAND_COLOR` and `CRPA_BRAND_FOOTER`.

The data sources require attribution (CMIP6 under CC BY 4.0, Copernicus ERA5 and others). The report includes the notices. Read `DATA_SOURCES.md` and `LIMITATIONS.md` before you rely on any figure. The model is a screening tool and does not replace a site survey or an engineering study.

## API

```bash
uvicorn api.main:app
```

Endpoints sit under `/api/v1`: `hazards`, `assess` (CSV upload), `jobs/{id}` and the generated files. Interactive docs are at `/docs`.

## Tests

```bash
pip install -r requirements-dev.txt
CRPA_OFFLINE=1 pytest -q
```

The connector tests use synthetic responses. I could not reach the Open-Meteo climate, flood and geocoding endpoints from the build environment, so those calls have not been run against the live services. Run one assessment with network access on before relying on them.

## Repository layout

`src/` holds the engine (ingestion, hazards, fragility, report, charts). `app/dashboard.py` is the Streamlit interface and `api/main.py` the FastAPI service. `archive/` holds retired experiments that are no longer maintained.

## Licence

See `LICENSE`.
