"""Presentation helpers: accessible HTML for hazard legends, the portfolio matrix and the asset inspector.

No Streamlit import here, so it is unit-testable. Every value that can come from a user CSV is HTML-escaped.
Colour marks the hazard; severity is carried by text and an ordinal pip meter, never by colour alone.
"""
from __future__ import annotations

from html import escape as _esc

import pandas as pd

from .hazard_registry import (
    ALL_HAZARDS,
    HAZARDS,
    NOT_ASSESSED,
    SEVERITY_LEVELS,
    SEVERITY_ORDER,
    STATUS_LABEL,
    confidence_class,
    mitigation_actions,
)

CSS = """
<style>
.hz-chip{display:inline-flex;align-items:center;gap:.4rem;padding:2px 9px;border-radius:999px;border:1px solid var(--hz);
 font-size:.78rem;font-weight:700;color:#e5edf7;background:rgba(255,255,255,.04);white-space:nowrap}
.hz-chip i{width:.7rem;height:.7rem;border-radius:50%;background:var(--hz);display:inline-block}
.sev{display:inline-flex;align-items:center;gap:.45rem;font-size:.82rem;font-weight:700;color:#f1f5f9;white-space:nowrap}
.sev .pips{display:inline-flex;gap:2px}.sev .pips b{width:.55rem;height:.9rem;border-radius:2px;background:#334155;display:inline-block}
.sev .pips b.on{background:#e2e8f0}
.sev.illus{font-style:italic;opacity:.85}.sev.illus .pips b.on{background:repeating-linear-gradient(45deg,#e2e8f0 0 2px,#475569 2px 4px)}
.sev.nodata{color:#94a3b8;font-weight:600}.sev.nodata .pips b{background:transparent;border:1px dashed #64748b}
.verified{border:1px solid #22c55e;color:#bbf7d0;background:rgba(34,197,94,.12);padding:2px 9px;border-radius:999px;font-size:.78rem;font-weight:700}
.unverified{border:1px dashed #94a3b8;color:#cbd5e1;padding:2px 9px;border-radius:999px;font-size:.78rem;font-weight:700}
.legend{display:flex;flex-wrap:wrap;gap:.6rem 1.2rem;align-items:center;margin:.4rem 0 1rem;padding:.7rem .9rem;border:1px solid #244264;border-radius:12px;background:#102139}
.legend .grp{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center}.legend .t{color:#9db4cf;font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.mx-wrap{overflow-x:auto;border:1px solid #244264;border-radius:12px}
table.mx{border-collapse:collapse;width:100%;min-width:640px;font-size:.84rem;color:#e5edf7}
table.mx caption{caption-side:top;text-align:left;padding:.5rem .8rem;color:#9db4cf;font-size:.78rem}
table.mx tbody th{min-width:11rem}table.mx td{white-space:nowrap}
table.mx th,table.mx td{padding:.5rem .7rem;border-bottom:1px solid #1b3350;text-align:left;vertical-align:middle}
table.mx thead th{background:#0d1b2f;position:sticky;top:0}
table.mx tbody th{font-weight:650}
table.mx td .sc{color:#9db4cf;font-size:.74rem;margin-left:.2rem}
.card{border:1px solid #244264;border-radius:14px;background:#102139;padding:1rem 1.1rem;margin:.6rem 0}
.card h3{margin:0 0 .2rem;font-size:1.15rem}.card .meta{color:#a9bdd4;font-size:.84rem}
.hz-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:.8rem;margin-top:.8rem}
.hz-card{border:1px solid #244264;border-left:5px solid var(--hz);border-radius:10px;padding:.7rem .8rem;background:#0d1b2f}
.hz-card h4{margin:.1rem 0 .4rem;font-size:.95rem}.hz-card ul{margin:.3rem 0 .2rem 1.1rem;padding:0;font-size:.82rem;color:#cfe0f5}
.hz-card .k{color:#9db4cf;font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-top:.5rem}
@media (max-width:800px){.legend{gap:.5rem}table.mx{font-size:.78rem}}
</style>
"""


def esc(x: object) -> str:
    return _esc("" if x is None else str(x), quote=True)


