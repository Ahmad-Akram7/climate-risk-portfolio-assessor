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
    assert result.iloc[0]["flood_aal_usd"] is None or pd.isna(result.iloc[0]["flood_aal_usd"])
    assert result.iloc[0]["flood_event_return_period"] == 20 and result.iloc[0]["flood_event_loss_usd"] > 0
    assert bool(result.iloc[0]["flood_tail_truncated"])
    assert meta["vulnerability_model_type"] == "fallback_screening"


def test_aal_matches_analytic_trapezoid():
    from src.flood_engine import _aal
    # losses 10, 20, 50 at RP 10, 100, 500; hand-computed trapezoids over AEP 1 -> 0.1 -> 0.01 -> 0.002
    expected = (0.9 * (0 + 10) / 2) + (0.09 * (10 + 20) / 2) + (0.008 * (20 + 50) / 2)
    assert abs(_aal([(10, 10.0), (100, 20.0), (500, 50.0)]) - expected) < 1e-9


def test_calculate_uses_all_supplied_return_period_depths():
    assets = pd.DataFrame([{"asset_id": "A1", "asset_class": "warehouse", "replacement_value": 1_000_000}])
    hz = pd.DataFrame([{"asset_id": "A1", "flood_depth_m": 1.0, "src_flood": "JRC_Global_FloodHazard_RP20Y_Local",
                        "flood_depth_m_rp010": 0.5, "flood_depth_m_rp020": 1.0, "flood_depth_m_rp100": 2.0}])
    r, _ = calculate(assets, hz, {})
    row = r.iloc[0]
    assert row["flood_supported_return_periods"] == [10, 20, 100]
    assert row["flood_aal_usd"] is not None and row["flood_aal_usd"] > 0
    assert row["flood_event_return_period"] == 100


def test_flood_rp_depths_reads_each_raster(monkeypatch):
    from src import hazards
    seen = {"flood_depth_rp010": 0.4, "flood_depth_rp100": 2.5}
    monkeypatch.setattr(hazards, "local_raster", lambda name, lat, lon, nodata_default=None: seen.get(name))
    out = hazards.flood_rp_depths(30.0, 70.0, 1.0)
    assert out == {"flood_depth_m_rp020": 1.0, "flood_depth_m_rp010": 0.4, "flood_depth_m_rp100": 2.5}


def test_aal_bounds_bracket_and_tail_is_explicit():
    from src.flood_engine import _aal, _aal_tail_flat
    losses = [(10, 10.0), (100, 20.0), (500, 50.0)]
    assert abs(_aal_tail_flat(losses) - 0.002 * 50.0) < 1e-12
    assert _aal(losses) + _aal_tail_flat(losses) > _aal(losses)
    assert abs(_aal(losses) + _aal_tail_flat(losses) - (_aal(losses) + 0.1)) < 1e-12
