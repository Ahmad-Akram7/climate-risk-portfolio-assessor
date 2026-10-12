"""Streamlit dashboard.  Run:  streamlit run app/dashboard.py"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from src import config, fragility, hazards, viz
from src.hazard_registry import ALL_HAZARDS, HAZARDS, NOT_ASSESSED, SEVERITY_LEVELS
from src.orchestrator import run_assessment

TEMPLATE = ROOT / "data" / "templates" / "portfolio_upload_template.csv"
# Severity uses a neutral ramp; hue is reserved for hazard identity (see src/hazard_registry.py).
TIER_COLORS = viz.SEVERITY_COLORS

st.set_page_config(page_title="CRPA · Climate Risk Intelligence", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.stApp{background:#08111f;color:#e5edf7;color-scheme:dark}
.block-container{padding:2.5rem 3rem 4rem;max-width:1500px}
[data-testid="stSidebar"]{border-right:1px solid #203451;background:linear-gradient(180deg,#0d1b2f 0%,#091525 100%)}
[data-testid="stSidebar"] .block-container{padding:2rem 1.25rem}
h1,h2,h3{letter-spacing:-.035em}
h1{font-size:2.35rem!important;font-weight:750!important;color:#f4f8fc}
h2{color:#cfe0f5}
div[data-testid="stMetric"]{background:#102139;border:1px solid #244264;border-radius:14px;padding:16px 18px;box-shadow:0 8px 24px rgba(0,0,0,.2)}
div[data-testid="stMetricLabel"]{color:#a9bdd4;font-size:.78rem;font-weight:650;text-transform:uppercase;letter-spacing:.08em}
div[data-testid="stMetricValue"]{color:#f4f8fc;font-size:1.65rem;font-weight:750}
.crpa-hero{padding:1.4rem 1.6rem;margin:0 0 1.4rem;border:1px solid #2d5b93;border-radius:18px;background:linear-gradient(115deg,#102f56 0%,#173f87 62%,#1d4ed8 100%);color:#fff;box-shadow:0 14px 36px rgba(0,0,0,.28)}
.crpa-hero h1{color:#fff!important;margin:0 0 .3rem;font-size:2.2rem!important}
.crpa-hero p{color:#dbeafe;margin:0;font-size:1rem}
.section-label{color:#9db4cf;font-size:.76rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin:.7rem 0}
.status-card{border:1px solid #244264;border-radius:14px;padding:1rem 1.1rem;background:#102139;margin:.8rem 0}
.pill{display:inline-block;padding:4px 10px;border-radius:999px;font-size:.76rem;font-weight:700;background:#193e73;color:#bfdbfe}
.stButton>button,.stDownloadButton>button{border-radius:10px;font-weight:650;min-height:2.7rem}
.stTabs [data-baseweb="tab-list"]{gap:1.4rem;border-bottom:1px solid #203451}
.stTabs [data-baseweb="tab"]{font-weight:650;color:#9db4cf;padding:13px 2px}
.stTabs [aria-selected="true"]{color:#60a5fa}
@media (max-width: 800px){.block-container{padding:1.25rem 1rem 3rem}.crpa-hero h1{font-size:1.7rem!important}}
</style>""", unsafe_allow_html=True)
st.markdown(viz.CSS, unsafe_allow_html=True)


def usd(x: float) -> str:
    return f"${x/1e9:.2f}B" if x >= 1e9 else f"${x/1e6:.1f}M" if x >= 1e6 else f"${x:,.0f}"


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("<div style='font-size:1.45rem;font-weight:800;color:#f4f8fc'>◈ CRPA</div>", unsafe_allow_html=True)
    st.caption("Climate Risk Intelligence")
    st.markdown("<div class='section-label'>Assessment setup</div>", unsafe_allow_html=True)
    scenario = st.selectbox("Climate scenario", list(hazards.SCENARIOS),
                            format_func=lambda k: hazards.SCENARIOS[k]["label"])
    use_llm = st.toggle("Use AI report", value=bool(config.key("NVIDIA_API_KEY")),
                        help="Uses NVIDIA_API_KEY when enabled; deterministic reporting remains available.")
    up = st.file_uploader("Portfolio CSV", type="csv")
    use_template = st.checkbox("Use the demo template", value=up is None, disabled=up is not None)
    run = st.button("Run assessment", type="primary", use_container_width=True)
    st.download_button("Download CSV template", TEMPLATE.read_bytes(), "portfolio_upload_template.csv",
                       use_container_width=True)
    st.divider()
    res = st.session_state.get("result")
    if res:
        conf = res["meta"]["confidence"]
        band = hazards.confidence_band(conf)
        color = {"Production": "#15803d", "Mixed": "#b45309", "Synthetic": "#b91c1c"}[band]
        st.markdown(f"<div class='status-card'><div class='section-label'>Data confidence</div><strong style='color:{color}'>{band}</strong></div>", unsafe_allow_html=True)
        st.progress(conf, text=f"Confidence {conf:.2f} / 1.00")
    with st.expander("API keys (this session only)"):
        for k in ("NVIDIA_API_KEY", "NOAA_CDO_TOKEN", "NASA_FIRMS_KEY", "OPENTOPOGRAPHY_API_KEY"):
            v = st.text_input(k, type="password", value="", placeholder="set" if config.key(k) else "not set")
            if v:
                os.environ[k] = "".join(v.split())
        st.caption("Keys live in memory only. Put them in `.env` to persist.")

