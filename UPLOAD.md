# GitHub / sales export

This folder is the clean, reviewable export of the Climate Risk Portfolio Assessor.

## Included

- application, API, tests, scripts, launchers, dependency files, and license
- sample Pakistan portfolios and expected results
- upload templates and data documentation
- `.env.example` only

## Deliberately excluded

- `.env` and every API key (the working keys remain at `D:\climate-risk-portfolio-assessor\.env`)
- `.venv`, caches, generated reports, logs, GraphFlow state, and the promotional video
- GeoTIFF/DEM hazard rasters and elevation tile bundles; they are too large for a normal GitHub repo and may have separate provider terms
- FEMA NFHL GeoPackages, which are not present in this checkout

The excluded rasters should be distributed through a release/object store with source, license, AOI, CRS, resolution, and checksum metadata. Do not put credentials in a release archive.

## Publish checklist

1. Copy `.env.example` to `.env` locally and fill keys on the deployment machine.
2. Review each hazard source license and attribution before selling or redistributing derived data.
3. Keep raw provider downloads outside Git history; commit only small fixtures or documented download scripts.
4. Run `run.bat` (Windows) or `bash run.sh api`/`bash run.sh dashboard` (Linux/macOS).

This export contains no credentials by design.
