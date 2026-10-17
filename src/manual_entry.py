"""Manual asset entry: place lookup (Open-Meteo geocoding, no key for non-commercial use) and row cleanup.

The form and the editable table both build a DataFrame that goes through the same `ingestion.ingest` checks as an
uploaded CSV, so manual rows get exactly the same validation.
"""
from __future__ import annotations

import pandas as pd
import requests

from . import config
from .hazards import openmeteo_url
from .ingestion import ASSET_CLASSES, PAKISTAN_REGIONS, REQUIRED, US_STATES

US_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY",
    "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "puerto rico": "PR",
}
PAKISTAN_NAMES = sorted(set(PAKISTAN_REGIONS.values()))
STATE_OPTIONS = PAKISTAN_NAMES + sorted(US_STATES)
OPTIONAL_FORM_FIELDS = ["contents_value", "first_floor_elevation_m", "year_built", "construction_type"]
ENTRY_COLUMNS = REQUIRED + OPTIONAL_FORM_FIELDS


def to_state(admin1: str | None, country_code: str | None) -> str | None:
    """Map a geocoder region name to a value the `state` column accepts, or None if unsupported."""
    a = (admin1 or "").strip()
    cc = (country_code or "").upper()
    if cc == "US":
        return US_STATE_NAMES.get(a.lower())
    if cc == "PK":
        key = a.upper().replace("-", " ")
        if key in PAKISTAN_REGIONS:
            return PAKISTAN_REGIONS[key]
        if "ISLAMABAD" in key:
            return PAKISTAN_REGIONS["ISLAMABAD"]
    return None


def geocode(query: str, count: int = 5) -> tuple[list[dict], str | None]:
    """Look up a place name. Returns (results, error). Each result has label, lat, lon, state (or None), country."""
    q = (query or "").strip()
    if len(q) < 2:
        return [], "Type at least two letters of a place name."
    if config.OFFLINE:
        return [], "Offline mode is on (CRPA_OFFLINE=1). Enter latitude and longitude by hand."
    url, extra = openmeteo_url("geocoding", "/v1/search")
    try:
        r = requests.get(url, params={"name": q, "count": count, "language": "en", "format": "json", **extra},
                         timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        raw = r.json().get("results") or []
    except Exception:
        return [], "Place lookup is not reachable right now. Enter latitude and longitude by hand."
    out = []
    for x in raw:
        try:
            lat, lon = float(x["latitude"]), float(x["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        parts = [x.get("name"), x.get("admin1"), x.get("country")]
        out.append({"label": ", ".join(p for p in parts if p), "lat": round(lat, 5), "lon": round(lon, 5),
                    "state": to_state(x.get("admin1"), x.get("country_code")), "country": x.get("country_code")})
    return out, (None if out else "No place found. Try a larger nearby city.")


def blank_rows(n: int = 3) -> pd.DataFrame:
    """Empty editable table: text columns as strings, numeric columns as floats so the editor shows number inputs."""
    df = pd.DataFrame({c: pd.Series([None] * n, dtype="object") for c in ENTRY_COLUMNS})
    for c in ("lat", "lon", "replacement_value", "contents_value", "first_floor_elevation_m", "year_built"):
        df[c] = pd.Series([None] * n, dtype="float64")
    return df


def rows_to_dataframe(rows: pd.DataFrame | list[dict]) -> pd.DataFrame:
    """Clean editor output: drop empty rows, number unnamed assets, turn missing cells into empty strings."""
    df = pd.DataFrame(rows).copy()
    for c in ENTRY_COLUMNS:
        if c not in df:
            df[c] = None
    df = df[ENTRY_COLUMNS]
    blank = df.apply(lambda r: all(pd.isna(v) or str(v).strip() == "" for v in r), axis=1)
    df = df[~blank].reset_index(drop=True)
    for i in df.index:
        if pd.isna(df.at[i, "asset_id"]) or not str(df.at[i, "asset_id"]).strip():
            df.at[i, "asset_id"] = f"M-{i + 1:03d}"
    for c in ("lat", "lon", "replacement_value", "contents_value", "first_floor_elevation_m", "year_built"):
        df[c] = df[c].map(lambda v: "" if pd.isna(v) else (f"{v:.0f}" if c in ("year_built", "replacement_value", "contents_value") else repr(float(v))))
    return df.fillna("").astype(str)


def asset_class_options() -> list[str]:
    return list(ASSET_CLASSES)