def hazard_chip(h: str) -> str:
    s = HAZARDS[h]
    return f'<span class="hz-chip" style="--hz:{s.color}" title="{esc(s.note)}"><i aria-hidden="true"></i>{s.code} {esc(s.label)}</span>'


def _pips(level: int) -> str:
    return '<span class="pips" aria-hidden="true">' + "".join(f'<b class="{"on" if i < level else ""}"></b>' for i in range(4)) + "</span>"


def severity_badge(severity: str, status: str = "assessed") -> str:
    """Text label + ordinal pips. 'illustrative' = synthetic input; 'not_assessed' = no data (never shown as Low)."""
    if status == "not_assessed" or severity == NOT_ASSESSED:
        return f'<span class="sev nodata" aria-label="No data, not assessed">{_pips(0)}No data</span>'
    lvl = SEVERITY_ORDER.get(severity, 0)
    if status == "illustrative":
        return (f'<span class="sev illus" aria-label="{esc(severity)} severity, illustrative synthetic input">'
                f'{_pips(lvl)}{esc(severity)} (illustrative)</span>')
    return f'<span class="sev" aria-label="{esc(severity)} severity">{_pips(lvl)}{esc(severity)}</span>'


def legend_html() -> str:
    hz = "".join(hazard_chip(h) for h in ALL_HAZARDS)
    sev = "".join(severity_badge(s) + " " for s in SEVERITY_LEVELS)
    other = severity_badge("Medium", "illustrative") + " " + severity_badge(NOT_ASSESSED, "not_assessed")
    return (f'<div class="legend" role="group" aria-label="Legend"><div class="grp"><span class="t">Hazard (colour)</span>{hz}</div>'
            f'<div class="grp"><span class="t">Severity (label + bars)</span>{sev}</div>'
            f'<div class="grp"><span class="t">Data status</span>{other}'
            f'<span class="meta" style="color:#9db4cf;font-size:.78rem">Illustrative = synthetic input. No data is not the same as low risk.</span></div></div>')


def _truthy_list(x) -> bool:
    return isinstance(x, (list, tuple)) and len(x) > 0


def _f(row, col, fmt="{:.1f}"):
    v = row.get(col)
    try:
        return None if v is None or pd.isna(v) else fmt.format(float(v))
    except (TypeError, ValueError):
        return None


def contributing_factors(row: pd.Series, hz: str) -> list[str]:
    """Plain-language drivers behind one hazard rating, built only from values present in the row."""
    out: list[str] = []
    src = row.get(f"src_{hz}")
    if hz == "flood":
        d, zone = _f(row, "flood_depth_m", "{:.2f}"), row.get("flood_zone")
        basis = ("return-period flood depth" if _truthy_list(row.get("flood_supported_return_periods"))
                 else "flood-zone depth proxy (not a modelled depth)")
        if d is not None:
            out.append(f"Depth {d} m from {basis}; zone {esc(zone)}.")
        if pd.isna(row.get("first_floor_elevation_m", float("nan"))):
            out.append("First-floor height not supplied; depth is measured from ground level.")
        if _f(row, "elevation_m") is not None:
            out.append(f"Ground elevation {_f(row, 'elevation_m', '{:.0f}')} m.")
        if bool(row.get("slr_applied", False)):
            out.append("Includes the scenario sea-level-rise uplift (coastal site).")
    elif hz == "wind" and _f(row, "wind_ms"):
        out.append(f"Maximum gust {_f(row, 'wind_ms')} m/s over the reference period.")
    elif hz == "heat" and _f(row, "heat_c"):
        out.append(f"Maximum daily temperature {_f(row, 'heat_c')} deg C.")
    elif hz == "wildfire" and _f(row, "wildfire_score"):
        out.append(f"Wildfire score {_f(row, 'wildfire_score', '{:.0f}')}/100.")
    elif hz == "drought" and _f(row, "drought_cdd_days"):
        out.append(f"Mean annual longest dry spell {_f(row, 'drought_cdd_days', '{:.0f}')} days.")
    elif hz == "landslide" and _f(row, "landslide_index"):
        out.append(f"Susceptibility index {_f(row, 'landslide_index', '{:.0f}')}/100.")
    if row.get(f"status_{hz}") == "not_assessed":
        out.append("No data layer or API result for this hazard.")
    elif src:
        q = confidence_class(row.get(f"confidence_{hz}"))
        out.append(f"Source: {esc(src)} ({'synthetic, not real data' if q == 'Synthetic' else q.lower() + ' source quality'}).")
    crit = row.get("criticality")
    if HAZARDS[hz].basis == "risk" and crit is not None and not pd.isna(crit) and float(crit) != 1.0:
        out.append(f"Consequence factor x{float(crit):.2f} for asset class {esc(row.get('asset_class'))}.")
    return out


