"""Stage 2 - hazard connectors.

Priority per hazard:  local production data  ->  cache / free API  ->  synthetic fallback.
Every value carries a source label so the dashboard can show how much of a result is real data.

Source label convention (used for the confidence score):
    "Synthetic_*"            -> 0.0  (procedural demo data, NOT real hazard data)
    "A+B" (contains '+')     -> 0.5  (blend of real and synthetic)
    anything else            -> 1.0
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from . import config

HAZARDS = ["flood", "wind", "heat", "wildfire", "elevation"]

# Flood-zone -> design flood depth proxy (m) used by the fragility engine.
FLOOD_DEPTH_M = {"VE": 2.5, "V": 2.5, "AE": 1.5, "A": 1.2, "AO": 1.0, "AH": 1.0, "AR": 0.8,
                 "A99": 0.8, "X_SHADED": 0.3, "X": 0.0, "D": 0.2}

SCENARIOS = {
    # Parametric 2050 uplifts (NOT downscaled model output - see README "Limitations").
    "current": dict(label="Current climate", dT=0.0, wind=1.00, slr=0.00, fire=1.00),
    "ssp126": dict(label="SSP1-2.6 (2050)", dT=1.2, wind=1.02, slr=0.20, fire=1.05),
    "ssp585": dict(label="SSP5-8.5 (2050)", dT=2.2, wind=1.05, slr=0.30, fire=1.12),
}

# ----------------------------------------------------------------------------- cache
_cache_lock = threading.Lock()


def _cache_path(key: str) -> Path:
    return config.CACHE_DIR / (hashlib.sha1(key.encode()).hexdigest() + ".json")


def cache_get(key: str):
    p = _cache_path(key)
    try:
        d = json.loads(p.read_text())
        if time.time() - d["t"] < config.CACHE_TTL_DAYS * 86400:
            return d["v"]
    except Exception:
        pass
    return None


def cache_put(key: str, value) -> None:
    with _cache_lock:
        try:
            _cache_path(key).write_text(json.dumps({"t": time.time(), "v": value}))
        except Exception:
            pass


# ----------------------------------------------------------------------------- run context
@dataclass
class RunContext:
    """Per-run state: API circuit breakers so a dead API doesn't stall every asset."""
    offline: bool = config.OFFLINE
    fails: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def usable(self, api: str) -> bool:
        return not self.offline and self.fails.get(api, 0) < 3

    def ok(self, api: str):
        with self.lock:
            self.fails[api] = 0

    def fail(self, api: str):
        with self.lock:
            self.fails[api] = self.fails.get(api, 0) + 1

    def disabled_apis(self) -> list[str]:
        return [a for a, n in self.fails.items() if n >= 3]


def _get(ctx: RunContext, api: str, url: str, *, accept_statuses=(), **kw):
    if not ctx.usable(api):
        return None
    try:
        r = requests.get(url, timeout=config.HTTP_TIMEOUT, **kw)
        if r.status_code not in accept_statuses:
            r.raise_for_status()
        ctx.ok(api)
        return r
    except Exception:
        ctx.fail(api)
        return None


