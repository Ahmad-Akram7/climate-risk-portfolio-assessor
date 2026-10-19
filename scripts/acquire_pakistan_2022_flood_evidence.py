#!/usr/bin/env python3
"""Acquire and checksum TU Wien's open Pakistan-2022 flood-frequency rasters.

Raw rasters are intentionally kept outside Git. Run from the repository root:
    python scripts/acquire_pakistan_2022_flood_evidence.py
Optional dependency for raster QA: rasterio (otherwise checksum verification still runs).
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "pakistan_2022_flood"
FILES = {
    "flood_frequency.tif": {
        "url": "https://researchdata.tuwien.at/records/zvvmh-nan78/files/flood_frequency.tif?download=1",
        "md5": "fb76fcffac6e5e1aa967668c55ba300a",
        "description": "Pixel-level percentage of valid observations classified as flooded during the study period.",
    },
    "first_flood_detection.tif": {
        "url": "https://researchdata.tuwien.at/records/zvvmh-nan78/files/first_flood_detection.tif?download=1",
        "md5": "19cb98e49e6b786b4efd2e2256d18859",
        "description": "Day-of-year of first flood detection in the study period.",
    },
}
SOURCE = {
    "title": "Sentinel-1 based analysis of the Pakistan Flood in 2022",
    "publisher": "TU Wien Research Data",
    "doi": "10.48436/zvvmh-nan78",
    "license": "CC BY 4.0",
    "study_period": "2022-08-10 to 2022-09-23",
    "coverage_note": "Southern Pakistan study area; not a complete all-Pakistan damage inventory.",
    "landing_page": "https://researchdata.tuwien.at/records/zvvmh-nan78",
}

def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def raster_metadata(path: Path) -> dict:
    try:
        import rasterio
    except ImportError:
        return {"qa_status": "checksum_only", "note": "Install rasterio to inspect raster metadata and valid-pixel statistics."}
    with rasterio.open(path) as ds:
        band = ds.read(1, masked=True)
        valid_count = int(band.count())
        out = {
            "qa_status": "metadata_inspected",
            "driver": ds.driver,
            "width": ds.width,
            "height": ds.height,
            "band_count": ds.count,
            "crs": str(ds.crs) if ds.crs else None,
            "bounds": list(ds.bounds),
            "transform": list(ds.transform),
            "dtypes": list(ds.dtypes),
            "nodata": ds.nodata,
            "valid_pixel_count": valid_count,
            "masked_pixel_count": int(band.size - valid_count),
        }
        if valid_count:
            out["valid_min"] = float(band.min())
            out["valid_max"] = float(band.max())
        return out

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "files": {},
        "warnings": [
            "Satellite-derived flood frequency is not water depth.",
            "Flood extent is not observed building damage or monetary loss.",
            "The product covers its stated southern Pakistan study area and dates only.",
        ],
    }
    failed = False
    for filename, meta in FILES.items():
        path = OUT / filename
        if not path.exists():
            request = urllib.request.Request(meta["url"], headers={"User-Agent": "CRPA-data-audit/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as target:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    target.write(block)
        actual = md5(path)
        record = {
            "url": meta["url"],
            "description": meta["description"],
            "path": str(path.relative_to(ROOT)),
            "size_bytes": path.stat().st_size,
            "expected_md5": meta["md5"],
            "actual_md5": actual,
            "checksum_verified": actual.lower() == meta["md5"].lower(),
        }
        record.update(raster_metadata(path))
        manifest["files"][filename] = record
        if not record["checksum_verified"]:
            failed = True
            print(f"ERROR: checksum mismatch for {filename}: {actual}")
        else:
            print(f"OK: {filename} checksum verified ({path.stat().st_size:,} bytes)")
    manifest_path = OUT / "acquisition_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest: {manifest_path}")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
