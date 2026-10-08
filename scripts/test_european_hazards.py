from pathlib import Path

import pandas as pd
import rasterio
import numpy as np


ROOT = Path(__file__).resolve().parents[1]

FLOOD_DIR = ROOT / "data" / "hazards" / "flood"
WILDFIRE = ROOT / "data" / "hazards" / "wildfire" / "severity_2025.tiff"

PORTFOLIO = ROOT / "data" / "templates" / "europe_demo_north.csv"
OUTPUT = ROOT / "outputs" / "europe_hazard_raw_test.csv"


RASTERS = {
    "flood_rp20_m": FLOOD_DIR / "Europe_RP20_filled_depth.tif",
    "flood_rp100_m": FLOOD_DIR / "Europe_RP100_filled_depth.tif",
    "flood_rp500_m": FLOOD_DIR / "Europe_RP500_filled_depth.tif",
    "wildfire_severity_2025": WILDFIRE,
}


def sample_raster(path, lat, lon):
    with rasterio.open(path) as src:
        # All current rasters are EPSG:4326.
        row, col = src.index(lon, lat)

        if not (0 <= row < src.height and 0 <= col < src.width):
            return None

        value = src.read(1, window=((row, row + 1), (col, col + 1)))[0, 0]

        if src.nodata is not None and value == src.nodata:
            return None

        if not np.isfinite(value):
            return None

        return float(value)


def main():
    df = pd.read_csv(PORTFOLIO)

    for name, raster in RASTERS.items():
        print(f"Sampling {name}...")
        df[name] = [
            sample_raster(raster, row.lat, row.lon)
            for row in df.itertuples()
        ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)

    print()
    print("Saved:")
    print(OUTPUT)
    print()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
