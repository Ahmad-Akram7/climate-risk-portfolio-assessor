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
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components

from src import config, fragility, hazards, ingestion, manual_entry, viz
from src.data_sources import SERVICES
from src.hazard_registry import (
    ALL_HAZARDS,
    DAMAGE_HAZARDS,
    HAZARDS,
    NOT_ASSESSED,
    SEVERITY_LEVELS,
)
from src.orchestrator import run_assessment
from src.readiness import readiness

TEMPLATE = ROOT / "data" / "templates" / "portfolio_upload_template.csv"
BRAND = config.brand()
BRAND_COLOR = BRAND["color"] if len(BRAND["color"]) == 7 and BRAND["color"].startswith("#") else "#1d4ed8"
SOURCE_MODES = ["Demo portfolio", "Upload CSV", "Enter manually"]

st.set_page_config(page_title=f"{BRAND['name']} · Climate risk", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
st.markdown(f"""
<style>
:root{{--bg:#0b1220;--surface:#111c2f;--surface2:#15243b;--line:#243a58;--text:#e8eef7;--muted:#9fb2c8;--brand:{BRAND_COLOR};--focus:#93c5fd}}
.stApp{{background:var(--bg);color:var(--text);color-scheme:dark}}
.block-container{{padding:1.6rem 2.2rem 4rem;max-width:1380px}}
[data-testid="stSidebar"]{{background:#0d1626;border-right:1px solid var(--line)}}
[data-testid="stSidebar"] .block-container{{padding:1.4rem 1.1rem}}
h1,h2,h3{{letter-spacing:-.02em;color:#f3f7fc}}
.hero{{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:.6rem 1.5rem;padding:1.1rem 1.4rem;margin-bottom:1.2rem;border:1px solid var(--line);border-left:5px solid var(--brand);border-radius:14px;background:linear-gradient(120deg,#111c2f,#13233d)}}
.hero h1{{margin:0;font-size:1.55rem!important}}.hero p{{margin:.15rem 0 0;color:var(--muted)}}
.hero .tag{{font-size:.78rem;color:var(--muted);border:1px solid var(--line);padding:.25rem .7rem;border-radius:999px}}
.brand-mark{{font-size:1.25rem;font-weight:800;color:#fff}}.brand-mark span{{color:var(--brand)}}
.section-label{{color:var(--muted);font-size:.72rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin:.9rem 0 .35rem}}
div[data-testid="stMetric"]{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem}}
div[data-testid="stMetricLabel"]{{color:var(--muted);font-size:.74rem;font-weight:650;text-transform:uppercase;letter-spacing:.07em}}
div[data-testid="stMetricValue"]{{color:#fff;font-size:1.5rem;font-weight:750}}
.stButton>button,.stDownloadButton>button,[data-testid="stLinkButton"] a{{border-radius:10px;font-weight:650;min-height:2.75rem}}
.stButton>button:focus-visible,input:focus-visible,[role=tab]:focus-visible,a:focus-visible{{outline:3px solid var(--focus)!important;outline-offset:2px}}
.stTabs [data-baseweb="tab-list"]{{gap:1.2rem;border-bottom:1px solid var(--line);overflow-x:auto}}
.stTabs [data-baseweb="tab"]{{font-weight:650;color:var(--muted);padding:.8rem .15rem;min-height:2.75rem}}
.stTabs [aria-selected="true"]{{color:#fff}}
.card{{border:1px solid var(--line);border-radius:14px;background:var(--surface);padding:1rem 1.1rem;margin:.5rem 0}}
.steps{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.8rem;margin:.6rem 0 1.2rem}}
.step{{border:1px solid var(--line);border-radius:14px;background:var(--surface);padding:1rem 1.1rem}}
.step b.n{{display:inline-grid;place-items:center;width:1.7rem;height:1.7rem;border-radius:50%;background:var(--brand);color:#fff;font-size:.85rem;margin-bottom:.4rem}}
.step h4{{margin:.1rem 0 .25rem;font-size:1rem}}.step p{{margin:0;color:var(--muted);font-size:.9rem}}
.svc{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:.8rem}}
.svc .card h4{{margin:0 0 .2rem;font-size:1rem}}.svc .card p{{margin:.15rem 0;color:var(--muted);font-size:.86rem}}
.pill{{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.74rem;font-weight:700;border:1px solid var(--line)}}
.pill.on{{border-color:#22c55e;color:#bbf7d0}}.pill.off{{color:var(--muted)}}
@media (max-width:800px){{.block-container{{padding:1rem .9rem 3rem}}.hero h1{{font-size:1.25rem!important}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important}}}}
</style>""", unsafe_allow_html=True)
st.markdown(viz.CSS, unsafe_allow_html=True)


def usd(x: float) -> str:
    return f"${x/1e9:.2f}B" if x >= 1e9 else f"${x/1e6:.1f}M" if x >= 1e6 else f"${x:,.0f}"


# ----------------------------------------------------------------------------- charts
def chart_style(fig: go.Figure, height: int = 320, title: str | None = None) -> go.Figure:
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", size=13, color="#cfe0f5"),
                      margin=dict(l=4, r=12, t=44 if title else 8, b=8),
                      title=dict(text=title, font=dict(size=15, color="#f3f7fc"), x=0, xanchor="left") if title else None,
                      hoverlabel=dict(bgcolor="#0b1220", font_size=13), legend=dict(orientation="h", y=-0.18, x=0, title_text=""))
    fig.update_xaxes(gridcolor="#1b3350", zeroline=False, linecolor="#243a58")
    fig.update_yaxes(showgrid=False, linecolor="#243a58")
    return fig


