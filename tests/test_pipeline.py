import json
import os

os.environ["CRPA_OFFLINE"] = "1"

import pandas as pd
import pytest

from src import fragility, hazards, ingestion
from src.orchestrator import run_assessment

TEMPLATE = "data/templates/portfolio_upload_template.csv"


def test_money_parsing():
    assert ingestion.parse_money("50M") == 50e6
    assert ingestion.parse_money("$1,200,000") == 1.2e6
    assert ingestion.parse_money("2.5k") == 2500
    with pytest.raises(ValueError):
        ingestion.parse_money("lots")


def test_qa_checks():
    csv = ("asset_id,name,lat,lon,state,asset_class,replacement_value\n"
           "A1,Ok,25.76,-80.19,FL,office,1M\n"
           "A1,Dup id,26.1,-80.2,FL,office,1M\n"
           "A2,Null,0,0,FL,office,1M\n"
           "A3,Abroad,48.85,2.35,FL,office,1M\n"
           "A4,BadClass,30.1,-90.2,LA,castle,1M\n"
           "A5,BadState,30.1,-90.2,ZZ,office,1M\n"
           "A6,Mismatch,34.05,-118.24,FL,office,1M\n")
    r = ingestion.ingest(csv)
    checks = {i.check for i in r.issues}
    assert {"duplicate_id", "null_island", "out_of_bounds", "schema", "state_mismatch"} <= checks
    assert set(r.assets.asset_id) == {"A1", "A6"}


def test_missing_columns_and_limit():
    with pytest.raises(ValueError, match="missing required"):
        ingestion.ingest("a,b\n1,2\n")


def test_fragility_monotonic_and_zero():
    x = [0, 1, 2, 3]
    p = fragility.sigmoid_damage(x, 1.5, 1.8)
    assert p[0] == 0 and all(a <= b for a, b in zip(p, p[1:])) and p[-1] < 1


def test_synthetic_deterministic():
    assert hazards.synthetic(25.76, -80.19, "FL") == hazards.synthetic(25.76, -80.19, "FL")
    miami, denver = hazards.synthetic(25.76, -80.19, "FL"), hazards.synthetic(39.74, -104.99, "CO")
    assert miami["wind_ms"] > denver["wind_ms"] and miami["elevation_m"] < denver["elevation_m"]


def test_end_to_end(tmp_path):
    r = run_assessment(TEMPLATE, "current", use_llm=False, out_dir=tmp_path)
    assert r["summary"]["n_assets"] == 15
    assert r["meta"]["confidence"] == 0.0
    df = r["assets"]
    assert df.risk_score.between(0, 100).all() and (df.expected_loss_usd <= df.replacement_value).all()
    for f in ("csv", "geojson", "summary", "qa", "report_md", "report_json", "ai_log"):
        assert (tmp_path / r["files"][f]).exists()
    assert "SYNTHETIC" in r["report_md"]
    json.loads((tmp_path / "portfolio_risk_summary.json").read_text())


def test_scenarios_increase_risk(tmp_path):
    cur = run_assessment(TEMPLATE, "current", False, out_dir=tmp_path / "a")["summary"]["total_expected_loss_usd"]
    hot = run_assessment(TEMPLATE, "ssp585", False, out_dir=tmp_path / "b")["summary"]["total_expected_loss_usd"]
    assert hot > cur
