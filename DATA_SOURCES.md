# Data sources and provenance

Every hazard result carries a source label and the run summary records source counts and data confidence.

| Hazard | Sources used by the current release | Limitation |
| --- | --- | --- |
| Flood | Local FEMA NFHL GeoPackage where present; Pakistan JRC flood raster; documented fallback | NFHL is US-only; global layers are screening resolution. |
| Elevation | Local Copernicus DSM, OpenTopography, Open-Meteo | DSM and point elevation are not a survey-grade first-floor elevation. |
| Wind | Open-Meteo ERA5 or local raster | Reanalysis is not a property-level return-period wind model. |
| Heat | Open-Meteo, NOAA CDO, or local raster | Operational heat effects need building HVAC and duration data. |
| Wildfire | NASA FIRMS or local burn layer | Active-fire detections are not annual structure-loss probabilities. |

Local rasters should be kept with provider name, dataset version, license, CRS, resolution, AOI, and retrieval date. API keys stay in `.env` and are never part of an assessment export.
