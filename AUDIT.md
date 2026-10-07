# Final export audit — 2026-10-07

## Result

**PASS for GitHub packaging.** The export is 51 files and about 318 KB. No `.env`, private key, certificate, cache, virtual environment, generated report, or large raster was copied.

## Findings

| Area | Status | Action |
|---|---|---|
| Credentials | PASS | `.env` stays only in the project root and is ignored; export contains `.env.example` only. |
| Source code | PASS | `app`, `api`, `src`, `scripts`, and `tests` included. |
| Reproducible fixtures | PASS | Sample Pakistan CSVs, expected results, templates, and data README included. |
| Launch/deploy | PASS | `run.bat`, `run.sh`, Dockerfile, and requirements included. |
| Large/raw hazard data | HOLD | Keep outside GitHub; publish separately with provenance and licensing metadata. |
| Generated artifacts | EXCLUDED | `outputs`, caches, GraphFlow state, and `brag-output-*` are local artifacts. |
| FEMA NFHL | HOLD | No GeoPackages exist in the source checkout. |

## Key safety check

The export was checked for secret-like filenames and credential-bearing files. No credential file is present. Preserve the root `.env` locally; never add it to `Github` or version control.
