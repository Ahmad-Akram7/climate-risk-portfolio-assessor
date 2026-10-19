# Verified external-data audit for CRPA

**Status:** source-verified reference evidence and data acquisition plan. This is not a validated loss model and does not claim that raw raster files or building-level observations have been imported.

## What has been verified

### 1. Pakistan Floods 2022 Post-Disaster Needs Assessment (PDNA)

The Government of Pakistan-led assessment, supported by ADB, the EU, UN agencies, and the World Bank, reports approximately **USD 14.9 billion in total damage**, **USD 15.2 billion in economic losses**, and **at least USD 16.3 billion in recovery/reconstruction needs**. The World Bank summary reports sector damage estimates of **USD 5.6 billion for housing**, **USD 3.7 billion for agriculture and livestock**, and **USD 3.3 billion for transport and communications**. These figures are transcribed as published, rounded aggregate benchmarks; see the linked source for definitions and context.

Sources:
- [UNDP Pakistan — Pakistan Floods 2022 PDNA](https://www.undp.org/pakistan/publications/pakistan-floods-2022-post-disaster-needs-assessment-pdna)
- [World Bank — PDNA headline estimates and sector figures](https://www.worldbank.org/en/news/press-release/2022/10/28/pakistan-flood-damages-and-economic-losses-over-usd-30-billion-and-reconstruction-needs-over-usd-16-billion-new-assessme)

**Interpretation boundary:** these are national/sector aggregates. They are useful for event context, reporting cross-checks, and top-down plausibility checks only. They are **not** building-level damage observations, not a sample of damage ratios against flood depth, and not suitable for directly fitting or validating CRPA's building-level vulnerability functions. Economic loss and recovery needs must not be relabelled as physical asset damage.

The accompanying CSV is a small, source-linked evidence table, not a copy of the complete PDNA dataset/report. The report's reuse terms should be checked before redistributing its contents.

### 2. JRC/Copernicus global river-flood hazard maps

The European Commission Joint Research Centre / Copernicus Emergency Management Service publishes global river-flood inundation and water-depth maps for seven return periods from 1-in-10 to 1-in-500 years. The dataset is described as approximately 3 arc-seconds (~90 m), with CC BY 4.0 conditions in the dataset record. It is a **modelled hazard layer**, not an observed-damage dataset.

- [JRC dataset record and licence](https://doi.org/10.2905/JRC.VD32YWG)
- [JRC/CEMS-GloFAS data directory](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/)

**CRPA action:** assess these maps as a replacement/comparison candidate for the currently limited Pakistan return-period coverage. Before integration, clip to the intended coverage, record the exact release/date and files, inspect no-data/spurious-depth/permanent-water masks, validate units and CRS, and compare against event observations where possible. Do not call modelled hazard depth "observed flood depth."

### 3. ERA5-Land climate reanalysis

ERA5-Land provides global land-surface reanalysis from 1950 onward, hourly, on a regular latitude-longitude grid; the catalogue lists 0.1° distribution spacing and a native resolution around 9 km. The dataset catalogue identifies CC BY terms and DOI 10.24381/cds.e2161bac.

- [Copernicus Climate Data Store — ERA5-Land](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land)

This can provide consistent historical climate covariates (for example temperature, wind-related variables where available, precipitation, and soil-water variables). It is reanalysis/modelled data, not a station observation at each asset. Document variable names, temporal aggregation, units, interpolation, and uncertainty. Accept the provider's current licence/terms before downloading or redistributing data.

### 4. NASA FIRMS active-fire observations

NASA FIRMS distributes MODIS, VIIRS and Landsat active-fire/hotspot products and provides archive downloads; standard science-quality products replace near-real-time detections after processing.

- [NASA FIRMS active-fire products](https://firms.modaps.eosdis.nasa.gov/active_fire)
- [NASA FIRMS archive downloads](https://firms2.modaps.eosdis.nasa.gov/download/)

Use fire detections as **evidence of satellite-observed thermal anomalies**, not as a complete burned-area boundary or property-damage record. Absence of a detection does not prove absence of fire. Select standard science-quality data for retrospective analysis and record sensor, confidence, acquisition time, and processing version.

## What this audit does not establish

- No building-level observed damage labels linked to hazard intensity were found in the connected GIS Cloud workspace during the preceding audit.
- A country-level PDNA cannot validate a damage ratio curve at individual-asset level.
- A hazard map's scientific provenance does not validate CRPA's exposure values, vulnerability functions, or monetary-loss outputs.
- EM-DAT's public-data terms restrict commercial use and redistribution/derivative databases; do not make it a packaged CRPA data dependency without reviewing the current terms. Reference: [EM-DAT access and terms FAQ](https://doc.emdat.be/docs/additional-resources-and-tutorials/faq/).

## Recommended analysis protocol

1. Keep raw provider data out of Git if files are large, access-controlled, or redistribution rights are unclear. Store scripts/manifests and stable source URLs in the repository; use a versioned data release or documented download command for reproducibility.
2. Add each acquired asset to a manifest with provider, product/version, URL, retrieval date, licence, checksum, coverage, CRS, resolution, temporal extent, units, nodata convention, processing steps, and QA result.
3. Keep hazard validation separate from vulnerability validation. Hazard validation compares event footprints/depths or observations; vulnerability validation requires damage-state or loss observations matched to asset attributes and hazard intensity.
4. Do not fit a curve using national sector totals alone. At minimum, require compatible asset-level or well-defined sample-level damage/loss observations, intensity values, exposure denominators, sampling/selection notes, and currency/base-year metadata.
5. Preserve CRPA's existing experimental-loss gate until an appropriate validation dataset and a documented validation report justify changing it.

## Files in this change

- `data/verified_reference_evidence.csv`: source-linked published aggregate benchmarks.
- `docs/VERIFIED_DATA_AUDIT.md`: source descriptions, use boundaries, and integration/validation plan.

No raw raster download or building-level validation dataset is included in this change.
