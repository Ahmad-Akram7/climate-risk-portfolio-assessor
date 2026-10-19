# Pakistan 2022 flood evidence: acquisition and exploratory validation

## Purpose and status

This package combines (a) published district-level flood extent statistics and (b) official provincial house-damage counts for Sindh. The comparison is an exploratory ecological check, not asset-level validation of CRPA's vulnerability or financial-loss functions.

## Source A — satellite-derived flood extent

Umer, A. (2026), *A Multi-Resolution Geospatial Dataset of Monsoon Flood Extent and Spatial Clustering for Pakistan (2022–2025)*, Zenodo, DOI [10.5281/zenodo.20100773](https://doi.org/10.5281/zenodo.20100773). The dataset description says it integrates UNOSAT satellite-detected flood polygons with Pakistan district/tehsil boundaries and publishes flooded area and percentage by administrative unit/year. Files are licensed CC BY 4.0.

Direct source file: [District_Level_Data.csv](https://zenodo.org/records/20100773/files/District_Level_Data.csv?download=1).

The table is a third-party analysis, not a primary UNOSAT product. Its pct_flooded is an administrative-area flood extent percentage; it is not water depth, damage ratio, probability of loss, or independent validation of a flood model.

## Source B — official reported house damage

Sindh Provincial Disaster Management Authority (PDMA), *Flood 2022 — Houses Damaged, Province Status*, as of 24 October 2022. The published map reports 1,171,200 partially damaged and 709,869 fully damaged houses across its listed Sindh areas, total 1,881,069. The district table says it is based on Deputy Commissioners' reports via the Provincial Emergency Operation Center.

Source PDF: [Houses Damaged — Province Status — 24 Oct 2022](https://pdma.gos.pk/Documents/Flood/Flood_2022/Flood%20Inundation%20GIS%20Maps/Houses%20Damaged-Province%20Status-24-10-2022.pdf). The [PDMA Flood 2022 Maps index](https://pdma.gos.pk/flood-2022-maps/) lists the official map.

These are reported housing damage counts at district/subdistrict level. They are not per-building coordinates, flood depths at buildings, replacement values, insurance claims, or validated damage ratios.

## Curated matched table

data/pakistan_2022_sindh_flood_damage_exploratory.csv contains 23 non-Karachi Sindh district matches with flood extent percentages from Source A and partial/full/total house-damage counts from Source B. The Karachi administrative units were excluded from the statistical comparison because their geography/name structure did not match the 23-district join. Their reported 171 damaged houses account for the difference between the 23-district matched total (1,880,898) and the full PDMA map total (1,881,069).

## Results

| Measure | Result |
|---|---:|
| Matched districts | 23 |
| Partially damaged houses in matched districts | 1,171,077 |
| Fully damaged houses in matched districts | 709,821 |
| Total damaged houses in matched districts | 1,880,898 |
| Pearson correlation: flooded-area percentage vs. damaged-house count | 0.289 (p = 0.181) |
| Spearman rank correlation | 0.182 (p = 0.406) |
| Pearson correlation after log1p transform of both measures | 0.362 (p = 0.090) |

The association is weak and statistically inconclusive at conventional 0.05 thresholds. This does not mean flood extent is unrelated to damage: district area, settlement density, riverine/coastal processes, damage definitions, reporting completeness, timing, and mismatched spatial products can all confound the relationship. The results show that an administrative flood-area percentage alone is not a defensible proxy for the number of damaged houses.

Five districts with the largest published flood-area percentages in this joined table were Jacobabad (97.94%; 89,993 damaged houses), Shikarpur (96.90%; 35,387), Larkana (96.51%; 226,980), Kashmore (90.28%; 119,698), and Badin (67.56%; 50,575). These figures are descriptive and should not be interpreted as a damage ranking.

The reproducible script scripts/analyze_pakistan_2022_sindh_damage.py checks the 23-row join, unique district names, percentage range, and partial + full = total invariants, then emits reports/pakistan_2022_sindh_exploratory_analysis.json.

## Raster acquisition — TU Wien Sentinel-1 flood-frequency evidence

TU Wien's open dataset, *Sentinel-1 based analysis of the Pakistan Flood in 2022*, DOI [10.48436/zvvmh-nan78](https://doi.org/10.48436/zvvmh-nan78), is CC BY 4.0. It covers the southern part of Pakistan for 10 August–23 September 2022. The merged flood_frequency.tif records the percentage of valid observations classified as flooded; first_flood_detection.tif records day-of-year of first detection. Neither is a water-depth surface or damage inventory.

Run from the repository root:

```bash
python scripts/acquire_pakistan_2022_flood_evidence.py
```

The script downloads both files into data/raw/pakistan_2022_flood/, checks the MD5 values published with the source record, and (if rasterio is installed) records CRS, bounds, dimensions, nodata, and valid-pixel min/max in an acquisition manifest. Raw rasters are intentionally not committed to Git because they are large binary assets; retain the manifest and source references.

**Execution limitation:** the connected execution environment could not resolve external download hosts, so the raster binaries have not been downloaded or checksum-verified in this run. The script provides the repeatable acquisition and verification path; it must be run in a network-enabled environment before claiming raster-level QA is complete.

## What would be required for actual vulnerability validation

A defensible loss-curve validation dataset needs observations matched at asset or carefully defined sample level, ideally containing: asset coordinates; occupancy/construction/material/floor attributes; event date; observed flood depth or intensity at the asset; damage state or repair cost; replacement value or a defensible denominator; source and survey method; missingness/selection flags; currency and price year. The current sources do not jointly provide these fields. Keep CRPA's experimental-loss gate in place.

## Attribution

- Flood extent: Umer, A. (2026), Zenodo, DOI 10.5281/zenodo.20100773, CC BY 4.0.
- Event flood-frequency raster: Roth, F. et al. (2022), TU Wien Research Data, DOI 10.48436/zvvmh-nan78, CC BY 4.0.
- House damage counts: Sindh PDMA, official *Flood 2022 — Houses Damaged — Province Status*, as of 24 October 2022; source map attribution states Deputy Commissioners' reports / Provincial Emergency Operation Center.
