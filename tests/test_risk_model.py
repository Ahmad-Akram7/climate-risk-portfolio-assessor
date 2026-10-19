"""Tests for the layered risk model, missing-data handling, ingestion edge cases and presentation helpers."""
import os

os.environ["CRPA_OFFLINE"] = "1"

import numpy as np
import pandas as pd
import pytest

from src import fragility, hazards, ingestion, viz
from src.hazard_registry import ALL_HAZARDS, DAMAGE_HAZARDS, HAZARDS, source_weight


def _assets(**over):
    base = {"asset_id": "A1", "name": "Plant", "lat": 25.76, "lon": -80.19, "state": "FL", "asset_class": "office", "replacement_value": 1_000_000.0}
    return pd.DataFrame([{**base, **over}])


def _haz(**over):
    base = {"asset_id": "A1", "flood_zone": "AE", "flood_depth_m": 1.5, "elevation_m": 10.0, "wind_ms": 40.0,
            "heat_c": 40.0, "wildfire_score": 10.0, "drought_cdd_days": np.nan, "landslide_index": np.nan,
            "src_flood": "FEMA_NFHL_Local", "src_wind": "Wind_Gust_Raster_Local", "src_heat": "Heat_MaxTemp_C_Local",
            "src_wildfire": "Local_Wildfire_BurnProb_Raster", "src_drought": "Unavailable", "src_landslide": "Unavailable"}
    return pd.DataFrame([{**base, **over}])


# ---------------------------------------------------------------- the original crash
def test_flood_without_return_period_events_does_not_crash_or_score_zero():
    """flood_damage_ratio is all-NaN when the flood engine has no events. Must fall back to the depth curve, not 0."""
    h = _haz()
    h["flood_damage_ratio"] = None
    out = fragility.score_assets(_assets(), h).iloc[0]
    assert out["p_flood"] > 0
    assert out["status_flood"] == "assessed"


def test_flood_engine_ratio_is_not_scaled_by_max_loss_twice():
    h = _haz()
    h["flood_damage_ratio"] = 0.175  # half of flood max_loss 0.35
    out = fragility.score_assets(_assets(), h).iloc[0]
    assert out["p_flood"] == pytest.approx(0.5, abs=1e-3)
    assert out["vuln_flood"] == pytest.approx(0.175, abs=1e-3)  # loss ratio equals the engine ratio


# ---------------------------------------------------------------- missing data vs low risk
def test_missing_hazard_is_not_assessed_not_low():
    out = fragility.score_assets(_assets(), _haz()).iloc[0]
    for hz in ("drought", "landslide"):
        assert out[f"status_{hz}"] == "not_assessed"
        assert out[f"severity_{hz}"] == "Not assessed"
        assert pd.isna(out[f"confidence_{hz}"])
    assert out["dominant_hazard"] in DAMAGE_HAZARDS + ["none"]


def test_nan_intensity_excluded_from_combined_score():
    full = fragility.score_assets(_assets(), _haz()).iloc[0]
    part = fragility.score_assets(_assets(), _haz(wind_ms=np.nan)).iloc[0]
    assert part["status_wind"] == "not_assessed" and part["overall_status"] == "partial"
    assert part["risk_score"] <= full["risk_score"]  # a missing hazard adds no risk, but is flagged, not silently zero
    assert not part["low_risk_verified"]


def test_all_hazards_missing_gives_not_assessed_tier():
    h = _haz(wind_ms=np.nan, heat_c=np.nan, wildfire_score=np.nan, flood_depth_m=np.nan)
    out = fragility.score_assets(_assets(), h).iloc[0]
    assert out["risk_tier"] == "Not assessed" and out["overall_status"] == "not_assessed"
    assert out["dominant_hazard"] == "not_assessed"
    assert fragility.tier(float("nan")) == "Not assessed"


def test_synthetic_input_is_illustrative_and_never_verified_low():
    h = _haz(src_flood="Synthetic_Flood", src_wind="Synthetic_Wind", src_heat="Synthetic_Heat",
             src_wildfire="Synthetic_Wildfire", flood_depth_m=0.0, wind_ms=25.0, heat_c=30.0, wildfire_score=1.0)
    out = fragility.score_assets(_assets(), h).iloc[0]
    assert out["overall_status"] == "illustrative"
    assert out["risk_tier"] == "Low" and not out["low_risk_verified"]


