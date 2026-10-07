import pandas as pd

from src.flood_engine import aep, calculate, relative_depth


def test_aep_and_relative_depth():
    assert aep(100) == 0.01
    assert relative_depth(0.84, 0.42) == (0.42, "DEPTH_MINUS_USER_FFE")
    assert relative_depth(0.84, None) == (0.84, "GROUND_REFERENCED_NO_FFE")


def test_flood_engine_returns_supported_events_and_components():
    assets = pd.DataFrame([{
        "asset_id": "A1", "asset_class": "warehouse", "replacement_value": 1_000_000,
        "first_floor_elevation_m": 0.4, "contents_value": 200_000,
        "critical_equipment_value": 100_000,
    }])
    hazards = pd.DataFrame([{"asset_id": "A1", "flood_depth_m": 1.0, "src_flood": "JRC_RP20Y_Local"}])
    result, meta = calculate(assets, hazards, {"source_counts": {"flood": {"JRC_RP20Y_Local": 1}}})
    assert result.iloc[0]["flood_supported_return_periods"] == [20]
    assert result.iloc[0]["flood_aal_usd"] > 0
    assert bool(result.iloc[0]["flood_tail_truncated"])
    assert meta["vulnerability_model_type"] == "fallback_screening"
