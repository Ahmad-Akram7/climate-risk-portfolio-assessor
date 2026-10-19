"""Check the local flood return-period rasters before trusting them.

Usage: python scripts/validate_rasters.py [portfolio.csv]

Reports CRS, grid, nodata share, whether the grids match, whether depth ever falls with a longer return period,
and (with a portfolio CSV) how many assets sit on a mapped cell or near one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parent.parent
HAZ = ROOT / "data" / "hazards"
RPS = (10, 20, 50, 100, 200, 500)


def path_for(rp: int) -> Path:
    return HAZ / ("flood_depth_jrc_rp20y.tif" if rp == 20 else f"flood_depth_rp{rp:03d}.tif")


def read(p: Path):
    with rasterio.open(p) as r:
        a = r.read(1).astype(float)
        if r.nodata is not None:
            a = np.where(a == r.nodata, np.nan, a)
        return a, r.crs, r.transform, r.bounds


def main() -> int:
    found = {rp: path_for(rp) for rp in RPS if path_for(rp).exists()}
    print("Return periods present:", sorted(found) or "none", "| missing:", [rp for rp in RPS if rp not in found])
    data = {}
    problems = 0
    for rp, p in found.items():
        a, crs, tr, b = read(p)
        data[rp] = (a, crs, tr)
        v = np.isfinite(a)
        print(f"RP{rp}: crs={crs.to_epsg()} shape={a.shape} valid={100 * v.mean():.1f}% max={np.nanmax(a):.2f} m "
              f"cells at max={int((a == np.nanmax(a)).sum())}")
        if crs.to_epsg() != 4326:
            print("  PROBLEM: not EPSG:4326, the app will skip this file")
            problems += 1
    ref = next(iter(data.values()), None)
    for rp, (a, crs, tr) in data.items():
        if ref and (a.shape != ref[0].shape or tr != ref[2]):
            print(f"PROBLEM: RP{rp} grid differs from the first raster")
            problems += 1
    order = sorted(data)
    for lo, hi in zip(order, order[1:]):
        both = np.isfinite(data[lo][0]) & np.isfinite(data[hi][0]) if data[lo][0].shape == data[hi][0].shape else None
        if both is None:
            continue
        drop = int((data[hi][0][both] < data[lo][0][both] - 0.01).sum())
        only_lo = int((np.isfinite(data[lo][0]) & ~np.isfinite(data[hi][0])).sum())
        print(f"RP{lo}->RP{hi}: shared={int(both.sum())} depth falls={drop} mapped at RP{lo} but not RP{hi}={only_lo}")
        problems += drop > 0
    if len(sys.argv) > 1 and data:
        df = pd.read_csv(sys.argv[1])
        a, crs, tr = data.get(20) or next(iter(data.values()))
        on = near = 0
        for _, x in df.iterrows():
            row, col = rasterio.transform.rowcol(tr, x.lon, x.lat)
            if not (0 <= row < a.shape[0] and 0 <= col < a.shape[1]):
                continue
            on += bool(np.isfinite(a[row, col]))
            win = a[max(row - 5, 0):row + 6, max(col - 5, 0):col + 6]
            near += bool(np.isfinite(win).any())
        print(f"Assets: {len(df)} | on a mapped cell: {on} | mapped flooding within ~5 km: {near}")
    print("Zero mapped depth means no mapped depth at that cell. It is not proof of no flood risk.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