# ----------------------------------------------------------------------------- run
if run:
    src = up.getvalue() if up is not None else (TEMPLATE if use_template else None)
    if src is None:
        st.sidebar.error("Upload a CSV or tick the demo template.")
    else:
        bar = st.progress(0.0, text="Starting...")
        try:
            st.session_state["result"] = run_assessment(
                src, scenario, use_llm, progress=lambda s, f: bar.progress(f, text=s))
            bar.empty()
            st.rerun()
        except Exception as e:
            bar.empty()
            st.error(f"Assessment failed: {e}")

res = st.session_state.get("result")
st.markdown("<div class='crpa-hero'><h1>Climate Risk Portfolio Assessor</h1><p>Screen asset portfolios across flood, wind, heat and wildfire exposure with transparent source provenance.</p></div>", unsafe_allow_html=True)
tabs = st.tabs(["Overview", "Map", "Hazard Risk", "Assets", "AI Report", "Setup Wizard"])

if not res:
    with tabs[0]:
        st.info("Upload a portfolio CSV (or tick the demo template) in the sidebar and click **Run climate risk assessment**.")
        st.markdown("Required columns: `asset_id, name, lat, lon, state, asset_class, replacement_value`. "
                    "Values like `50M`, `2.5k` or `$1,200,000` are accepted.")
