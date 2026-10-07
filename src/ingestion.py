"""Stage 1 - ingestion, validation (Pydantic v2) and spatial QA checks."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator

from .config import MAX_ASSETS

ASSET_CLASSES = [
    "office", "industrial", "retail", "residential", "hospital",
    "data_center", "infrastructure", "hotel", "other",
]
US_STATES = set(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
    "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR".split()
)
# Pakistan administrative regions accepted in the `state` column.
PAKISTAN_REGIONS = {
    "PUNJAB": "Punjab", "SINDH": "Sindh", "BALOCHISTAN": "Balochistan",
    "KHYBER PAKHTUNKHWA": "Khyber Pakhtunkhwa", "KPK": "Khyber Pakhtunkhwa", "KP": "Khyber Pakhtunkhwa",
    "GILGIT BALTISTAN": "Gilgit Baltistan", "GB": "Gilgit Baltistan",
    "AZAD JAMMU AND KASHMIR": "Azad Jammu and Kashmir", "AZAD KASHMIR": "Azad Jammu and Kashmir", "AJK": "Azad Jammu and Kashmir",
    "ISLAMABAD": "Islamabad Capital Territory", "ISLAMABAD CAPITAL TERRITORY": "Islamabad Capital Territory", "ICT": "Islamabad Capital Territory",
}
# Coarse national bounds; province boxes below are only QA warnings, not official borders.
US_BOUNDS = (17.5, 72.0, -180.0, -64.0)  # lat_min, lat_max, lon_min, lon_max
PAKISTAN_BOUNDS = (23.4, 37.2, 60.8, 77.9)
PAKISTAN_STATE_BOX = {
    "Punjab": (27.5, 34.0, 69.5, 75.5),
    "Sindh": (23.4, 28.8, 66.5, 71.5),
    "Balochistan": (24.5, 32.5, 60.8, 70.8),
    "Khyber Pakhtunkhwa": (31.0, 36.9, 69.0, 74.5),
    "Gilgit Baltistan": (35.0, 37.2, 72.0, 77.9),
    "Azad Jammu and Kashmir": (33.0, 35.2, 73.2, 75.5),
    "Islamabad Capital Territory": (33.4, 33.9, 72.7, 73.4),
}

ALIASES = {
    "id": "asset_id", "assetid": "asset_id", "asset": "asset_id",
    "asset_name": "name", "latitude": "lat", "longitude": "lon", "lng": "lon", "long": "lon",
    "st": "state", "class": "asset_class", "type": "asset_class", "asset_type": "asset_class",
    "replacement_val": "replacement_value", "replacement_cost": "replacement_value",
    "value": "replacement_value", "tiv": "replacement_value",
}
REQUIRED = ["asset_id", "name", "lat", "lon", "state", "asset_class", "replacement_value"]


def parse_money(v: Any) -> float:
    """Accepts 50000000, '50,000,000', '$50M', '2.5k', '1.2B'."""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("$", "").replace(",", "").replace("_", "").lower()
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*([kmb])?", s)
    if not m:
        raise ValueError(f"cannot parse replacement value '{v}'")
    mult = {"k": 1e3, "m": 1e6, "b": 1e9, None: 1.0}[m.group(2)]
    return float(m.group(1)) * mult


class Asset(BaseModel):
    asset_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    state: str
    asset_class: str
    replacement_value: float = Field(gt=0)

    @field_validator("asset_id", "name", mode="before")
    @classmethod
    def _strip(cls, v):
        return str(v).strip()

    @field_validator("state", mode="before")
    @classmethod
    def _state(cls, v):
        s = str(v).strip().upper().replace("-", " ")
        if s in US_STATES:
            return s
        if s in PAKISTAN_REGIONS:
            return PAKISTAN_REGIONS[s]
        raise ValueError(f"unknown supported US state or Pakistan region '{v}'")

    @field_validator("asset_class", mode="before")
    @classmethod
    def _cls(cls, v):
        s = str(v).strip().lower().replace(" ", "_").replace("-", "_")
        if s not in ASSET_CLASSES:
            raise ValueError(f"asset_class '{v}' not in {ASSET_CLASSES}")
        return s

    @field_validator("replacement_value", mode="before")
    @classmethod
    def _val(cls, v):
        return parse_money(v)


@dataclass
class QAIssue:
    severity: str  # "error" (row dropped) | "warning" (row kept)
    check: str
    row: int | None
    asset_id: str | None
    message: str


@dataclass
class IngestionResult:
    assets: pd.DataFrame
    issues: list[QAIssue] = field(default_factory=list)
    n_input: int = 0

    @property
    def n_valid(self) -> int:
        return len(self.assets)

    def summary(self) -> dict:
        checks: dict[str, int] = {}
        for i in self.issues:
            checks[i.check] = checks.get(i.check, 0) + 1
        return {
            "rows_in": self.n_input,
            "rows_valid": self.n_valid,
            "rows_rejected": self.n_input - self.n_valid,
            "issue_counts": checks,
            "issues": [i.__dict__ for i in self.issues],
        }


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [ALIASES.get(c.strip().lower().replace(" ", "_"), c.strip().lower().replace(" ", "_")) for c in df.columns]
    return df


def read_csv(source) -> pd.DataFrame:
    """source: path, bytes, str CSV text or file-like."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    elif isinstance(source, str) and "\n" in source:
        source = io.StringIO(source)
    return pd.read_csv(source, dtype=str, keep_default_na=False, skipinitialspace=True)