# ----------------------------------------------------------------------------- synthetic model
_COAST = [  # coarse US coastline polyline vertices: (lat, lon, basin) basin A = Atlantic/Gulf, P = Pacific/other
    *[(a, b, "A") for a, b in [
        (44.8, -66.95), (44.0, -69.0), (43.6, -70.2), (42.9, -70.8), (42.3, -70.9), (41.7, -70.0), (41.3, -71.5),
        (40.9, -72.5), (40.6, -74.0), (39.8, -74.1), (38.9, -74.9), (38.3, -75.1), (37.1, -75.9), (36.0, -75.6),
        (35.2, -75.5), (34.6, -76.6), (33.9, -77.9), (33.0, -79.2), (32.0, -80.8), (30.7, -81.4), (29.5, -81.1),
        (28.4, -80.6), (27.0, -80.1), (25.8, -80.1), (25.2, -80.4), (25.2, -81.1), (26.1, -81.8), (27.0, -82.3),
        (28.0, -82.8), (29.0, -83.0), (29.9, -84.0), (29.7, -85.1), (30.2, -86.5), (30.3, -87.5), (30.2, -88.5),
        (30.3, -89.4), (29.2, -89.3), (29.5, -90.6), (29.6, -92.0), (29.7, -93.8), (29.3, -94.7), (28.5, -96.2),
        (27.8, -97.2), (26.5, -97.2), (25.9, -97.3), (18.4, -66.1), (18.0, -67.1)]],
    *[(a, b, "P") for a, b in [
        (48.4, -124.7), (46.9, -124.1), (45.5, -124.0), (43.4, -124.4), (42.0, -124.3), (40.4, -124.4), (38.3, -123.0),
        (37.8, -122.5), (36.6, -121.9), (35.2, -120.8), (34.4, -120.5), (34.0, -118.5), (33.2, -117.4), (32.6, -117.1),
        (21.3, -157.9), (20.9, -156.5), (19.7, -155.0), (61.2, -149.9), (58.3, -134.4)]],
]
_COAST_LAT = np.array([c[0] for c in _COAST])
_COAST_LON = np.array([c[1] for c in _COAST])
_COAST_ATL = np.array([c[2] == "A" for c in _COAST])

# approximate mean state elevation (m), used only by the synthetic model
_STATE_ELEV = dict(AL=150, AK=580, AZ=1250, AR=200, CA=880, CO=2070, CT=150, DE=20, DC=30, FL=30, GA=180, HI=920,
                   ID=1520, IL=180, IN=230, IA=330, KS=610, KY=230, LA=30, ME=180, MD=100, MA=150, MI=270, MN=370,
                   MS=90, MO=240, MT=1030, NE=790, NV=1680, NH=310, NJ=80, NM=1740, NY=300, NC=210, ND=580, OH=260,
                   OK=400, OR=1000, PA=340, RI=60, SC=110, SD=670, TN=270, TX=520, UT=1860, VT=300, VA=290, WA=520,
                   WV=460, WI=320, WY=2040, PR=260)
_STATE_FIRE = dict(CA=55, OR=40, WA=30, ID=40, MT=38, CO=40, AZ=40, NM=38, UT=35, NV=25, WY=25, TX=12, FL=12,
                   OK=12, KS=8, SD=10, NE=8, AK=15, HI=12)


def _u(lat: float, lon: float, salt: str) -> float:
    """Deterministic pseudo-random in [0,1) from coordinates."""
    h = hashlib.sha1(f"{lat:.4f},{lon:.4f},{salt}".encode()).digest()
    return int.from_bytes(h[:6], "big") / float(1 << 48)


def _haversine_km(lat, lon, lats, lons):
    p = np.pi / 180
    a = (np.sin((lats - lat) * p / 2) ** 2
         + np.cos(lat * p) * np.cos(lats * p) * np.sin((lons - lon) * p / 2) ** 2)
    return 12742 * np.arcsin(np.sqrt(a))


def _coast_dist(lat, lon):
    """(min distance to any coast, to Atlantic/Gulf coast) in km - vertex-based, so approximate."""
    d = _haversine_km(lat, lon, _COAST_LAT, _COAST_LON)
    # densify: also compare against midpoints of consecutive vertices of the same basin
    mid_lat = (_COAST_LAT[:-1] + _COAST_LAT[1:]) / 2
    mid_lon = (_COAST_LON[:-1] + _COAST_LON[1:]) / 2
    same = _COAST_ATL[:-1] == _COAST_ATL[1:]
    dm = _haversine_km(lat, lon, mid_lat, mid_lon)
    dm = np.where(same, dm, 1e9)
    allm = np.concatenate([d, dm])
    atl = np.concatenate([np.where(_COAST_ATL, d, 1e9), np.where(_COAST_ATL[:-1] & same, dm, 1e9)])
    return float(allm.min()), float(atl.min())


