"""Conservative exposure enrichment.

This module records what is known about an asset without pretending that a
missing building attribute was observed. It does not invent footprints or
construction data; providers can be added behind this boundary later.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

SCHEMA_VERSION = "CRPA-asset-1.1"
OPTIONAL_EXPOSURE_FIELDS = [
    "address", "country", "province", "city", "postal_code", "occupancy",
    "contents_value", "business_interruption_value", "building_area_m2",
    "building_height_m", "stories", "year_built", "construction_type",
    "foundation_type", "roof_type", "wall_type", "first_floor_elevation_m",
    "basement", "basement_depth_m", "critical_equipment_value", "hvac_type",
    "backup_power", "flood_protection", "notes",
]


def _present(row: pd.Series, name: str) -> bool:
    value = row.get(name)
    return value is not None and str(value).strip().lower() not in {"", "nan", "none", "unknown"}


def _tier(row: pd.Series) -> str:
    known = sum(_present(row, name) for name in OPTIONAL_EXPOSURE_FIELDS)
    if known >= 10:
        return "ENHANCED"
    if known >= 3:
        return "SCREENING"
    return "SCREENING"


def enrich_assets(assets: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Add explicit completeness and provenance fields to validated assets."""
    df = assets.copy()
    for name in OPTIONAL_EXPOSURE_FIELDS:
        if name not in df:
            df[name] = None
    df["exposure_model_tier"] = df.apply(_tier, axis=1)
    df["exposure_known_fields"] = df.apply(
        lambda row: int(sum(_present(row, name) for name in OPTIONAL_EXPOSURE_FIELDS)), axis=1
    )
    df["exposure_completeness_pct"] = (100 * df["exposure_known_fields"] / len(OPTIONAL_EXPOSURE_FIELDS)).round(1)
    df["exposure_data_quality"] = df["exposure_completeness_pct"].apply(
        lambda x: "HIGH" if x >= 60 else "MEDIUM" if x >= 20 else "LOW"
    )
    meta = {
        "schema_version": SCHEMA_VERSION,
        "model_tier": "SCREENING",
        "exposure_fields_observed": OPTIONAL_EXPOSURE_FIELDS,
        "enrichment": "user supplied fields only; no building attributes were fabricated",
    }
    return df, meta