def ingest(source) -> IngestionResult:
    raw = _normalise_columns(read_csv(source) if not isinstance(source, pd.DataFrame) else source.astype(str))
    n_in = len(raw)
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}. Required: {REQUIRED}")
    if n_in == 0:
        raise ValueError("CSV has no rows")
    if n_in > MAX_ASSETS:
        raise ValueError(f"CSV has {n_in} rows; limit is {MAX_ASSETS} (set CRPA_MAX_ASSETS to change)")

    issues: list[QAIssue] = []
    good: list[dict] = []

    # --- schema validation (row level) ---
    for idx, rec in enumerate(raw[REQUIRED].to_dict("records")):
        try:
            good.append(Asset(**rec).model_dump() | {"_row": idx + 2})
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                issues.append(QAIssue("error", "schema", idx + 2, rec.get("asset_id"), f"{loc}: {err['msg']}"))

    df = pd.DataFrame(good)
    if df.empty:
        return IngestionResult(assets=pd.DataFrame(columns=REQUIRED), issues=issues, n_input=n_in)

    drop = set()

    # --- QA 1: null island ---
    for _, r in df[(df.lat.abs() < 0.5) & (df.lon.abs() < 0.5)].iterrows():
        issues.append(QAIssue("error", "null_island", r._row, r.asset_id, "coordinates are (0,0)"))
        drop.add(r.name)

    # --- QA 2: duplicates ---
    for _, r in df[df.duplicated("asset_id", keep="first")].iterrows():
        issues.append(QAIssue("error", "duplicate_id", r._row, r.asset_id, "duplicate asset_id"))
        drop.add(r.name)
    dup_loc = df[~df.index.isin(drop)].duplicated(["name", "lat", "lon"], keep="first")
    for i in dup_loc[dup_loc].index:
        r = df.loc[i]
        issues.append(QAIssue("error", "duplicate_asset", r._row, r.asset_id, "same name and coordinates as an earlier row"))
        drop.add(i)

    # --- QA 3: out of bounds (outside supported US and Pakistan coverage) ---
    us = df.lat.between(US_BOUNDS[0], US_BOUNDS[1]) & df.lon.between(US_BOUNDS[2], US_BOUNDS[3])
    pk = df.lat.between(PAKISTAN_BOUNDS[0], PAKISTAN_BOUNDS[1]) & df.lon.between(PAKISTAN_BOUNDS[2], PAKISTAN_BOUNDS[3])
    oob = df[~(us | pk)]
    for _, r in oob.iterrows():
        issues.append(QAIssue("error", "out_of_bounds", r._row, r.asset_id,
                              f"({r.lat}, {r.lon}) is outside supported US/Pakistan coverage"))
        drop.add(r.name)

    # --- QA 4: coordinate precision (warning) ---
    def _decimals(x: float) -> int:
        s = f"{x:.8f}".rstrip("0")
        return len(s.split(".")[1]) if "." in s else 0

    for _, r in df.iterrows():
        if _decimals(r.lat) < 2 and _decimals(r.lon) < 2:
            issues.append(QAIssue("warning", "coordinate_precision", r._row, r.asset_id,
                                  "coordinates have <2 decimals (~1 km precision); results will be coarse"))

    # --- QA 5: state vs coordinates (warning; rough lat/lon boxes for the contiguous 48) ---
    for _, r in df.iterrows():
        box = STATE_BOX.get(r.state) or PAKISTAN_STATE_BOX.get(r.state)
        if box and not (box[0] - 0.5 <= r.lat <= box[1] + 0.5 and box[2] - 0.5 <= r.lon <= box[3] + 0.5):
            issues.append(QAIssue("warning", "state_mismatch", r._row, r.asset_id,
                                  f"coordinates fall outside the rough extent of {r.state}"))

    # --- QA 6: asset class enum is enforced in schema validation ---
    out = df.drop(index=list(drop)).drop(columns="_row").reset_index(drop=True)
    return IngestionResult(assets=out, issues=issues, n_input=n_in)