def synthetic(lat: float, lon: float, state: str) -> dict:
    """Plausible but NOT real hazard values. Deterministic per coordinate. For demos/offline only."""
    coast, atl = _coast_dist(lat, lon)
    base = _STATE_ELEV.get(state, 300)
    elev = max(0.5, base * (1 - math.exp(-coast / 150)) + 2 + 6 * _u(lat, lon, "el"))

    p_sfha = min(0.85, 0.55 * math.exp(-coast / 40) + 0.05 + (0.15 if elev < 10 else 0))
    u = _u(lat, lon, "fl")
    if u < p_sfha * 0.15 and coast < 8:
        zone = "VE"
    elif u < p_sfha:
        zone = "AE"
    elif u < p_sfha + 0.12:
        zone = "X_SHADED"
    else:
        zone = "X"

    lat_f = min(1.0, max(0.3, (42 - lat) / 17))
    wind = 28 + 32 * math.exp(-atl / 150) * lat_f + 6 * (_u(lat, lon, "wi") - 0.5)

    heat = 44 - 0.35 * (lat - 25) + 3 * (_u(lat, lon, "he") - 0.5)
    if -118 < lon < -105 and lat < 37:
        heat += 4
    if coast < 40 and lon < -115:
        heat -= 8
    if atl < 25:
        heat -= 5
    heat = float(max(25, min(52, heat)))

    fire_base = _STATE_FIRE.get(state, 5)
    fire = fire_base + 15 * (_u(lat, lon, "fi") - 0.3) if fire_base > 5 else 3 + 4 * _u(lat, lon, "fi")
    fire = float(min(100, max(0, fire)))

    return dict(flood_zone=zone, wind_ms=round(wind, 1), heat_c=round(heat, 1),
                wildfire_score=round(fire, 1), elevation_m=round(elev, 1), coast_km=round(coast, 1))


# ----------------------------------------------------------------------------- local production data
def _fema_path(state: str) -> Path:
    return config.HAZARD_DIR / f"fema_nfhl_{state.upper()}.gpkg"


def local_flood(lat: float, lon: float, state: str):
    """Memory-safe point query on a FEMA NFHL GeoPackage using a tiny bbox read."""
    path = _fema_path(state)
    if not path.exists():
        return None
    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ImportError:
        return None
    try:
        eps = 0.001
        gdf = gpd.read_file(path, layer="S_FLD_HAZ_AR", bbox=(lon - eps, lat - eps, lon + eps, lat + eps))
        pt = Point(lon, lat)
        hit = gdf[gdf.geometry.contains(pt)]
        if hit.empty:
            return "X"
        zones = [str(z).upper().replace(" ", "") for z in hit["FLD_ZONE"]]
        for z in ("VE", "V", "AE", "AO", "AH", "A", "AR", "A99"):
            if z in zones:
                return z
        sub = " ".join(str(s) for s in hit.get("ZONE_SUBTY", []))
        return "X_SHADED" if "0.2" in sub else "X"
    except Exception:
        return None


def local_raster(name: str, lat: float, lon: float, nodata_default=None):
    """Read a WGS84 point from an optional local GeoTIFF, or skip if it does not cover it."""
    p = config.HAZARD_DIR / f"{name}.tif"
    if not p.exists() and name == "elevation_dem":
        lat0, lon0 = math.floor(lat), math.floor(lon)
        ns = "N" if lat0 >= 0 else "S"
        ew = "E" if lon0 >= 0 else "W"
        tile = (f"Copernicus_DSM_COG_30_{ns}{abs(lat0):02d}_00_"
                f"{ew}{abs(lon0):03d}_00_DEM.tif")
        p = config.HAZARD_DIR / "elevation_dem_tiles" / tile
    if not p.exists():
        return None
    try:
        import rasterio
        with rasterio.open(p) as src:
            if src.crs is None or src.crs.to_epsg() != 4326:
                return None
            if not (src.bounds.left <= lon <= src.bounds.right and src.bounds.bottom <= lat <= src.bounds.top):
                return None
            v = next(src.sample([(lon, lat)]))[0]
            if src.nodata is not None and v == src.nodata:
                return nodata_default
            return float(v)
    except Exception:
        return None


