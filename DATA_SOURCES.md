# Data sources and provenance

Every hazard result carries a source label and the run summary records source counts and data confidence.

| Hazard | Sources used by the current release | Limitation |
| --- | --- | --- |
| Flood | Local FEMA NFHL GeoPackage where present; Pakistan JRC flood raster; documented fallback | NFHL is US-only; global layers are screening resolution. |
| Elevation | Local Copernicus DSM, OpenTopography, Open-Meteo | DSM and point elevation are not a survey-grade first-floor elevation. |
| Wind | Open-Meteo ERA5 or local raster | Reanalysis is not a property-level return-period wind model. |
| Heat | Open-Meteo, NOAA CDO, or local raster | Operational heat effects need building HVAC and duration data. |
| Wildfire | NASA FIRMS or local burn layer | Active-fire detections are not annual structure-loss probabilities. |
| Drought | Open-Meteo ERA5 daily precipitation, 2015-2024 (mean annual longest dry spell) | Dry-spell length, not a drought anomaly; coarse grid; not available offline. |
| Landslide | Optional local raster `landslide_susceptibility.tif` | Not assessed without the raster; the scale of any raster you add is your responsibility to document. |

Local rasters should be kept with provider name, dataset version, license, CRS, resolution, AOI, and retrieval date. API keys stay in `.env` and are never part of an assessment export.

Source quality is ranked by the table in `src/hazard_registry.py` (synthetic 0, FIRMS 0.3, JRC no-mapped-depth 0.4, ERA5 0.6, JRC depth 0.7, FEMA/NOAA 0.8, local rasters 0.9, Copernicus DEM 1.0). The ranking is a judgement about resolution and directness, not a measured accuracy.

## Added with the API and commercial upgrade

Open-Meteo Climate API serves CMIP6 HighResMIP output (CC BY 4.0), used for the per-site climate change signal. Open-Meteo Flood API serves GloFAS v4 river discharge, used for the river indicator. Open-Meteo Geocoding powers the place search in manual entry. All three use the same key as the other Open-Meteo calls (`OPEN_METEO_API_KEY`).