def matrix_html(df: pd.DataFrame, hazards: list[str] | None = None) -> str:
    hazards = hazards or ALL_HAZARDS
    head = "".join(f'<th scope="col">{hazard_chip(h)}</th>' for h in hazards)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for h in hazards:
            sc = r.get(f"risk_{h}")
            score = f'<span class="sc">{sc:.0f}</span>' if r.get(f"status_{h}") != "not_assessed" and pd.notna(sc) else ""
            cells.append(f'<td>{severity_badge(r.get(f"severity_{h}", NOT_ASSESSED), r.get(f"status_{h}", "not_assessed"))}{score}</td>')
        overall = (f'{esc(r.get("risk_tier"))} <span class="sc">{r.get("risk_score"):.0f}</span>'
                   if pd.notna(r.get("risk_score")) else "No data")
        rows.append(f'<tr><th scope="row">{esc(r.get("name"))}<br><span class="sc">{esc(r.get("asset_id"))} · {esc(r.get("state"))}</span></th>'
                    f'<td>{overall}</td>{"".join(cells)}</tr>')
    return ('<div class="mx-wrap"><table class="mx"><caption>Severity by hazard for each asset. Score = 0-100 screening score.</caption>'
            f'<thead><tr><th scope="col">Asset</th><th scope="col">Overall</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def asset_card_html(r: pd.Series) -> str:
    tier = r.get("risk_tier")
    verified = bool(r.get("low_risk_verified", False))
    if tier == "Low":
        flag = ('<span class="verified">Low risk, verified with real data</span>' if verified
                else '<span class="unverified">Low (unverified: synthetic or partial data)</span>')
    else:
        flag = ""
    rng = (f' (range {r.get("risk_score_low"):.0f}-{r.get("risk_score_high"):.0f}, +/-15% intensity sensitivity)'
           if pd.notna(r.get("risk_score_low")) and pd.notna(r.get("risk_score_high")) else "")
    score = f'{r.get("risk_score"):.0f}/100' if pd.notna(r.get("risk_score")) else "n/a"
    head = (f'<div class="card"><h3>{esc(r.get("name"))}</h3><div class="meta">{esc(r.get("asset_id"))} · {esc(r.get("asset_class"))} · '
            f'{esc(r.get("state"))} · {_f(r, "lat", "{:.4f}")}, {_f(r, "lon", "{:.4f}")}</div>'
            f'<p style="margin:.6rem 0 .2rem"><b>Overall: {esc(tier)}</b> · score {score}{esc(rng)} · '
            f'data status {esc(STATUS_LABEL.get(r.get("overall_status"), r.get("overall_status")))} · '
            f'source quality {esc(confidence_class(r.get("overall_confidence")))} {flag}</p>'
            f'<div class="meta">Scenario: {esc(r.get("scenario"))}. {esc(r.get("assessment_basis"))}</div>')
    cards = []
    for h in sorted(ALL_HAZARDS, key=lambda k: -(r.get(f"risk_{k}") if pd.notna(r.get(f"risk_{k}")) else -1)):
        s, sev, st = HAZARDS[h], r.get(f"severity_{h}", NOT_ASSESSED), r.get(f"status_{h}", "not_assessed")
        facts = "".join(f"<li>{x}</li>" for x in contributing_factors(r, h))
        acts = "".join(f"<li>{esc(a)}</li>" for a in mitigation_actions(h, sev, st))
        basis = "hazard x vulnerability x consequence" if s.basis == "risk" else "hazard index only, no damage function"
        sc = f'{r.get(f"risk_{h}"):.0f}' if st != "not_assessed" and pd.notna(r.get(f"risk_{h}")) else "n/a"
        cards.append(f'<div class="hz-card" style="--hz:{s.color}">{hazard_chip(h)}<h4>{severity_badge(sev, st)} · score {sc}</h4>'
                     f'<div class="meta">Basis: {basis}. Source quality: {esc(confidence_class(r.get(f"confidence_{h}")))}.</div>'
                     f'<div class="k">Contributing factors</div><ul>{facts}</ul><div class="k">Recommended actions</div><ul>{acts}</ul></div>')
    return head + f'<div class="hz-grid">{"".join(cards)}</div></div>'


# Severity is an ordinal ramp (neutral lightness), deliberately NOT using the hazard hues.
SEVERITY_COLORS = {"Low": "#64748B", "Medium": "#94A3B8", "High": "#CBD5E1", "Critical": "#F8FAFC", NOT_ASSESSED: "#475569"}


def filter_assets(df: pd.DataFrame, hazards: list[str], severities: list[str]) -> pd.DataFrame:
    """Keep assets where at least one selected hazard has a selected severity ('Not assessed' counts as a severity)."""
    if not hazards or not severities:
        return df.iloc[0:0]
    mask = pd.Series(False, index=df.index)
    for h in hazards:
        col = f"severity_{h}"
        if col in df:
            mask |= df[col].isin(severities)
    return df[mask]


def map_frame(df: pd.DataFrame, hazard: str = "dominant") -> pd.DataFrame:
    """Map layer data. Fill colour = hazard identity, marker size = severity step, hollow grey = no data."""
    rows = []
    for _, r in df.iterrows():
        h = r.get("dominant_hazard") if hazard == "dominant" else hazard
        if h not in HAZARDS:  # 'none' (all low) or 'not_assessed'
            h = None
        sev = r.get(f"severity_{h}", NOT_ASSESSED) if h else (NOT_ASSESSED if r.get("dominant_hazard") == "not_assessed" else "Low")
        st = r.get(f"status_{h}", "not_assessed") if h else ("not_assessed" if sev == NOT_ASSESSED else "assessed")
        hide = st == "not_assessed"
        hexc = (HAZARDS[h].color if h and not hide else "#64748B").lstrip("#")
        rgb = [int(hexc[i:i + 2], 16) for i in (0, 2, 4)]
        lvl = 0 if hide else SEVERITY_ORDER.get(sev, 1)
        rows.append({
            "lat": r["lat"], "lon": r["lon"], "fill": rgb + [0 if hide else 215], "line": [226, 232, 240, 255] if not hide else [148, 163, 184, 255],
            "size_px": 8 + 3 * lvl,
            "name_html": esc(r.get("name")),
            "detail_html": esc(f'{HAZARDS[h].label if h else "No dominant hazard"}: '
                               f'{"no data" if hide else sev}{" (illustrative)" if st == "illustrative" else ""}'
                               f' · overall {r.get("risk_tier")} {r.get("risk_score") if pd.notna(r.get("risk_score")) else ""}'),
        })
    return pd.DataFrame(rows)


def fit_view(df: pd.DataFrame, width_px: int = 900, height_px: int = 520) -> tuple[float, float, float]:
    """(lat, lon, zoom) that frames all assets with a margin. A single site gets a city-level zoom."""
    import math
    lat0, lat1, lon0, lon1 = df["lat"].min(), df["lat"].max(), df["lon"].min(), df["lon"].max()
    clat, clon = (lat0 + lat1) / 2, (lon0 + lon1) / 2
    lat_span = max(lat1 - lat0, 0.02) * 1.35
    lon_span = max((lon1 - lon0) * max(math.cos(math.radians(clat)), 0.2), 0.02) * 1.35
    z = min(math.log2(360 * width_px / 512 / lon_span), math.log2(180 * height_px / 512 / lat_span))
    return float(clat), float(clon), float(max(1.0, min(11.0, z)))