# (lat_min, lat_max, lon_min, lon_max) - coarse extents, used for warnings only
STATE_BOX = {
    "AL": (30.1, 35.0, -88.5, -84.9), "AZ": (31.3, 37.0, -114.8, -109.0), "AR": (33.0, 36.5, -94.6, -89.6),
    "CA": (32.5, 42.0, -124.5, -114.1), "CO": (37.0, 41.0, -109.1, -102.0), "CT": (41.0, 42.1, -73.7, -71.8),
    "DE": (38.4, 39.9, -75.8, -75.0), "FL": (24.4, 31.0, -87.7, -80.0), "GA": (30.3, 35.0, -85.7, -80.8),
    "ID": (42.0, 49.0, -117.3, -111.0), "IL": (36.9, 42.6, -91.6, -87.0), "IN": (37.8, 41.8, -88.1, -84.8),
    "IA": (40.3, 43.5, -96.7, -90.1), "KS": (37.0, 40.0, -102.1, -94.6), "KY": (36.5, 39.2, -89.6, -81.9),
    "LA": (28.9, 33.1, -94.1, -88.8), "ME": (43.0, 47.5, -71.1, -66.9), "MD": (37.9, 39.8, -79.5, -75.0),
    "MA": (41.2, 42.9, -73.6, -69.9), "MI": (41.7, 48.3, -90.5, -82.1), "MN": (43.5, 49.4, -97.3, -89.5),
    "MS": (30.1, 35.0, -91.7, -88.1), "MO": (36.0, 40.7, -95.8, -89.1), "MT": (44.3, 49.0, -116.1, -104.0),
    "NE": (40.0, 43.0, -104.1, -95.3), "NV": (35.0, 42.0, -120.0, -114.0), "NH": (42.7, 45.3, -72.6, -70.6),
    "NJ": (38.9, 41.4, -75.6, -73.9), "NM": (31.3, 37.0, -109.1, -103.0), "NY": (40.5, 45.0, -79.8, -71.8),
    "NC": (33.8, 36.6, -84.4, -75.4), "ND": (45.9, 49.0, -104.1, -96.5), "OH": (38.4, 42.0, -84.8, -80.5),
    "OK": (33.6, 37.0, -103.0, -94.4), "OR": (42.0, 46.3, -124.6, -116.4), "PA": (39.7, 42.3, -80.5, -74.7),
    "RI": (41.1, 42.0, -71.9, -71.1), "SC": (32.0, 35.2, -83.4, -78.5), "SD": (42.5, 45.9, -104.1, -96.4),
    "TN": (34.9, 36.7, -90.3, -81.6), "TX": (25.8, 36.5, -106.7, -93.5), "UT": (37.0, 42.0, -114.1, -109.0),
    "VT": (42.7, 45.0, -73.5, -71.5), "VA": (36.5, 39.5, -83.7, -75.2), "WA": (45.5, 49.0, -124.8, -116.9),
    "WV": (37.2, 40.6, -82.7, -77.7), "WI": (42.5, 47.1, -92.9, -86.8), "WY": (41.0, 45.0, -111.1, -104.0),
    "DC": (38.7, 39.0, -77.2, -76.9),
}
