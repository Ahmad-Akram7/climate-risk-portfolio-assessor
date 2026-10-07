"""Phase 2 flood loss engine.

The engine is intentionally conservative: it only expands a supplied flood
depth into return periods when the source declares that it is a return-period
layer. Otherwise it reports one supported event and marks tail metrics as
truncated. The vulnerability function is explicitly labelled fallback_screening
until a licensed or published, compatible function is configured.
"""
from __future__ import annotations

from datetime import date
import math

import numpy as np
import pandas as pd

RETURN_PERIODS = (10, 20, 50, 100, 200, 500)
ARCHETYPES = {
    "hospital": "HOSPITAL_RC",
    "data_center": "DATA_CENTER_RC",
    "industrial": "INDUSTRIAL_RC",
    "infrastructure": "INFRASTRUCTURE",
    "warehouse": "WAREHOUSE",
    "hotel": "HOTEL_RC",
}


def aep(return_period_years: int) -> float:
    if return_period_years <= 0:
        raise ValueError("return period must be positive")
    return 1.0 / return_period_years


def relative_depth(depth_m: float | None, first_floor_elevation_m: float | None) -> tuple[float | None, str]:
    if depth_m is None:
        return None, "UNAVAILABLE"
    if first_floor_elevation_m is None:
        return max(0.0, float(depth_m)), "GROUND_REFERENCED_NO_FFE"
    return max(0.0, float(depth_m) - float(first_floor_elevation_m)), "DEPTH_MINUS_USER_FFE"


def archetype(row: pd.Series) -> tuple[str, str]:
    explicit = str(row.get("construction_type") or "").strip()
    if explicit:
        return explicit.upper().replace(" ", "_"), "user_input"
    asset_class = str(row.get("asset_class") or "other").lower()
    return ARCHETYPES.get(asset_class, "GENERIC_SCREENING"), "inferred_from_asset_class"


def fallback_damage(relative_depth_m: float, archetype_name: str) -> dict[str, float | str]:
    """Documented monotonic screening ratios, not an engineering curve."""
    scale = {"HOSPITAL_RC": 1.15, "DATA_CENTER_RC": 1.10, "WAREHOUSE": 1.05}.get(archetype_name, 1.0)
    base = min(0.85, max(0.0, relative_depth_m) / 3.0) * scale
    return {
        "vulnerability_model_type": "fallback_screening",
        "damage_state": "none" if base == 0 else "slight" if base < .15 else "moderate" if base < .4 else "extensive" if base < .7 else "complete",
        "structural_damage_ratio": round(min(.85, base), 6),
        "contents_damage_ratio": round(min(.95, base * 1.25), 6),
        "equipment_damage_ratio": round(min(.95, base * 1.4), 6),
        "vulnerability_source": "CRPA documented fallback screening function",
    }


def _event_depth(base_depth: float, rp: int, source: str) -> float:
    # A single RP raster cannot be converted into other RPs without a fitted
    # frequency model. Keep only the event actually identified by the source.
    if "RP20" in source.upper() or "20Y" in source.upper():
        return base_depth if rp == 20 else float("nan")
    return base_depth if rp == 0 else float("nan")


def _aal(losses: list[tuple[int, float]]) -> float:
    # Integrate loss against AEP; include zero loss at AEP=1 and truncate tails.
    points = sorted([(1.0, 0.0)] + [(aep(rp), loss) for rp, loss in losses], reverse=True)
    return float(sum((p0 - p1) * (l0 + l1) / 2 for (p0, l0), (p1, l1) in zip(points, points[1:])))


def calculate(assets: pd.DataFrame, hazards: pd.DataFrame, source_meta: dict) -> tuple[pd.DataFrame, dict]:
    rows = []
    all_events = []
    for _, asset in assets.iterrows():
        h = hazards.loc[hazards.asset_id == asset.asset_id].iloc[0]
        src = str(h.get("src_flood", "UNAVAILABLE"))
        base_depth = float(h.get("flood_depth_m", 0.0)) if pd.notna(h.get("flood_depth_m")) else None
        ffe = asset.get("first_floor_elevation_m")
        if pd.isna(ffe):
            ffe = None
        arch, arch_method = archetype(asset)
        events = []
        for rp in RETURN_PERIODS:
            depth = _event_depth(base_depth, rp, src) if base_depth is not None else float("nan")
            if math.isnan(depth):
                continue
            rel, depth_method = relative_depth(depth, ffe)
            vuln = fallback_damage(rel or 0.0, arch)
            structure = float(asset.replacement_value) * vuln["structural_damage_ratio"]
            contents_value = asset.get("contents_value")
            equipment_value = asset.get("critical_equipment_value")
            contents = float(contents_value) * vuln["contents_damage_ratio"] if contents_value not in (None, "", np.nan) and not pd.isna(contents_value) else None
            equipment = float(equipment_value) * vuln["equipment_damage_ratio"] if equipment_value not in (None, "", np.nan) and not pd.isna(equipment_value) else None
            total = structure + (contents or 0.0) + (equipment or 0.0)
            event = {"return_period_years": rp, "aep": aep(rp), "depth_m": round(depth, 4), "relative_depth_m": round(rel or 0.0, 4), "loss_usd": round(total, 2), "structural_loss_usd": round(structure, 2), "contents_loss_usd": round(contents, 2) if contents is not None else None, "equipment_loss_usd": round(equipment, 2) if equipment is not None else None, "business_interruption_loss_usd": None, "duration_hours": None, "velocity_m_s": None, "source": src, "vulnerability_model_type": vuln["vulnerability_model_type"], "damage_state": vuln["damage_state"], "archetype": arch, "archetype_method": arch_method, "relative_depth_method": depth_method, "vertical_datum_uncertainty": True}
            events.append(event); all_events.append(event)
        if events:
            losses = [(e["return_period_years"], e["loss_usd"]) for e in events]
            rows.append({"asset_id": asset.asset_id, "flood_events": events, "flood_aal_usd": round(_aal(losses), 2), "flood_pml_100_usd": next((e["loss_usd"] for e in events if e["return_period_years"] == 100), None), "flood_pml_500_usd": next((e["loss_usd"] for e in events if e["return_period_years"] == 500), None), "flood_supported_return_periods": [e["return_period_years"] for e in events], "flood_tail_truncated": len(events) < len(RETURN_PERIODS), "flood_quality_gate": "SCREENING ONLY", "flood_provenance_date": date.today().isoformat()})
        else:
            rows.append({"asset_id": asset.asset_id, "flood_events": [], "flood_aal_usd": None, "flood_pml_100_usd": None, "flood_pml_500_usd": None, "flood_supported_return_periods": [], "flood_tail_truncated": True, "flood_quality_gate": "INSUFFICIENT DATA", "flood_provenance_date": date.today().isoformat()})
    result = pd.DataFrame(rows)
    meta = {"flood_engine": "CRPA-FLOOD-2.0-screening", "return_periods_requested": list(RETURN_PERIODS), "event_count": len(all_events), "aal_method": "trapezoidal integration over AEP-loss points with zero-loss AEP=1; tails truncated", "vulnerability_model_type": "fallback_screening", "vertical_datum_uncertainty": True, "duration_available": False, "velocity_available": False, "source": source_meta.get("source_counts", {}).get("flood", {})}
    return result, meta
