"""Download free Pakistan-wide screening rasters into data/hazards.

Sources:
- Copernicus DEM GLO-90 COG tiles on AWS (public, no API key).
- JRC Global Flood Hazard Map 20-year depth GeoTIFF (global, CC BY 4.0).

The Pakistan bounding box is used so the elevation mosaic also covers border
assets; the JRC file is kept at global extent because it is only about 64 MB.
"""
from __future__ import annotations

import concurrent.futures
import math
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HAZARD_DIR = ROOT / "data" / "hazards"
TILE_DIR = HAZARD_DIR / "elevation_dem_tiles"
BOUNDS = (60.8, 23.4, 77.9, 37.2)  # west, south, east, north; WGS84
DEM_BASE = "https://copernicus-dem-90m.s3.eu-central-1.amazonaws.com"
FLOOD_URL = "https://storage.googleapis.com/fao-gismgr-jrc-data/DATA/JRC/MAP/JRC.FLOOD.tif"


def tile_id(lat0: int, lon0: int) -> str:
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    return f"Copernicus_DSM_COG_30_{ns}{abs(lat0):02d}_00_{ew}{abs(lon0):03d}_00_DEM"


def download(url: str, target: Path) -> tuple[str, int]:
    if target.exists() and target.stat().st_size > 0:
        return "existing", target.stat().st_size
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "climate-risk-portfolio-assessor/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as out:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            shutil.copyfileobj(response, out, length=1024 * 1024)
        size = partial.stat().st_size
        with partial.open("rb") as file:
            signature = file.read(4)
        if size < 1024 or signature not in (b"II*\x00", b"MM\x00*"):
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"download is not a GeoTIFF ({size} bytes)")
        os.replace(partial, target)
        return "downloaded", size
    except urllib.error.HTTPError as exc:
        partial.unlink(missing_ok=True)
        if exc.code == 404:
            return "no_tile", 0
        raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def download_dem_tiles() -> list[Path]:
    west, south, east, north = BOUNDS
    jobs = []
    for lat0 in range(math.floor(south), math.ceil(north)):
        for lon0 in range(math.floor(west), math.ceil(east)):
            name = tile_id(lat0, lon0)
            jobs.append((f"{DEM_BASE}/{name}/{name}.tif", TILE_DIR / f"{name}.tif"))

    downloaded = existing = missing = total_bytes = 0
    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(download, url, path): path for url, path in jobs}
        for future in concurrent.futures.as_completed(futures):
            path = futures[future]
            try:
                status, size = future.result()
                total_bytes += size
                if status == "downloaded":
                    downloaded += 1
                elif status == "existing":
                    existing += 1
                else:
                    missing += 1
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
    print(f"Copernicus GLO-90 tiles: downloaded={downloaded}, existing={existing}, no tile={missing}")
    print(f"Tile storage: {total_bytes / (1024**2):.1f} MiB")
    if errors:
        raise RuntimeError("Tile download failed:\n" + "\n".join(errors[:10]))

    paths = sorted(TILE_DIR.glob("*.tif"))
    if not paths:
        raise RuntimeError("No Copernicus GLO-90 tiles are available for the Pakistan bounding box.")
    return paths


def mosaic_dem(paths: list[Path]) -> None:
    try:
        import rasterio
        from rasterio.merge import merge
    except ImportError as exc:
        raise RuntimeError("Rasterio is required. Install it with: pip install -r requirements-geo.txt") from exc

    dst = HAZARD_DIR / "elevation_dem.tif"
    partial = HAZARD_DIR / "elevation_dem.partial.tif"
    sources = [rasterio.open(path) for path in paths]
    try:
        first = sources[0]
        nodata = first.nodata
        array, transform = merge(
            sources,
            bounds=BOUNDS,
            res=first.res,
            nodata=nodata,
            dtype=first.dtypes[0],
        )
        profile = first.profile.copy()
        profile.update(
            driver="GTiff",
            height=array.shape[1],
            width=array.shape[2],
            transform=transform,
            crs=first.crs,
            nodata=nodata,
            compress="DEFLATE",
            predictor=2,
            tiled=True,
            blockxsize=512,
            blockysize=512,
            BIGTIFF="IF_SAFER",
        )
        with rasterio.open(partial, "w", **profile) as out:
            out.write(array)
            out.update_tags(
                source="Copernicus DEM GLO-90, 2023_1",
                product_type="Digital Surface Model",
                license="Copernicus DEM GLO-90 free and open license",
                coverage="Pakistan bounding box; EPSG:4326",
            )
    finally:
        for source in sources:
            source.close()
    os.replace(partial, dst)
    print(f"Elevation mosaic: {dst} ({dst.stat().st_size / (1024**2):.1f} MiB)")


def download_flood() -> None:
    dst = HAZARD_DIR / "flood_depth_jrc_rp20y.tif"
    status, size = download(FLOOD_URL, dst)
    if status == "no_tile":
        raise RuntimeError("JRC flood raster URL unexpectedly returned 404.")
    try:
        import rasterio
        with rasterio.open(dst) as src:
            if src.crs is None or src.crs.to_epsg() != 4326:
                raise RuntimeError(f"Expected a WGS84 flood raster, got {src.crs}.")
            if not (src.bounds.left <= BOUNDS[0] and src.bounds.right >= BOUNDS[2]
                    and src.bounds.bottom <= BOUNDS[1] and src.bounds.top >= BOUNDS[3]):
                raise RuntimeError(f"JRC raster does not cover Pakistan: {src.bounds}.")
            print(f"JRC flood raster: {src.width}x{src.height}, {src.res[0]} degrees, "
                  f"nodata={src.nodata}, {size / (1024**2):.1f} MiB ({status})")
    except ImportError:
        print(f"JRC flood raster downloaded ({size / (1024**2):.1f} MiB); Rasterio is required to validate it.")


def main() -> int:
    HAZARD_DIR.mkdir(parents=True, exist_ok=True)
    download_flood()
    mosaic_dem(download_dem_tiles())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