else:
    df: pd.DataFrame = res["assets"]
    s, meta = res["summary"], res["meta"]
    if meta["confidence"] < 0.3:
        st.warning("Hazard data is mostly **synthetic demo data**. Results illustrate the method only. "
                   "Add FEMA/DEM layers or API keys (Setup Wizard) for real inputs.")
    if s.get("hazards_not_assessed"):
        st.info("Not assessed (no data, which is not the same as low risk): "
                + ", ".join(HAZARDS[h].label for h in s["hazards_not_assessed"]) + ".")
    with tabs[0]:
        c = st.columns(4)
        c[0].metric("Assets", s["n_assets"])
        c[1].metric("Total value", usd(s["total_replacement_value_usd"]))
        c[2].metric("Avg risk score", s["mean_risk_score"] if s["mean_risk_score"] is not None else "n/a")
        c[3].metric("High + Critical", s["tier_counts"]["High"] + s["tier_counts"]["Critical"])
        c = st.columns(3)
        c[0].metric("Scenario expected loss", usd(s["total_expected_loss_usd"]),
                    f"{s['expected_loss_pct_of_value']}% of value", delta_color="off")
        c[1].metric("Value-weighted risk", s["value_weighted_risk_score"])
        c[2].metric("Low risk, verified", s["low_risk_verified_assets"],
                    help="Low rating backed by real data on every modelled hazard. Other Low ratings are unverified.")
        a, b = st.columns(2)
        pie = px.pie(names=list(s["tier_counts"]), values=list(s["tier_counts"].values()), hole=.55,
                     color=list(s["tier_counts"]), color_discrete_map=TIER_COLORS, title="Risk tiers")
        pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=40, b=0))
        a.plotly_chart(pie, use_container_width=True)
        hz = pd.DataFrame({"hazard": [HAZARDS[h].label for h in s["mean_hazard_probability"]],
                           "key": list(s["mean_hazard_probability"]),
                           "mean damage probability": list(s["mean_hazard_probability"].values())})
        bar = px.bar(hz, x="hazard", y="mean damage probability", title="Hazard mix (colour = hazard)", color="key",
                     color_discrete_map={h: HAZARDS[h].color for h in HAZARDS}, text_auto=".1%")
        bar.update_layout(showlegend=False)
        bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=40, b=0))
        b.plotly_chart(bar, use_container_width=True)
        with st.expander("Methodology"):
            st.markdown(
                "Each hazard intensity is converted to a damage probability with a sigmoid fragility curve "
                "(HAZUS-*inspired*, uncalibrated defaults in `src/fragility.py`). Hazards are combined with a survival "
                "model `P(any) = 1 - Π(1 - p_i)`, scaled by an asset-class criticality factor, and expected loss = "
                "probability × loss ratio × replacement value. Loss is **scenario-based**, not an annual expected loss. "
                "Drought (dry-spell length) and landslide are hazard-only indices with no damage function; they are "
                "shown on the Hazard Risk tab but are not part of the score or the loss. Severity: Low <25, Medium 25-49, "
                "High 50-74, Critical 75+ (screening thresholds). The score range is a ±15% hazard-intensity sensitivity, "
                "not a confidence interval.")
            st.dataframe(pd.DataFrame(fragility.CURVES).T[["col", "k", "x0", "max_loss", "unit"]])
        if res["qa"]["issue_counts"]:
            with st.expander(f"Data quality: {res['qa']['rows_valid']}/{res['qa']['rows_in']} rows valid, "
                             f"{len(res['qa']['issues'])} issue(s)"):
                st.dataframe(pd.DataFrame(res["qa"]["issues"]), use_container_width=True)
        st.caption(f"Processed in {res['elapsed_s']}s · outputs in `{res['out_dir']}`")

    with tabs[1]:
        opt = st.selectbox("Colour markers by", ["dominant"] + ALL_HAZARDS, format_func=lambda k: "Dominant hazard per asset" if k == "dominant" else HAZARDS[k].label)
        m = viz.map_frame(df, opt)
        layer = pdk.Layer("ScatterplotLayer", m, get_position=["lon", "lat"], get_fill_color="fill", get_line_color="line",
                          get_radius="size_px", radius_units="pixels", stroked=True, line_width_min_pixels=1.5,
                          pickable=True, opacity=1.0)
        view = pdk.ViewState(latitude=float(m.lat.mean()), longitude=float(m.lon.mean()), zoom=3.4)
        tip = {"html": "<b>{name_html}</b><br/>{detail_html}",
               "style": {"backgroundColor": "rgba(28,28,30,.9)", "color": "white", "borderRadius": "10px"}}
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tip,
                                 map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"))
        st.markdown(viz.legend_html(), unsafe_allow_html=True)
        st.caption("Marker colour identifies the hazard. Marker size shows severity (larger = more severe). "
                   "Hollow grey = no data for that hazard, which is not a low-risk finding.")

    with tabs[2]:
        st.markdown(viz.legend_html(), unsafe_allow_html=True)
        f1, f2 = st.columns(2)
        hz_sel = f1.multiselect("Hazards", ALL_HAZARDS, default=ALL_HAZARDS, format_func=lambda k: HAZARDS[k].label)
        sev_sel = f2.multiselect("Severity", SEVERITY_LEVELS + [NOT_ASSESSED], default=SEVERITY_LEVELS + [NOT_ASSESSED])
        flt = viz.filter_assets(df, hz_sel, sev_sel).sort_values("risk_score", ascending=False, na_position="last")
        st.caption(f"{len(flt)} of {len(df)} assets match the filters.")
        if hz_sel:
            cnt = pd.DataFrame([{"hazard": HAZARDS[h].label, "severity": sv, "assets": int((df[f"severity_{h}"] == sv).sum())}
                                for h in hz_sel for sv in SEVERITY_LEVELS + [NOT_ASSESSED]])
            ch = px.bar(cnt, x="hazard", y="assets", color="severity", title="Portfolio comparison: assets by severity and hazard",
                        color_discrete_map=TIER_COLORS, category_orders={"severity": SEVERITY_LEVELS + [NOT_ASSESSED]}, text_auto=True)
            ch.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=40, b=0), legend_title_text="Severity")
            ch.for_each_trace(lambda t: t.update(marker=dict(color="#0f172a", pattern=dict(shape="/", fgcolor="#94A3B8")))
                              if t.name == NOT_ASSESSED else None)  # hatched = no data, distinct from Low
            st.plotly_chart(ch, use_container_width=True)
        if len(flt):
            st.markdown(viz.matrix_html(flt.head(200), hz_sel or None), unsafe_allow_html=True)
            if len(flt) > 200:
                st.caption("Showing the 200 highest-scoring matches. Export the CSV for the full list.")
            pick = st.selectbox("Inspect an asset", flt["asset_id"] + " - " + flt["name"], key="inspect_asset")
            st.markdown(viz.asset_card_html(df[df["asset_id"] == pick.split(" - ")[0]].iloc[0]), unsafe_allow_html=True)
        else:
            st.info("No assets match the current filters.")

    with tabs[3]:
        cols = ["asset_id", "name", "state", "asset_class", "replacement_value", "risk_score", "risk_tier",
                "dominant_hazard", "overall_status", "expected_loss_usd", "p_flood", "p_wind", "p_wildfire", "p_heat"]
        st.dataframe(df[cols].sort_values("risk_score", ascending=False), use_container_width=True, hide_index=True,
                     column_config={"risk_score": st.column_config.ProgressColumn("risk_score", min_value=0, max_value=100),
                                    "replacement_value": st.column_config.NumberColumn(format="$%d"),
                                    "expected_loss_usd": st.column_config.NumberColumn(format="$%d")})
        st.download_button("Export CSV", df.to_csv(index=False), "asset_risk_scores.csv", "text/csv")
        st.caption("Per-hazard severity, confidence and an asset inspector are on the Hazard Risk tab.")

    with tabs[4]:
        mode = res["report_log"]["mode"]
        if meta["confidence"] < 0.3:
            st.warning("Synthetic data in use - do not use this report for disclosure.")
        if res["report_log"].get("error"):
            st.info("AI call failed, deterministic report shown instead: " + res["report_log"]["error"])
        st.caption(f"Report mode: {mode}")
        st.markdown(res["report_md"])
        a, b = st.columns(2)
        a.download_button("Download .md", res["report_md"], "portfolio_risk_report.md")
        b.download_button("Download .json", json.dumps({"markdown": res["report_md"], "summary": s, "data_meta": meta},
                                                       indent=2, default=str), "portfolio_risk_report.json")

