import shutil
from pathlib import Path

from src import config
from src.orchestrator import run_assessment
from src.readiness import readiness

TEMPLATE = Path(__file__).resolve().parents[1] / "data" / "templates" / "portfolio_upload_template.csv"


def _by_item(r):
    return {i["item"]: i for i in r["items"]}


def test_missing_files_are_named(monkeypatch):
    monkeypatch.delenv("NASA_FIRMS_KEY", raising=False)
    it = _by_item(readiness())
    assert it["wind_gust_max_ms"]["status"] == "missing" and "data/hazards/wind_gust_max_ms.tif" in it["wind_gust_max_ms"]["fix"]
    assert "landslide_susceptibility.tif or pakistan_landslide.tif" in it["landslide_susceptibility"]["fix"]
    assert it["flood_return_periods"]["status"] == "partial" and "flood_depth_rp050.tif" in it["flood_return_periods"]["fix"]
    assert it["NASA_FIRMS_KEY"]["status"] == "missing" and "firms.modaps" in it["NASA_FIRMS_KEY"]["fix"]


def test_unreadable_raster_is_flagged_not_trusted():
    (config.HAZARD_DIR / "heat_max_c.tif").write_bytes(b"not a tiff")
    it = _by_item(readiness())["heat_max_c"]
    assert it["status"] == "partial" and "cannot be read" in it["detail"] or "rasterio" in it["detail"]


def test_report_lists_defects_and_what_to_add(tmp_path):
    r = run_assessment(TEMPLATE, "current", False, out_dir=tmp_path)
    assert "Data coverage and known defects" in r["report_md"] and "Known defects" in r["report_html"]
    assert r["meta"]["readiness"]["precise"] and r["meta"]["readiness"]["weakest"]
    assert any(i["status"] == "missing" for i in r["meta"]["readiness"]["items"])
    shutil.rmtree(tmp_path, ignore_errors=True)
