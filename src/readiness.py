"""What data CRPA found, what is missing, and what that does to accuracy.

Shown in the dashboard, the API and the report. Missing files name the exact path to add.
"""
from __future__ import annotations

from . import config
from .hazard_registry import source_weight
from .hazards import FLOOD_RETURN_PERIODS

# file stem -> (hazard, what it gives, what happens without it)
RASTERS = {
    "flood_depth_jrc_rp20y": ("flood", "20-year flood depth", "no real flood depth: flood falls back to synthetic demo values"),
    "elevation_dem": ("elevation", "ground elevation", "elevation comes from Open-Meteo (coarse) or an OpenTopography key"),
    "wind_gust_max_ms": ("wind", "peak wind gust", "wind comes from live Open-Meteo history when online, otherwise synthetic"),
    "heat_max_c": ("heat", "peak temperature", "heat comes from live Open-Meteo or NOAA when available, otherwise synthetic"),
    "wildfire_burn_prob": ("wildfire", "burn probability", "wildfire comes from NASA FIRMS (needs a key), otherwise synthetic"),
    "landslide_susceptibility": ("landslide", "landslide susceptibility class", "landslide is not assessed (never scored as low)"),
}
KEYS = {
    "NASA_FIRMS_KEY": "wildfire detections (https://firms.modaps.eosdis.nasa.gov/api/map_key/)",
    "NOAA_CDO_TOKEN": "US temperature records (https://www.ncdc.noaa.gov/cdo-web/token)",
    "OPENTOPOGRAPHY_API_KEY": "1 m to 30 m elevation (https://portal.opentopography.org/)",
    "OPEN_METEO_API_KEY": "commercial Open-Meteo use (https://open-meteo.com/en/pricing)",
}
KNOWN_DEFECTS = [
    "Damage functions are assumed, not calibrated or validated, so loss figures are withheld and scores are screening indices.",
    "Flood loss uses a simple depth-ratio fallback. Annual average loss needs at least three return-period rasters.",
    "Mapped flood depth is about 1 km and looks capped at 30 m. A site on a blank cell has no mapped depth, which is not proof of safety.",
    "Future scenarios apply fixed uplifts, and the climate delta uses one CMIP6 model, so there is no model spread.",
    "River discharge is an indicator, not a flood depth. Landslide and drought are indices with no damage function.",
]


def _alt_path(stem: str) -> str:
    return "landslide_susceptibility.tif or pakistan_landslide.tif" if stem == "landslide_susceptibility" else f"{stem}.tif"


def _raster_check(path, assets) -> str | None:
    """Return a problem with a present raster, or None when it looks usable."""
    try:
        import rasterio
    except ImportError:
        return "rasterio is not installed, so this file is ignored"
    try:
        with rasterio.open(path) as ds:
            if ds.crs is None or ds.crs.to_epsg() != 4326:
                return "not in WGS84 (EPSG:4326): reproject it, it is ignored until then"
            if assets is not None and len(assets):
                b = ds.bounds
                inside = int(((assets.lon >= b.left) & (assets.lon <= b.right) & (assets.lat >= b.bottom) & (assets.lat <= b.top)).sum())
                if inside == 0:
                    return "opens fine but covers none of your assets: upload a file for your region"
                if inside < len(assets):
                    return f"covers only {inside} of {len(assets)} assets: the rest use another source"
    except Exception as e:  # corrupt or unreadable file
        return f"cannot be read ({type(e).__name__}): download it again"
    return None


def readiness(meta: dict | None = None, assets=None) -> dict:
    """Items (ok, partial, missing), the most and least precise hazard inputs, and known defects."""
    items = []
    for stem, (hz, gives, without) in RASTERS.items():
        names = ["landslide_susceptibility", "pakistan_landslide"] if stem == "landslide_susceptibility" else [stem]
        found = next((config.HAZARD_DIR / f"{n}.tif" for n in names if (config.HAZARD_DIR / f"{n}.tif").exists()), None)
        if stem == "elevation_dem" and not found and any((config.HAZARD_DIR / "elevation_dem_tiles").glob("*.tif")):
            items.append(dict(hazard=hz, item=stem, status="ok", detail="elevation tiles found", fix=""))
            continue
        if found:
            problem = _raster_check(found, assets)
            items.append(dict(hazard=hz, item=stem, status="partial" if problem else "ok", detail=problem or f"{gives}: file found and readable",
                              fix=f"Replace data/hazards/{found.name}." if problem else ""))
        else:
            items.append(dict(hazard=hz, item=stem, status="missing", detail=f"Missing, so {without}.",
                              fix=f"Upload data/hazards/{_alt_path(stem)} (WGS84 GeoTIFF)."))
    have = [rp for rp in FLOOD_RETURN_PERIODS if (config.HAZARD_DIR / ("flood_depth_jrc_rp20y.tif" if rp == 20 else f"flood_depth_rp{rp:03d}.tif")).exists()]
    miss = [rp for rp in FLOOD_RETURN_PERIODS if rp not in have]
    ok_aal = len(have) >= 3
    items.append(dict(hazard="flood", item="flood_return_periods", status="ok" if ok_aal else "partial",
                      detail=f"Return periods found: {have or 'none'}." + ("" if ok_aal else " Annual average loss needs at least 3."),
                      fix="" if not miss else "Add " + ", ".join(f"data/hazards/flood_depth_rp{rp:03d}.tif" for rp in miss) + " for a fuller loss curve."))
    for k, gives in KEYS.items():
        items.append(dict(hazard="keys", item=k, status="ok" if config.key(k) else "missing",
                          detail=("Key set." if config.key(k) else f"Not set, so {gives.split(' (')[0]} is unavailable."),
                          fix="" if config.key(k) else f"Get a key: {gives.split('(')[1].rstrip(')')} then set {k} in .env."))
    out = dict(items=items, known_defects=KNOWN_DEFECTS, precise=None, weakest=None, coverage={})
    sc = (meta or {}).get("source_counts") or {}
    scores = {}
    for hz, counts in sc.items():
        n = sum(counts.values())
        if not n:
            continue
        w = sum(source_weight(lbl) * c for lbl, c in counts.items()) / n
        weak = sum(c for lbl, c in counts.items() if source_weight(lbl) == 0)
        scores[hz] = w
        out["coverage"][hz] = dict(sources=counts, quality=round(w, 2), unusable_pct=round(100 * weak / n))
    if scores:
        top, low = max(scores, key=scores.get), min(scores, key=scores.get)
        out["precise"] = dict(hazard=top, quality=round(scores[top], 2), sources=list(sc[top]))
        out["weakest"] = dict(hazard=low, quality=round(scores[low], 2), sources=list(sc[low]))
    return out


def readiness_markdown(r: dict) -> str:
    L = ["", "## Data coverage and known defects", ""]
    if r["precise"]:
        p, w = r["precise"], r["weakest"]
        L.append(f"The most precise input in this run is {p['hazard']} (source {', '.join(p['sources'])}, quality {p['quality']} of 1). "
                 f"The weakest is {w['hazard']} (source {', '.join(w['sources'])}, quality {w['quality']} of 1).")
        L.append("")
    todo = [i for i in r["items"] if i["status"] != "ok" and i["fix"]]
    if todo:
        L.append("To get a more accurate estimate, add the following:")
        L += ["", *[f"- {i['fix']} {i['detail']}" for i in todo], ""]
    L.append("Known defects of this software:")
    L += ["", *[f"- {d}" for d in r["known_defects"]], ""]
    return "\n".join(L)