# ----------------------------------------------------------------------------- free APIs
def api_opentopo_elevation(ctx: RunContext, lat, lon):
    """Point elevation from OpenTopography's global Copernicus 30m DSM; requires a personal API key."""
    api_key = config.key("OPENTOPOGRAPHY_API_KEY")
    if not api_key:
        return None
    dataset = "COP30"
    cache_key = f"opentopo-elev:{dataset}:{lat:.4f},{lon:.4f}"
    if (v := cache_get(cache_key)) is not None:
        return v
    r = _get(ctx, "opentopography-elevation", "https://portal.opentopography.org/API/v1/elevation",
             accept_statuses=(404, 422), params={
                 "longitude": f"{lon:.4f}", "latitude": f"{lat:.4f}",
                 "dataset": dataset, "API_Key": api_key})
    if r is None or r.status_code in (404, 422):
        # These mean no point data / out-of-coverage, not a broken API.
        return None
    try:
        elevation = r.json().get("Elevation")
        if elevation is None:
            return None
        v = float(elevation)
        if not math.isfinite(v):
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    cache_put(cache_key, v)
    return v


def api_elevation(ctx: RunContext, lat, lon):
    key = f"elev:{lat:.4f},{lon:.4f}"
    if (v := cache_get(key)) is not None:
        return v
    r = _get(ctx, "open-meteo-elev", "https://api.open-meteo.com/v1/elevation",
             params={"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}"})
    if r is None:
        return None
    try:
        v = float(r.json()["elevation"][0])
    except Exception:
        return None
    cache_put(key, v)
    return v


def api_openmeteo_extremes(ctx: RunContext, lat, lon):
    """One request -> (10-yr max daily gust m/s, 10-yr max daily temp C). ERA5 reanalysis, ~10 km grid."""
    key = f"om:{lat:.1f},{lon:.1f}"
    if (v := cache_get(key)) is not None:
        return tuple(v)
    r = _get(ctx, "open-meteo-archive", "https://archive-api.open-meteo.com/v1/archive", params={
        "latitude": f"{lat:.3f}", "longitude": f"{lon:.3f}", "start_date": "2015-01-01", "end_date": "2024-12-31",
        "daily": "wind_gusts_10m_max,temperature_2m_max", "wind_speed_unit": "ms", "timezone": "UTC"})
    if r is None:
        return None
    try:
        d = r.json()["daily"]
        out = (float(np.nanmax(np.array(d["wind_gusts_10m_max"], dtype=float))),
               float(np.nanmax(np.array(d["temperature_2m_max"], dtype=float))))
    except Exception:
        return None
    cache_put(key, list(out))
    return out


def api_noaa_heat(ctx: RunContext, lat, lon):
    """Max TMAX (C) at the nearest GHCND station for 2024. Needs NOAA_CDO_TOKEN. Falls back silently."""
    token = config.key("NOAA_CDO_TOKEN")
    if not token:
        return None
    key = f"cdo:{lat:.2f},{lon:.2f}"
    if (v := cache_get(key)) is not None:
        return v
    h = {"token": token}
    base = "https://www.ncei.noaa.gov/cdo-web/api/v2"
    r = _get(ctx, "noaa-cdo", f"{base}/stations", headers=h, params={
        "datasetid": "GHCND", "datatypeid": "TMAX", "startdate": "2024-01-01", "enddate": "2024-12-31",
        "extent": f"{lat-0.5},{lon-0.5},{lat+0.5},{lon+0.5}", "limit": 25})
    if r is None:
        return None
    try:
        st = r.json().get("results", [])
        st = [s for s in st if s.get("maxdate", "") >= "2024-12-01"]
        if not st:
            return None
        s = min(st, key=lambda s: (s["latitude"] - lat) ** 2 + (s["longitude"] - lon) ** 2)
        r2 = _get(ctx, "noaa-cdo", f"{base}/data", headers=h, params={
            "datasetid": "GHCND", "datatypeid": "TMAX", "stationid": s["id"], "startdate": "2024-01-01",
            "enddate": "2024-12-31", "units": "metric", "limit": 1000})
        if r2 is None:
            return None
        vals = [x["value"] for x in r2.json().get("results", [])]
        if not vals:
            return None
        v = float(max(vals))
    except Exception:
        return None
    cache_put(key, v)
    return v