def test_real_data_low_risk_is_verified():
    h = _haz(flood_zone="X", flood_depth_m=0.0, wind_ms=25.0, heat_c=30.0, wildfire_score=1.0)
    out = fragility.score_assets(_assets(), h).iloc[0]
    assert out["risk_tier"] == "Low" and out["overall_status"] == "assessed" and bool(out["low_risk_verified"])


# ---------------------------------------------------------------- layers and scoring properties
def test_layers_are_separate_columns_and_consistent():
    out = fragility.score_assets(_assets(asset_class="hospital"), _haz()).iloc[0]
    for hz in DAMAGE_HAZARDS:
        for k in ("hazard_index", "vuln", "risk", "loss"):
            assert (f"{k}_{hz}" if k != "loss" else f"loss_{hz}_usd") in out.index
        assert out[f"risk_{hz}"] == pytest.approx(min(100, out[f"hazard_index_{hz}"] * out["criticality"]), abs=0.15)
    assert out["criticality"] == 1.5


def test_score_monotonic_in_hazard_and_within_bounds():
    scores = [fragility.score_assets(_assets(), _haz(wind_ms=w)).iloc[0]["risk_score"] for w in (20, 40, 60, 80)]
    assert scores == sorted(scores) and all(0 <= s <= 100 for s in scores)


def test_sensitivity_range_brackets_score():
    out = fragility.score_assets(_assets(), _haz(wind_ms=55.0)).iloc[0]
    assert out["risk_score_low"] <= out["risk_score"] <= out["risk_score_high"]


def test_expected_loss_never_exceeds_value():
    h = _haz(wind_ms=90.0, heat_c=60.0, wildfire_score=100.0, flood_depth_m=6.0)
    out = fragility.score_assets(_assets(asset_class="hospital"), h).iloc[0]
    assert 0 < out["expected_loss_usd"] <= out["replacement_value"]


def test_index_hazards_use_hazard_index_and_stay_out_of_loss():
    base = fragility.score_assets(_assets(), _haz()).iloc[0]
    dry = fragility.score_assets(_assets(), _haz(drought_cdd_days=180.0, src_drought="OpenMeteo_ERA5_API",
                                                 landslide_index=80.0, src_landslide="Local_Landslide_Susceptibility_Raster")).iloc[0]
    assert dry["severity_drought"] == "Critical" and dry["severity_landslide"] == "Critical"
    assert dry["risk_score"] == base["risk_score"] and dry["expected_loss_usd"] == base["expected_loss_usd"]


# ---------------------------------------------------------------- hazard layer
def test_cdd_counts_longest_dry_run_per_year():
    dates = pd.date_range("2020-01-01", "2021-12-31")
    p = np.full(len(dates), 5.0)
    p[10:25] = 0.0   # 15 dry days in 2020
    p[400:430] = 0.2  # 30 dry days in 2021
    assert hazards.mean_annual_max_cdd(dates, p) == pytest.approx(22.5)
    assert hazards.mean_annual_max_cdd(dates[:100], p[:100]) is None  # too few valid days


def test_slr_only_at_coastal_sites():
    h = pd.DataFrame({"asset_id": ["coastal", "inland"], "flood_zone": ["AE", "AE"], "elevation_m": [2.0, 2.0],
                      "coast_km": [3.0, 900.0], "coast_km_valid": [True, True], "heat_c": [40.0, 40.0], "wind_ms": [30.0, 30.0],
                      "wildfire_score": [5.0, 5.0], "flood_depth_m_raw": [np.nan, np.nan]})
    out = hazards.apply_scenario(h, "ssp585")
    assert list(out["slr_applied"]) == [True, False]
    assert out.loc[0, "flood_depth_m"] == pytest.approx(1.5 + 0.30) and out.loc[1, "flood_depth_m"] == pytest.approx(1.5)


