# Local hazard files

Put optional hazard rasters here. They are not committed to git because they are large.

Each file must be a WGS84 (EPSG:4326) GeoTIFF that covers your assets. The app looks for these exact names:

flood_depth_jrc_rp20y.tif, elevation_dem.tif, wind_gust_max_ms.tif, heat_max_c.tif, wildfire_burn_prob.tif, landslide_susceptibility.tif

FEMA flood zones go here as fema_nfhl_<STATE>.gpkg. The Setup tab in the dashboard lists which files it found.

Flood return periods: RP20 is `flood_depth_jrc_rp20y.tif`. Other return periods use `flood_depth_rp010.tif`, `flood_depth_rp050.tif`, `flood_depth_rp100.tif`, `flood_depth_rp200.tif` and `flood_depth_rp500.tif`. Annual average loss is reported only with at least three of these.