def chart_severity(s: dict) -> go.Figure:
    order = SEVERITY_LEVELS + [NOT_ASSESSED]
    hs = s["hazard_summary"]
    labels = [HAZARDS[h].label for h in ALL_HAZARDS]
    fig = go.Figure()
    for sv in order:
        vals = [hs[h]["status_counts"]["not_assessed"] if sv == NOT_ASSESSED else hs[h]["severity_counts"][sv] for h in ALL_HAZARDS]
        marker = dict(color="#0f172a", pattern=dict(shape="/", fgcolor="#94A3B8")) if sv == NOT_ASSESSED else dict(color=viz.SEVERITY_COLORS[sv])
        fig.add_trace(go.Bar(y=labels, x=vals, name=sv, orientation="h", marker=marker,
                             text=[str(v) if v else "" for v in vals], textposition="inside", insidetextanchor="middle",
                             textfont=dict(color="#0b1220" if sv in ("High", "Critical") else "#f3f7fc"),
                             hovertemplate="%{y}: %{x} assets, " + sv + "<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.35, uniformtext=dict(minsize=11, mode="hide"))
    fig.update_traces(textangle=0)
    fig.update_yaxes(autorange="reversed")
    return chart_style(fig, 330, "Assets by severity, per hazard")


def chart_loss(s: dict) -> go.Figure:
    if not s.get("loss_publication", {}).get("allowed", s.get("total_expected_loss_usd") is not None):
        fig = go.Figure()
        fig.add_annotation(text="Withheld: damage functions are experimental and not empirically validated",
                           x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=14))
        return chart_style(fig, 330, "Financial loss estimates withheld")
    items = sorted(((h, s["hazard_summary"][h]["scenario_loss_usd"] or 0.0) for h in DAMAGE_HAZARDS), key=lambda x: x[1])
    fig = go.Figure(go.Bar(y=[HAZARDS[h].label for h, _ in items], x=[v for _, v in items], orientation="h",
                           marker_color=[HAZARDS[h].color for h, _ in items], text=[usd(v) for _, v in items],
                           textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{text}<extra></extra>"))
    fig.update_layout(bargap=0.4)
    fig.update_xaxes(showticklabels=False, showgrid=False)
    return chart_style(fig, 330, "Scenario loss by hazard")


def chart_top(df: pd.DataFrame, n: int = 8) -> go.Figure:
    top = df.dropna(subset=["risk_score"]).sort_values("risk_score", ascending=False).head(n).iloc[::-1]
    cols = [HAZARDS[h].color if h in HAZARDS else "#64748B" for h in top["dominant_hazard"]]
    fig = go.Figure(go.Bar(y=top["name"], x=top["risk_score"], orientation="h", marker_color=cols,
                           text=top["risk_score"].round(0).astype(int), textposition="outside", cliponaxis=False,
                           customdata=top["dominant_hazard"], hovertemplate="%{y}: score %{x:.0f}, main hazard %{customdata}<extra></extra>"))
    fig.update_layout(bargap=0.35)
    fig.update_xaxes(range=[0, 105], title_text="Risk score (bar colour = main hazard)")
    return chart_style(fig, max(260, 44 * len(top) + 70), f"Highest-risk assets (top {len(top)})")


# ----------------------------------------------------------------------------- manual entry
def _use_place(place: dict):
    st.session_state["f_lat"], st.session_state["f_lon"] = place["lat"], place["lon"]
    if place["state"] in manual_entry.STATE_OPTIONS:
        st.session_state["f_state"] = place["state"]
    if not st.session_state.get("f_name"):
        st.session_state["f_name"] = place["label"].split(",")[0] + " site"


def manual_panel():
    if "manual_df" not in st.session_state:
        st.session_state["manual_df"] = manual_entry.blank_rows(0)
    st.markdown("### Enter your assets")
    st.caption("Add one asset at a time with the form, or edit the table directly. Everything goes through the same checks as a CSV upload.")
    with st.expander("1. Find a place (fills latitude and longitude)", expanded=True):
        c1, c2 = st.columns([3, 1])
        q = c1.text_input("Place name", key="geo_q", placeholder="For example: Lahore, or Houston Texas")
        if c2.button("Search", use_container_width=True, key="geo_btn"):
            st.session_state["geo"] = manual_entry.geocode(q)
        results, err = st.session_state.get("geo", ([], None))
        if err:
            st.info(err)
        if results:
            idx = st.selectbox("Matches", range(len(results)), format_func=lambda i: results[i]["label"] + ("" if results[i]["state"] else "  (outside supported US/Pakistan coverage)"))
            st.button("Use this place in the form", on_click=_use_place, args=(results[idx],), key="geo_use")
    with st.form("add_asset"):
        st.markdown("**2. Describe the asset**")
        c1, c2 = st.columns(2)
        name = c1.text_input("Asset name *", key="f_name")
        cls = c2.selectbox("Asset type *", manual_entry.asset_class_options(), key="f_cls")
        val = c1.number_input("Replacement value, USD *", min_value=0.0, value=None, step=100000.0, format="%.0f", key="f_val", placeholder="e.g. 25000000")
        state = c2.selectbox("State or region *", manual_entry.STATE_OPTIONS, key="f_state")
        lat = c1.number_input("Latitude *", min_value=-90.0, max_value=90.0, value=None, format="%.5f", key="f_lat", placeholder="e.g. 31.5204")
        lon = c2.number_input("Longitude *", min_value=-180.0, max_value=180.0, value=None, format="%.5f", key="f_lon", placeholder="e.g. 74.3587")
        with st.expander("Optional details (better flood and loss estimates)"):
            o1, o2 = st.columns(2)
            contents = o1.number_input("Contents value, USD", min_value=0.0, value=None, step=50000.0, format="%.0f", key="f_contents")
            ffe = o2.number_input("First-floor height above ground, m", min_value=-5.0, max_value=100.0, value=None, format="%.2f", key="f_ffe")
            year = o1.number_input("Year built", min_value=1600, max_value=2100, value=None, step=1, key="f_year")
            ctype = o2.text_input("Construction type", key="f_ctype", placeholder="e.g. reinforced concrete")
        add = st.form_submit_button("Add asset to the list", type="primary")
    if add:
        row = {"asset_id": "", "name": name, "asset_class": cls, "replacement_value": val, "state": state, "lat": lat, "lon": lon,
               "contents_value": contents, "first_floor_elevation_m": ffe, "year_built": year, "construction_type": ctype or None}
        cur = st.session_state["manual_df"]
        probe = manual_entry.rows_to_dataframe(pd.concat([cur, pd.DataFrame([row])], ignore_index=True))
        res = ingestion.ingest(probe) if len(probe) else None
        bad = [i for i in (res.issues if res else []) if i.severity == "error" and i.row == len(probe) + 1]
        if bad:
            for i in bad:
                st.error(f"{i.message}")
        else:
            st.session_state["manual_df"] = pd.concat([cur, pd.DataFrame([row])], ignore_index=True)
            st.success(f"Added {name}. You now have {len(st.session_state['manual_df'])} asset(s).")
            for i in (res.issues if res else []):
                if i.severity == "warning" and i.row == len(probe) + 1:
                    st.warning(i.message)
    st.markdown("**3. Check the list**, edit cells, or add rows at the bottom of the table.")
    b1, b2 = st.columns([1, 3])
    if b1.button("Load 3 examples", key="ex_btn"):
        st.session_state["manual_df"] = pd.DataFrame([
            {"asset_id": "", "name": "Lahore plant", "asset_class": "industrial", "replacement_value": 35e6, "state": "Punjab", "lat": 31.5204, "lon": 74.3587, "contents_value": None, "first_floor_elevation_m": None, "year_built": None, "construction_type": None},
            {"asset_id": "", "name": "Karachi office", "asset_class": "office", "replacement_value": 50e6, "state": "Sindh", "lat": 24.8607, "lon": 67.0011, "contents_value": None, "first_floor_elevation_m": None, "year_built": None, "construction_type": None},
            {"asset_id": "", "name": "Houston warehouse", "asset_class": "industrial", "replacement_value": 18e6, "state": "TX", "lat": 29.7604, "lon": -95.3698, "contents_value": 4e6, "first_floor_elevation_m": 0.3, "year_built": 2004.0, "construction_type": None}])
        st.rerun()
    edited = st.data_editor(
        st.session_state["manual_df"], num_rows="dynamic", use_container_width=True, hide_index=True, key="manual_editor",
        column_config={
            "asset_id": st.column_config.TextColumn("ID (optional)"), "name": st.column_config.TextColumn("Name", required=True),
            "asset_class": st.column_config.SelectboxColumn("Type", options=manual_entry.asset_class_options(), required=True),
            "replacement_value": st.column_config.NumberColumn("Value, USD", format="$%d", min_value=0),
            "state": st.column_config.SelectboxColumn("State or region", options=manual_entry.STATE_OPTIONS, required=True),
            "lat": st.column_config.NumberColumn("Latitude", format="%.5f", min_value=-90, max_value=90),
            "lon": st.column_config.NumberColumn("Longitude", format="%.5f", min_value=-180, max_value=180),
            "contents_value": st.column_config.NumberColumn("Contents, USD", format="$%d", min_value=0),
            "first_floor_elevation_m": st.column_config.NumberColumn("Floor height, m", format="%.2f"),
            "year_built": st.column_config.NumberColumn("Year built", format="%d", min_value=1600, max_value=2100),
            "construction_type": st.column_config.TextColumn("Construction")})
    st.session_state["manual_df"] = edited
    st.caption(f"{len(manual_entry.rows_to_dataframe(edited))} asset(s) ready. Press **Run assessment** in the sidebar.")


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(f"<div class='brand-mark'><span>◈</span> {BRAND['name']}</div>", unsafe_allow_html=True)
    st.caption(BRAND["tagline"])
    st.markdown("<div class='section-label'>1 · Your assets</div>", unsafe_allow_html=True)
    mode = st.radio("Where do the assets come from?", SOURCE_MODES, label_visibility="collapsed", key="source_mode")
    up = st.file_uploader("Portfolio CSV", type="csv") if mode == "Upload CSV" else None
    st.markdown("<div class='section-label'>2 · Scenario</div>", unsafe_allow_html=True)
    scenario = st.selectbox("Climate scenario", list(hazards.SCENARIOS), format_func=lambda k: hazards.SCENARIOS[k]["label"], label_visibility="collapsed")
    use_llm = st.toggle("Add an AI-written narrative", value=bool(config.key("NVIDIA_API_KEY")),
                        help="Needs NVIDIA_API_KEY. A portfolio summary is sent to the provider. The report works without it.")
    run = st.button("Run assessment", type="primary", use_container_width=True)
    if mode == "Upload CSV":
        st.download_button("Download CSV template", TEMPLATE.read_bytes(), "portfolio_upload_template.csv", use_container_width=True)
    res = st.session_state.get("result")
    if res:
        conf = res["meta"]["confidence"]
        band = hazards.confidence_band(conf)
        st.markdown(f"<div class='card'><div class='section-label' style='margin-top:0'>Data confidence</div><strong>{band}</strong> · {conf:.2f} / 1.00</div>", unsafe_allow_html=True)
    if not config.key("OPEN_METEO_API_KEY"):
        st.caption("Open-Meteo is free for non-commercial use. Add `OPEN_METEO_API_KEY` before you sell results built on it.")
    with st.expander("API keys (this session only)"):
        for sv in SERVICES:
            if not sv["needs_key"] and sv["env"] != "OPEN_METEO_API_KEY":
                continue
            v = st.text_input(sv["env"], type="password", value="", placeholder="set" if config.key(sv["env"]) else "not set", key=f"key_{sv['env']}")
            if v:
                os.environ[sv["env"]] = "".join(v.split())
            st.link_button(sv["link_label"] + " ↗", sv["link"], use_container_width=True)
        st.caption("Keys stay in memory. Put them in `.env` to keep them.")

# ----------------------------------------------------------------------------- run
if run:
    src = None
    if mode == "Demo portfolio":
        src = TEMPLATE
    elif mode == "Upload CSV":
        src = up.getvalue() if up is not None else None
        if src is None:
            st.sidebar.error("Upload a CSV, or switch to Demo portfolio.")
    else:
        df_m = manual_entry.rows_to_dataframe(st.session_state.get("manual_df", manual_entry.blank_rows(0)))
        if df_m.empty:
            st.sidebar.error("Add at least one asset first.")
        else:
            src = df_m
    if src is not None:
        bar = st.progress(0.0, text="Starting...")
        try:
            st.session_state["result"] = run_assessment(src, scenario, use_llm, progress=lambda s, f: bar.progress(f, text=s))
            bar.empty()
            st.rerun()
        except Exception as e:
            bar.empty()
            st.error(f"Assessment failed: {e}")

res = st.session_state.get("result")
st.markdown(f"<div class='hero'><div><h1>Physical climate risk, asset by asset</h1><p>Flood, wind, heat, fire, drought, landslide and river flood, with the source of every number.</p></div>"
            f"<span class='tag'>{BRAND['name']}</span></div>", unsafe_allow_html=True)

if mode == "Enter manually":
    manual_panel()

if not res:
    st.markdown("""<div class='steps'>
<div class='step'><b class='n'>1</b><h4>Add your assets</h4><p>Upload a CSV, type them in with the form, or start from the demo portfolio.</p></div>
<div class='step'><b class='n'>2</b><h4>Pick a scenario</h4><p>Today's climate, or a future with a CMIP6 climate-change signal for each site.</p></div>
<div class='step'><b class='n'>3</b><h4>Read the results</h4><p>Hazard and severity for every asset, a map, and a report you can print or send.</p></div></div>""", unsafe_allow_html=True)
    st.markdown("### Connect real data (all free to start)")
    cards = []
    for sv in SERVICES:
        on = bool(config.key(sv["env"])) if sv["needs_key"] else True
        status = "<span class='pill on'>Ready</span>" if on else "<span class='pill off'>Key not set</span>"
        cards.append(f"<div class='card'><h4>{viz.esc(sv['name'])} {status}</h4><p>{viz.esc(sv['gives'])}</p><p>{viz.esc(sv['terms'])}</p>"
                     f"<p><a href='{viz.esc(sv['link'])}' target='_blank' rel='noopener noreferrer'>{viz.esc(sv['link_label'])} ↗</a></p></div>")
    st.markdown(f"<div class='svc'>{''.join(cards)}</div>", unsafe_allow_html=True)
    st.caption("Without keys the app still runs: hazards with no data are shown as 'No data', never as low risk.")
else:
    df: pd.DataFrame = res["assets"]
    s, meta = res["summary"], res["meta"]
    tabs = st.tabs(["Overview", "Map", "Hazard Risk", "Assets", "Report", "Setup"])
    if meta["confidence"] < 0.3:
        st.warning("Hazard data is mostly **synthetic demo data**. Results show the method only. Connect real data under Setup.")
    st.caption(f"Model status: **{s['model_status'].capitalize()}**. {s['model_status_note']}")
    loss_policy = s.get("loss_publication", {"allowed": s.get("total_expected_loss_usd") is not None, "override_used": False,
                                             "note": "Monetary loss estimates are experimental and not validated."})
    if not loss_policy.get("allowed"):
        st.warning("**Financial loss estimates withheld.** " + loss_policy.get("note", ""))
    elif loss_policy.get("override_used"):
        st.error("**INTERNAL OVERRIDE ACTIVE — EXPERIMENTAL LOSSES.** " + loss_policy.get("note", ""))
    if s.get("hazards_not_assessed"):
        st.info("Not assessed (no data, which is not the same as low risk): " + ", ".join(HAZARDS[h].label for h in s["hazards_not_assessed"]) + ".")
    _ls = hazards.layer_status()
    if any(_ls["rasters"].values()) and not _ls["rasterio"]:
        st.warning("Hazard rasters are present but the rasterio library is not installed, so they are being ignored. Install rasterio.")
    with tabs[0]:
        c = st.columns(4)
        c[0].metric("Assets", s["n_assets"])
        c[1].metric("Total value", usd(s["total_replacement_value_usd"]))
        c[2].metric("Avg risk score", s["mean_risk_score"] if s["mean_risk_score"] is not None else "n/a")
        c[3].metric("High + Critical", s["tier_counts"]["High"] + s["tier_counts"]["Critical"])
        c = st.columns(3)
        if loss_policy.get("allowed") and s.get("total_expected_loss_usd") is not None:
            c[0].metric("Scenario loss", usd(s["total_expected_loss_usd"]), f"{s['expected_loss_pct_of_value']}% of value", delta_color="off")
        else:
            c[0].metric("Scenario loss", "WITHHELD", help="Experimental damage functions are not empirically validated.")
        c[1].metric("Value-weighted risk", s["value_weighted_risk_score"])
        c[2].metric("Low risk, verified", s["low_risk_verified_assets"], help="Low rating backed by real data on every modelled hazard.")
        a, b = st.columns(2)
        a.plotly_chart(chart_severity(s), use_container_width=True, config={"displayModeBar": False})
        b.plotly_chart(chart_loss(s), use_container_width=True, config={"displayModeBar": False})
        st.plotly_chart(chart_top(df), use_container_width=True, config={"displayModeBar": False})
        with st.expander("How scores are built"):
            st.markdown("Each hazard intensity becomes a damage probability with a sigmoid curve (HAZUS-*inspired*, uncalibrated, in `src/fragility.py`). "
                        "Hazards combine as `P(any) = 1 - Π(1 - pᵢ)`, scaled by an asset-class consequence factor. Scenario loss = probability × loss ratio × value, not an annual expected loss. "
                        "River flood, drought and landslide are hazard indices with no damage function: they show on the Hazard Risk tab but not in the score or loss. "
                        "Severity: Low <25, Medium 25-49, High 50-74, Critical 75+. The score range is a ±15% hazard-intensity sensitivity, not a confidence interval.")
            st.dataframe(pd.DataFrame(fragility.CURVES).T[["col", "k", "x0", "max_loss", "unit"]])
        if res["qa"]["issue_counts"]:
            with st.expander(f"Data quality: {res['qa']['rows_valid']}/{res['qa']['rows_in']} rows valid, {len(res['qa']['issues'])} issue(s)", expanded=res["qa"]["rows_valid"] < res["qa"]["rows_in"]):
                st.dataframe(pd.DataFrame(res["qa"]["issues"]), use_container_width=True, hide_index=True)
        if loss_policy.get("allowed"):
            st.caption(s.get("loss_basis", "") + f" Flood loss covers {s.get('flood_loss_coverage_assets', 0)} of {s['n_assets']} assets ({s.get('flood_loss_coverage_pct', 0)}%).")
        else:
            st.caption(f"Flood event coverage metadata: {s.get('flood_loss_coverage_assets', 0)} of {s['n_assets']} assets ({s.get('flood_loss_coverage_pct', 0)}%). Monetary values are withheld.")
        st.caption(f"Processed in {res['elapsed_s']}s")

    with tabs[1]:
        opt = st.selectbox("Colour markers by", ["dominant"] + ALL_HAZARDS, format_func=lambda k: "Main hazard of each asset" if k == "dominant" else HAZARDS[k].label)
        m = viz.map_frame(df, opt)
        lat0, lon0, zoom = viz.fit_view(m)
        layer = pdk.Layer("ScatterplotLayer", m, get_position=["lon", "lat"], get_fill_color="fill", get_line_color="line",
                          get_radius="size_px", radius_units="'pixels'", stroked=True, line_width_min_pixels=2, pickable=True, opacity=1.0)
        tip = {"html": "<b>{name_html}</b><br/>{detail_html}", "style": {"backgroundColor": "#0b1220", "color": "#e8eef7", "borderRadius": "10px", "border": "1px solid #243a58"}}
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=lat0, longitude=lon0, zoom=zoom),
                                 tooltip=tip, map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"), height=520)
        st.markdown(viz.legend_html(), unsafe_allow_html=True)
        st.caption("Marker colour is the hazard. Marker size is severity: larger means more severe. Hollow grey means no data for that hazard, which is not a low-risk finding.")

    with tabs[2]:
        st.markdown(viz.legend_html(), unsafe_allow_html=True)
        f1, f2 = st.columns(2)
        hz_sel = f1.multiselect("Hazards", ALL_HAZARDS, default=ALL_HAZARDS, format_func=lambda k: HAZARDS[k].label)
        sev_sel = f2.multiselect("Severity", SEVERITY_LEVELS + [NOT_ASSESSED], default=SEVERITY_LEVELS + [NOT_ASSESSED])
        flt = viz.filter_assets(df, hz_sel, sev_sel).sort_values("risk_score", ascending=False, na_position="last")
        st.caption(f"{len(flt)} of {len(df)} assets match the filters.")
        if len(flt):
            st.markdown(viz.matrix_html(flt.head(200), hz_sel or None), unsafe_allow_html=True)
            if len(flt) > 200:
                st.caption("Showing the 200 highest-scoring matches. Export the CSV for the full list.")
            pick = st.selectbox("Inspect an asset", flt["asset_id"] + " - " + flt["name"], key="inspect_asset")
            st.markdown(viz.asset_card_html(df[df["asset_id"] == pick.split(" - ")[0]].iloc[0]), unsafe_allow_html=True)
        else:
            st.info("No assets match the current filters.")

    with tabs[3]:
        cols = ["asset_id", "name", "state", "asset_class", "replacement_value", "risk_score", "risk_tier", "dominant_hazard", "overall_status",
                "p_flood", "p_wind", "p_wildfire", "p_heat"]
        if loss_policy.get("allowed"):
            cols.insert(9, "expected_loss_usd")
        st.dataframe(df[cols].sort_values("risk_score", ascending=False), use_container_width=True, hide_index=True,
                     column_config={"risk_score": st.column_config.ProgressColumn("risk_score", min_value=0, max_value=100),
                                    "replacement_value": st.column_config.NumberColumn(format="$%d"),
                                    "expected_loss_usd": st.column_config.NumberColumn(format="$%d")})
        st.download_button("Export CSV", df.to_csv(index=False), "asset_risk_scores.csv", "text/csv")

    with tabs[4]:
        if meta["confidence"] < 0.3:
            st.warning("Synthetic data in use. Do not use this report for disclosure.")
        if res["report_log"].get("error"):
            st.info("The AI call failed, so the standard report is shown: " + res["report_log"]["error"])
        a, b, c = st.columns(3)
        a.download_button("Download report (HTML, prints to PDF)", res["report_html"], "climate_risk_report.html", "text/html", use_container_width=True)
        b.download_button("Markdown", res["report_md"], "portfolio_risk_report.md", use_container_width=True)
        c.download_button("JSON", json.dumps({"markdown": res["report_md"], "summary": s, "data_meta": meta}, indent=2, default=str),
                          "portfolio_risk_report.json", use_container_width=True)
        if hasattr(st, "iframe"):
            st.iframe(res["report_html"], height=1100)
        else:
            components.html(res["report_html"], height=1100, scrolling=True)

if res:
    with tabs[5]:
        st.subheader("What is missing for a more accurate estimate")
        rd = res["meta"].get("readiness") or readiness()
        icon = {"ok": "✅", "partial": "🟠", "missing": "⚪"}
        for i in rd["items"]:
            st.write(f"{icon[i['status']]} **{i['item']}**: {i['detail']} {i['fix']}")
        if rd["precise"]:
            st.caption(f"Most precise input in the last run: {rd['precise']['hazard']}. Weakest: {rd['weakest']['hazard']}.")
        with st.expander("Known defects of this software"):
            for d in rd["known_defects"]:
                st.write("- " + d)
        st.subheader("Data services")
        cards = []
        for sv in SERVICES:
            on = bool(config.key(sv["env"])) if sv["needs_key"] else True
            status = "<span class='pill on'>Ready</span>" if on else "<span class='pill off'>Key not set</span>"
            cards.append(f"<div class='card'><h4>{viz.esc(sv['name'])} {status}</h4><p>{viz.esc(sv['gives'])}</p><p>{viz.esc(sv['terms'])}</p>"
                         f"<p><a href='{viz.esc(sv['link'])}' target='_blank' rel='noopener noreferrer'>{viz.esc(sv['link_label'])} ↗</a></p></div>")
        st.markdown(f"<div class='svc'>{''.join(cards)}</div>", unsafe_allow_html=True)
        st.subheader("Local hazard files (optional)")
        ls = hazards.layer_status()
        st.write(("✅" if ls["fema_states"] else "⚪") + " FEMA NFHL GeoPackages: " + (", ".join(ls["fema_states"]) if ls["fema_states"] else "none found (US only)"))
        for n, ok in ls["rasters"].items():
            st.write(("✅ found" if ok else "⚪ optional") + f" `data/hazards/{n}.tif`")
        st.caption("A local raster is used only when it is WGS84 and covers the asset. Offline mode: set CRPA_OFFLINE=1.")
        if st.button("Run pipeline on the demo portfolio", key="smoke"):
            t = time.time()
            try:
                r = run_assessment(TEMPLATE, "current", False, out_dir=config.OUTPUT_DIR / "smoke")
                st.success(f"OK: {r['summary']['n_assets']} assets in {time.time()-t:.1f}s (confidence {r['meta']['confidence']:.2f})")
            except Exception as e:
                st.error(str(e))