def test_source_weight_rubric():
    assert source_weight("Synthetic_Flood") == 0.0
    assert source_weight("Unavailable") == 0.0
    assert source_weight("JRC_RP20Y_NoMappedDepth_Local") < source_weight("JRC_Global_FloodHazard_RP20Y_Local")
    assert source_weight("OpenMeteo_ERA5_API") < 1.0
    assert source_weight("FEMA_NFHL_Local+Synthetic_Flood") <= 0.5


# ---------------------------------------------------------------- ingestion edge cases
def test_blank_optional_cells_do_not_reject_rows():
    csv = ("asset_id,name,lat,lon,state,asset_class,replacement_value,contents_value,year_built,basement\n"
           "A1,Ok,25.76,-80.19,FL,office,1M,,,\n"
           "A2,Ok2,25.77,-80.19,FL,office,1M,100k,1999.0,yes\n")
    r = ingestion.ingest(csv)
    assert r.n_valid == 2 and not r.issues
    assert r.assets.set_index("asset_id").loc["A2", "contents_value"] == 100_000


@pytest.mark.parametrize("col,val", [("contents_value", "-5"), ("year_built", "1066"), ("lat", "nan")])
def test_bad_optional_or_coordinate_values_rejected(col, val):
    row = {"asset_id": "A1", "name": "N", "lat": "25.76", "lon": "-80.19", "state": "FL", "asset_class": "office",
           "replacement_value": "1M", "contents_value": "", "year_built": ""}
    row[col] = val
    r = ingestion.ingest(pd.DataFrame([row]))
    assert r.n_valid == 0 and r.issues[0].check == "schema"


# ---------------------------------------------------------------- presentation helpers
def test_html_escapes_user_supplied_text():
    out = fragility.score_assets(_assets(name='<img src=x onerror=alert(1)>'), _haz()).iloc[0]
    for html in (viz.asset_card_html(out), viz.matrix_html(pd.DataFrame([out]))):
        assert "<img" not in html and "&lt;img" in html
    assert "<img" not in viz.map_frame(pd.DataFrame([out])).iloc[0]["name_html"]


def test_badges_distinguish_no_data_from_low():
    low, nodata, ill = viz.severity_badge("Low"), viz.severity_badge("Not assessed", "not_assessed"), viz.severity_badge("Low", "illustrative")
    assert "No data" in nodata and "Low" not in nodata
    assert "illustrative" in ill.lower() and "illustrative" not in low.lower()


def test_legend_lists_every_hazard_with_text_code():
    html = viz.legend_html()
    for h in ALL_HAZARDS:
        assert HAZARDS[h].code in html and HAZARDS[h].color in html


def test_hazard_colors_are_unique():
    assert len({s.color for s in HAZARDS.values()}) == len(HAZARDS)


def test_filter_assets_by_hazard_and_severity():
    df = pd.concat([fragility.score_assets(_assets(asset_id="A1"), _haz(asset_id="A1", wind_ms=80.0)),
                    fragility.score_assets(_assets(asset_id="A2"), _haz(asset_id="A2", wind_ms=20.0))], ignore_index=True)
    assert list(viz.filter_assets(df, ["wind"], ["High", "Critical"]).asset_id) == ["A1"]
    assert len(viz.filter_assets(df, ["drought"], ["Not assessed"])) == 2
    assert len(viz.filter_assets(df, [], ["Low"])) == 0


def test_map_frame_marks_no_data_hollow_and_size_tracks_severity():
    df = fragility.score_assets(_assets(), _haz(wind_ms=80.0))
    sev_row = viz.map_frame(df, "wind").iloc[0]
    none_row = viz.map_frame(df, "drought").iloc[0]
    assert none_row["fill"][3] == 0 and none_row["size_px"] < sev_row["size_px"]
    assert sev_row["fill"][:3] == [0x94, 0xA3, 0xB8]  # wind hazard colour


def test_vulnerability_registry_covers_every_curve_and_blocks_unsupported_status():
    from src import fragility
    from src.vulnerability_registry import REGISTRY, check_registry, overall_status
    assert {e["hazard"] for e in REGISTRY} >= set(fragility.CURVES)
    assert check_registry() == [] and overall_status() == "experimental"
    REGISTRY.append({"function_id": "x", "hazard": "flood", "validation_status": "empirically_validated", "validation_reference": None})
    try:
        assert check_registry() != []
    finally:
        REGISTRY.pop()