def api_firms(ctx: RunContext, lat, lon):
    """Active-fire detections (VIIRS, last 10 days, ~10 km box) -> 0-100 activity score. Needs NASA_FIRMS_KEY."""
    k = config.key("NASA_FIRMS_KEY")
    if not k:
        return None
    key = f"firms:{lat:.2f},{lon:.2f}:{time.strftime('%Y-%m-%d')}"
    if (v := cache_get(key)) is not None:
        return v
    d = 0.09
    url = (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{k}/VIIRS_SNPP_NRT/"
           f"{lon-d:.3f},{lat-d:.3f},{lon+d:.3f},{lat+d:.3f}/10")
    r = _get(ctx, "nasa-firms", url)
    if r is None:
        return None
    lines = [l for l in r.text.strip().splitlines() if l]
    if not lines or not lines[0].lower().startswith("latitude"):
        return None
    v = float(min(100, (len(lines) - 1) * 10))
    cache_put(key, v)
    return v


# ----------------------------------------------------------------------------- orchestration
def _extract_one(a: dict, ctx: RunContext) -> dict:
    lat, lon, st = a["lat"], a["lon"], a["state"]
    syn = synthetic(lat, lon, st)
    out = dict(asset_id=a["asset_id"], coast_km=syn["coast_km"])
    src = {}

    # FLOOD
    out["flood_depth_m_raw"] = None
    z = local_flood(lat, lon, st)
    if z:
        out["flood_zone"], src["flood"] = z, "FEMA_NFHL_Local"
    else:
        # This JRC product maps modeled river-flood depths; nodata inside its
        # global footprint means no mapped depth at that pixel, not no flood risk.
        d = local_raster("flood_depth_jrc_rp20y", lat, lon, nodata_default=0.0)
        if d is not None and d >= 0:
            out["flood_zone"], out["flood_depth_m_raw"] = ("JRC_RP20Y" if d > 0 else "X"), d
            src["flood"] = ("JRC_Global_FloodHazard_RP20Y_Local" if d > 0
                            else "JRC_RP20Y_NoMappedDepth_Local")
        else:
            out["flood_zone"], src["flood"] = syn["flood_zone"], "Synthetic_Flood"

    # ELEVATION
    v = local_raster("elevation_dem", lat, lon)
    if v is not None:
        out["elevation_m"], src["elevation"] = v, "Copernicus_COP90_DSM_Local"
    elif (v := api_opentopo_elevation(ctx, lat, lon)) is not None:
        out["elevation_m"], src["elevation"] = v, "OpenTopography_COP30_API"
    elif (v := api_elevation(ctx, lat, lon)) is not None:
        out["elevation_m"], src["elevation"] = v, "OpenMeteo_Elevation_API"
    else:
        out["elevation_m"], src["elevation"] = syn["elevation_m"], "Synthetic_Elevation"

    # WIND  (+ HEAT share one API call)
    om = None
    v = local_raster("wind_gust_max_ms", lat, lon)
    if v is not None:
        out["wind_ms"], src["wind"] = v, "Wind_Gust_Raster_Local"
    else:
        om = api_openmeteo_extremes(ctx, lat, lon)
        if om:
            out["wind_ms"], src["wind"] = om[0], "OpenMeteo_ERA5_API"
        else:
            out["wind_ms"], src["wind"] = syn["wind_ms"], "Synthetic_Wind"

    # HEAT
    # Only accept a temperature raster in degrees C; the legacy Heat.tif is a categorical U.S. map.
    v = local_raster("heat_max_c", lat, lon)
    if v is not None:
        out["heat_c"], src["heat"] = v, "Heat_MaxTemp_C_Local"
    elif (v := api_noaa_heat(ctx, lat, lon)) is not None:
        out["heat_c"], src["heat"] = v, "NOAA_CDO_API"
    else:
        om = om or api_openmeteo_extremes(ctx, lat, lon)
        if om:
            out["heat_c"], src["heat"] = om[1], "OpenMeteo_ERA5_API"
        else:
            out["heat_c"], src["heat"] = syn["heat_c"], "Synthetic_Heat"

    # WILDFIRE
    v = local_raster("wildfire_burn_prob", lat, lon)
    if v is not None:
        out["wildfire_score"], src["wildfire"] = min(100.0, v * 100 if v <= 1 else v), "Local_Wildfire_BurnProb_Raster"
    elif (v := api_firms(ctx, lat, lon)) is not None:
        out["wildfire_score"] = v
        src["wildfire"] = "NASA_FIRMS_Recent_Activity_API"
    else:
        out["wildfire_score"], src["wildfire"] = syn["wildfire_score"], "Synthetic_Wildfire"

    for h in HAZARDS:
        out[f"src_{h}"] = src[h]
    return out


