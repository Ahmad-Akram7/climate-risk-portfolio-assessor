"""Pipeline orchestrator + CLI:  python -m src.orchestrator portfolio.csv [--scenario ssp585] [--no-llm]"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import pandas as pd

from . import config, fragility, hazards, ingestion, reporting
from .flood_engine import calculate as calculate_flood
from .exposure import enrich_assets


def run_assessment(source, scenario: str = "current", use_llm: bool = True, frameworks: list[str] | None = None,
                   out_dir: str | Path | None = None, progress=None) -> dict:
    """Run all 4 stages. `source` = CSV path/bytes/text/DataFrame. Returns dict with results and output paths."""
    p = progress or (lambda stage, frac: None)
    t0 = time.time()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    out = Path(out_dir) if out_dir else config.OUTPUT_DIR / run_id
    out.mkdir(parents=True, exist_ok=True)

    p("Ingestion & QA", 0.05)
    ing = ingestion.ingest(source)
    if ing.n_valid == 0:
        raise ValueError("No valid assets after validation. See issues: " + json.dumps(ing.summary()["issues"][:5]))

    p("Exposure profile", 0.18)
    enriched, exposure_meta = enrich_assets(ing.assets)

    p("Hazard extraction", 0.25)
    haz, meta = hazards.extract_hazards(enriched, scenario)
    meta.update(exposure_meta)
    meta["quality_gate"] = "SCREENING ONLY" if meta["confidence"] < 0.8 else "LIMITED"

    flood, flood_meta = calculate_flood(enriched, haz, meta)
    meta["flood"] = flood_meta

    p("Fragility & risk scoring", 0.7)
    scored = fragility.score_assets(enriched, haz.merge(flood[["asset_id", "flood_damage_ratio"]], on="asset_id", how="left"))
    scored = scored.merge(flood, on="asset_id", how="left")
    summary = fragility.portfolio_summary(scored, meta)

    p("Report generation", 0.85)
    rep = reporting.generate_report(summary, meta, frameworks, use_llm)

    p("Writing outputs", 0.95)
    files = _write_outputs(out, scored, summary, meta, ing, rep)
    p("Done", 1.0)
    return dict(run_id=run_id, out_dir=str(out), assets=scored, summary=summary, meta=meta, qa=ing.summary(),
                report_md=rep["markdown"], report_log=rep["log"], files=files,
                elapsed_s=round(time.time() - t0, 2))


def _write_outputs(out: Path, scored: pd.DataFrame, summary: dict, meta: dict, ing, rep: dict) -> dict:
    f = {}
    scored.to_csv(out / "asset_risk_scores.csv", index=False)
    f["csv"] = "asset_risk_scores.csv"
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
              "properties": {k: (v if not hasattr(v, "item") else v.item()) for k, v in r.items() if k not in ("lat", "lon")}}
             for r in scored.to_dict("records")]
    (out / "asset_risk_scores.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, default=str))
    f["geojson"] = "asset_risk_scores.geojson"
    try:  # GeoPackage if geopandas is available
        import geopandas as gpd
        g = gpd.GeoDataFrame(scored, geometry=gpd.points_from_xy(scored.lon, scored.lat), crs="EPSG:4326")
        g.to_file(out / "asset_risk_scores.gpkg", driver="GPKG")
        f["gpkg"] = "asset_risk_scores.gpkg"
    except Exception:
        pass
    (out / "portfolio_risk_summary.json").write_text(json.dumps({"summary": summary, "data_meta": meta}, indent=2, default=str))
    (out / "qa_report.json").write_text(json.dumps(ing.summary(), indent=2, default=str))
    (out / "portfolio_risk_report.md").write_text(rep["markdown"])
    (out / "portfolio_risk_report.json").write_text(json.dumps(
        {"markdown": rep["markdown"], "summary": summary, "data_meta": meta}, indent=2, default=str))
    (out / "ai_report_log.json").write_text(json.dumps(rep["log"], indent=2, default=str))
    f.update(summary="portfolio_risk_summary.json", qa="qa_report.json", report_md="portfolio_risk_report.md",
             report_json="portfolio_risk_report.json", ai_log="ai_report_log.json")
    return f


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Climate Risk Portfolio Assessor")
    ap.add_argument("csv", help="portfolio CSV")
    ap.add_argument("--scenario", default="current", choices=list(hazards.SCENARIOS))
    ap.add_argument("--no-llm", action="store_true", help="use deterministic report only")
    ap.add_argument("--out", help="output directory (default outputs/<run-id>)")
    a = ap.parse_args(argv)
    try:
        r = run_assessment(a.csv, a.scenario, not a.no_llm, out_dir=a.out,
                           progress=lambda s, f: print(f"[{f:4.0%}] {s}", file=sys.stderr))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    s = r["summary"]
    print(f"\nAssets: {s['n_assets']}  Value: ${s['total_replacement_value_usd']:,.0f}  "
          f"Expected loss: ${s['total_expected_loss_usd']:,.0f}  Mean score: {s['mean_risk_score']}  "
          f"Tiers: {s['tier_counts']}")
    print(f"Data confidence: {r['meta']['confidence']} ({hazards.confidence_band(r['meta']['confidence'])})  "
          f"Report mode: {r['report_log']['mode']}  Time: {r['elapsed_s']}s")
    print(f"Outputs: {r['out_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