with tabs[5]:
    st.subheader("Local hazard files (optional overrides)")
    ls = hazards.layer_status()
    st.write(("✅" if ls["fema_states"] else "⚪") + " FEMA NFHL GeoPackages: " +
             (", ".join(ls["fema_states"]) if ls["fema_states"] else
              "none found (U.S.-only; Pakistan uses `flood_depth_jrc_rp20y.tif` if installed)"))
    for n, ok in ls["rasters"].items():
        if n == "elevation_dem" and ls.get("elevation_dem_tiles"):
            st.write(f"✅ found {ls['elevation_dem_tiles']} Copernicus GLO-90 tiles")
        else:
            st.write(("✅ found" if ok else "⚪ optional") + f" `data/hazards/{n}.tif`")
    st.caption("A local raster is used only when it is WGS84 and covers the asset coordinate. The legacy `Heat.tif` is a U.S. categorical map, not temperature in °C; the pipeline uses `heat_max_c.tif` for local temperatures.")
    st.write(("✅" if ls["geopandas"] else "⚪") + " geopandas (needed for FEMA layers & .gpkg output)  ·  " +
             ("✅" if ls["rasterio"] else "⚪") + " rasterio (needed for local rasters)")
    st.subheader("Global sources")
    st.write("Open-Meteo historical reanalysis supplies wind gusts and maximum temperature for global coordinates; Open-Meteo also supplies global point elevation. OpenTopography COP30 adds global 30 m elevation when its API key is configured.")
    st.write("NASA FIRMS supplies recent global fire detections when `NASA_FIRMS_KEY` is configured. Without it, wildfire falls back to synthetic demo values.")
    st.caption("The JRC global flood layer is a modeled 20-year river-flood depth product at about 1 km; it is not an official Pakistan flood map.")
    st.subheader("API keys")
    for k, v in ls["keys"].items():
        st.write(("✅" if v else "⚪") + f" {k}")
    st.caption("Open-Meteo (elevation, wind gusts, max temp) needs no key. Offline mode: set CRPA_OFFLINE=1.")
    st.subheader("Smoke test")
    if st.button("Run pipeline on the demo template"):
        t = time.time()
        try:
            r = run_assessment(TEMPLATE, "current", False, out_dir=config.OUTPUT_DIR / "smoke")
            st.success(f"OK - {r['summary']['n_assets']} assets in {time.time()-t:.1f}s "
                       f"(confidence {r['meta']['confidence']:.2f})")
        except Exception as e:
            st.error(str(e))