def source_weight(label: str) -> float:
    if label.startswith("Synthetic"):
        return 0.0
    return 0.5 if "+" in label else 1.0


def apply_scenario(h: pd.DataFrame, scenario: str) -> pd.DataFrame:
    s = SCENARIOS[scenario]
    h = h.copy()
    h["heat_c"] = h["heat_c"] + s["dT"]
    h["wind_ms"] = h["wind_ms"] * s["wind"]
    h["wildfire_score"] = (h["wildfire_score"] * s["fire"]).clip(upper=100)
    depth = h["flood_zone"].map(FLOOD_DEPTH_M).fillna(0.0)
    if "flood_depth_m_raw" in h:
        depth = h["flood_depth_m_raw"].where(h["flood_depth_m_raw"].notna(), depth)
    h["flood_depth_m"] = depth + np.where(h["flood_zone"] != "X", s["slr"], 0.0)
    h = h.drop(columns=["flood_depth_m_raw"], errors="ignore")
    return h


def extract_hazards(assets: pd.DataFrame, scenario: str = "current", ctx: RunContext | None = None) -> tuple[pd.DataFrame, dict]:
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {list(SCENARIOS)}")
    ctx = ctx or RunContext()
    rows = assets[["asset_id", "lat", "lon", "state"]].to_dict("records")
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
        res = list(ex.map(lambda a: _extract_one(a, ctx), rows))
    h = pd.DataFrame(res)
    h = apply_scenario(h, scenario)
    w = np.mean([[source_weight(v) for v in h[f"src_{x}"]] for x in HAZARDS], axis=0)
    h["data_confidence"] = np.round(w, 3)
    meta = {
        "scenario": scenario,
        "scenario_label": SCENARIOS[scenario]["label"],
        "confidence": round(float(h["data_confidence"].mean()), 3),
        "apis_disabled_after_failures": ctx.disabled_apis(),
        "offline_mode": ctx.offline,
        "source_counts": {x: h[f"src_{x}"].value_counts().to_dict() for x in HAZARDS},
    }
    return h, meta


def confidence_band(c: float) -> str:
    return "Production" if c >= 0.8 else "Mixed" if c >= 0.3 else "Synthetic"


def layer_status() -> dict:
    """What local production data is present (for the dashboard Setup Wizard)."""
    fema = sorted(p.stem.replace("fema_nfhl_", "") for p in config.HAZARD_DIR.glob("fema_nfhl_*.gpkg"))
    elevation_tiles = list((config.HAZARD_DIR / "elevation_dem_tiles").glob("*.tif"))
    rasters = {n: (config.HAZARD_DIR / f"{n}.tif").exists()
               for n in ("flood_depth_jrc_rp20y", "elevation_dem", "wind_gust_max_ms", "heat_max_c", "wildfire_burn_prob")}
    rasters["elevation_dem"] = rasters["elevation_dem"] or bool(elevation_tiles)
    try:
        import geopandas  # noqa: F401
        gp = True
    except ImportError:
        gp = False
    try:
        import rasterio  # noqa: F401
        rio = True
    except ImportError:
        rio = False
    return {"fema_states": fema, "rasters": rasters, "elevation_dem_tiles": len(elevation_tiles),
            "geopandas": gp, "rasterio": rio,
            "keys": {k: bool(config.key(k)) for k in ("NOAA_CDO_TOKEN", "NASA_FIRMS_KEY",
                                                         "OPENTOPOGRAPHY_API_KEY", "NVIDIA_API_KEY")}}
