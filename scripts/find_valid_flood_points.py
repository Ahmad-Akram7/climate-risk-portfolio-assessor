from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(__file__).resolve().parents[1]

RASTER = (
    ROOT
    / "data"
    / "hazards"
    / "flood"
    / "Europe_RP20_filled_depth.tif"
)


def main():
    with rasterio.open(RASTER) as src:
        print("Raster:", RASTER)
        print("Size:", src.width, "x", src.height)
        print("Bounds:", src.bounds)
        print("CRS:", src.crs)
        print("NoData:", src.nodata)

        found = 0

        # Process by raster blocks instead of loading the 21+ GB
        # uncompressed array into RAM.
        for _, window in src.block_windows(1):
            data = src.read(1, window=window)

            valid = (
                np.isfinite(data)
                & (data != src.nodata)
                & (data > 0)
            )

            rows, cols = np.where(valid)

            for row, col in zip(rows, cols):
                value = float(data[row, col])

                global_row = int(window.row_off + row)
                global_col = int(window.col_off + col)

                lon, lat = src.xy(global_row, global_col)

                print(
                    f"{lat:.6f},{lon:.6f},"
                    f"depth={value:.3f}m"
                )

                found += 1

                if found >= 100:
                    print()
                    print("Found 100 valid flood pixels.")
                    return

        print()
        print("Found:", found, "valid pixels.")


if __name__ == "__main__":
    main()