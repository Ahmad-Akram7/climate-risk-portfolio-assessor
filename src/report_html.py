"""Standalone HTML report (no scripts, no external files). Opens in any browser and prints cleanly to PDF.

Colour marks the hazard; severity is always written out. Every dynamic string is escaped.
"""
from __future__ import annotations

import re
import time

import pandas as pd

from .hazard_registry import (
    ALL_HAZARDS,
    DAMAGE_HAZARDS,
    HAZARDS,
    NOT_ASSESSED,
    SEVERITY_LEVELS,
)
from .readiness import readiness_markdown
from .viz import esc

SEV_FILL = {"Low": "#94a3b8", "Medium": "#64748b", "High": "#334155", "Critical": "#0f172a", NOT_ASSESSED: "#e2e8f0"}

# (label prefix, plain description, attribution line)
SOURCE_NOTES = [
    ("FEMA_NFHL", "FEMA National Flood Hazard Layer", "FEMA NFHL, public domain."),
    ("JRC_", "JRC Global Flood Hazard (20-year depth)", "European Commission Joint Research Centre, open licence."),
    ("OpenMeteo_ERA5", "ERA5 reanalysis via Open-Meteo", "Contains Copernicus Climate Change Service information (ERA5). Data via Open-Meteo.com."),
    ("OpenMeteo_Climate", "CMIP6 HighResMIP via Open-Meteo Climate API", "CMIP6 model data, CC BY 4.0. Data via Open-Meteo.com."),
    ("OpenMeteo_GloFAS", "GloFAS river discharge via Open-Meteo", "GloFAS, Copernicus Emergency Management Service. Data via Open-Meteo.com."),
    ("OpenMeteo_Elevation", "Elevation via Open-Meteo", "Data via Open-Meteo.com."),
    ("OpenTopography", "Copernicus DEM 30 m via OpenTopography", "Copernicus DEM, ESA. Served by OpenTopography."),
    ("Copernicus", "Copernicus DEM (local tiles)", "Copernicus DEM, ESA."),
    ("NOAA_CDO", "NOAA Climate Data Online", "NOAA NCEI, public domain."),
    ("NASA_FIRMS", "NASA FIRMS active fire detections", "NASA FIRMS, public domain."),
    ("Synthetic", "Synthetic demonstration values", "Not real data. For demonstration only."),
]

CSS = """
*{box-sizing:border-box}body{margin:0;background:#fff;color:#0f172a;font:15px/1.55 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
.page{max-width:920px;margin:0 auto;padding:28px 24px 40px}
.cover{border-bottom:4px solid var(--brand);padding-bottom:18px;margin-bottom:22px}
.cover .org{font-size:.8rem;letter-spacing:.14em;text-transform:uppercase;color:var(--brand);font-weight:700}
.cover h1{font-size:1.9rem;margin:.2rem 0 .3rem;letter-spacing:-.02em}.cover p{margin:0;color:#475569}
h2{font-size:1.15rem;margin:1.8rem 0 .6rem;padding-top:.4rem;border-top:1px solid #e2e8f0}
.warn{border:1px solid #b45309;background:#fffbeb;color:#78350f;padding:10px 14px;border-radius:8px;margin:14px 0;font-size:.92rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.kpi{border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;background:#f8fafc}.kpi b{display:block;font-size:1.35rem}
.kpi span{font-size:.74rem;color:#64748b;text-transform:uppercase;letter-spacing:.06em}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{padding:7px 9px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top}
th{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:#64748b}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--c);border-radius:999px;padding:1px 9px;font-size:.78rem;font-weight:600;white-space:nowrap}
.chip i{width:9px;height:9px;border-radius:50%;background:var(--c);display:inline-block}
.sev{font-weight:700;white-space:nowrap}.pips{display:inline-flex;gap:2px;margin-right:6px;vertical-align:middle}
.pips b{width:7px;height:13px;border-radius:2px;background:#e2e8f0;display:inline-block}.pips b.on{background:#1e293b}
.pips.ill b.on{background:repeating-linear-gradient(45deg,#1e293b 0 2px,#94a3b8 2px 4px)}
.muted{color:#64748b}.note{font-size:.85rem;color:#475569}
svg text{font-family:inherit}
.narr p{margin:.5rem 0}.narr h3{font-size:1rem;margin:1rem 0 .3rem}
footer{margin-top:2rem;padding-top:.8rem;border-top:1px solid #e2e8f0;font-size:.8rem;color:#64748b}
@media print{.page{padding:0}h2{break-after:avoid}table,svg,.kpis{break-inside:avoid}}
@media (max-width:600px){.page{padding:16px 12px}.cover h1{font-size:1.5rem}}
"""


def usd(x: float) -> str:
    x = float(x or 0)
    return f"${x/1e9:.2f}B" if x >= 1e9 else f"${x/1e6:.1f}M" if x >= 1e6 else f"${x:,.0f}"


def chip(h: str) -> str:
    s = HAZARDS[h]
    return f'<span class="chip" style="--c:{s.color}"><i></i>{s.code} {esc(s.label)}</span>'


def sev_badge(sev: str, status: str = "assessed") -> str:
    if status == "not_assessed" or sev == NOT_ASSESSED:
        return '<span class="sev muted">No data</span>'
    lvl = SEVERITY_LEVELS.index(sev) + 1 if sev in SEVERITY_LEVELS else 0
    pips = "".join(f'<b class="{"on" if i < lvl else ""}"></b>' for i in range(4))
    ill = " ill" if status == "illustrative" else ""
    return f'<span class="sev"><span class="pips{ill}" aria-hidden="true">{pips}</span>{esc(sev)}{" (illustrative)" if ill else ""}</span>'


def svg_stacked(rows: list[tuple[str, str, dict[str, int]]]) -> str:
    """Horizontal stacked bars. rows = (hazard key, label, {severity: count}). Width scales to the largest total."""
    if not rows:
        return ""
    order = SEVERITY_LEVELS + [NOT_ASSESSED]
    total_max = max(sum(c.values()) for _, _, c in rows) or 1
    lw, bw, bh, gap = 190, 520, 22, 12
    h = len(rows) * (bh + gap) + 8
    out = [f'<svg viewBox="0 0 {lw + bw + 40} {h}" width="100%" role="img" aria-label="Assets by severity for each hazard">']
    for i, (hk, label, counts) in enumerate(rows):
        y = 4 + i * (bh + gap)
        out.append(f'<circle cx="8" cy="{y + bh/2}" r="5" fill="{HAZARDS[hk].color}"/>'
                   f'<text x="20" y="{y + bh/2 + 4}" font-size="13" fill="#0f172a">{esc(label)}</text>')
        x = lw
        for sv in order:
            n = counts.get(sv, 0)
            if not n:
                continue
            w = bw * n / total_max
            pat = ' stroke="#94a3b8" stroke-dasharray="3 2"' if sv == NOT_ASSESSED else ""
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w, 1):.1f}" height="{bh}" fill="{SEV_FILL[sv]}"{pat}><title>{esc(label)}: {n} {esc(sv)}</title></rect>')
            if w > 20:
                col = "#0f172a" if sv in (NOT_ASSESSED, "Low") else "#fff"
                out.append(f'<text x="{x + w/2:.1f}" y="{y + bh/2 + 4}" font-size="12" text-anchor="middle" fill="{col}">{n}</text>')
            x += w
    out.append("</svg>")
    return "".join(out)


def svg_bars(items: list[tuple[str, str, float]], fmt=usd) -> str:
    """Horizontal single-colour bars: (hazard key, label, value). Colour = hazard identity."""
    items = [i for i in items if i[2] and i[2] > 0]
    if not items:
        return '<p class="note">No modelled loss for any hazard.</p>'
    vmax = max(v for _, _, v in items)
    lw, bw, bh, gap = 190, 480, 20, 12
    h = len(items) * (bh + gap) + 8
    out = [f'<svg viewBox="0 0 {lw + bw + 90} {h}" width="100%" role="img" aria-label="Scenario loss by hazard">']
    for i, (hk, label, v) in enumerate(items):
        y = 4 + i * (bh + gap)
        w = max(2.0, bw * v / vmax)
        out.append(f'<text x="0" y="{y + bh/2 + 4}" font-size="13" fill="#0f172a">{esc(label)}</text>'
                   f'<rect x="{lw}" y="{y}" width="{w:.1f}" height="{bh}" rx="3" fill="{HAZARDS[hk].color}"><title>{esc(label)}: {esc(fmt(v))}</title></rect>'
                   f'<text x="{lw + w + 8:.1f}" y="{y + bh/2 + 4}" font-size="12" fill="#334155">{esc(fmt(v))}</text>')
    out.append("</svg>")
    return "".join(out)


def md_to_html(md: str) -> str:
    """Tiny, safe markdown subset for the AI narrative: headings, bullets, bold, paragraphs. Everything is escaped first."""
    out, bullets = [], []

    def flush():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    def inline(t: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(t))

    for line in md.splitlines():
        s = line.strip()
        if not s:
            flush()
        elif s.startswith("#"):
            flush()
            out.append(f"<h3>{inline(s.lstrip('#').strip())}</h3>")
        elif s[:2] in ("- ", "* "):
            bullets.append(inline(s[2:]))
        elif s.startswith(">"):
            flush()
            out.append(f'<p class="note">{inline(s.lstrip("> "))}</p>')
        else:
            flush()
            out.append(f"<p>{inline(s)}</p>")
    flush()
    return "".join(out)


def _sources(meta: dict) -> list[tuple[str, str]]:
    labels = {lab for d in meta.get("source_counts", {}).values() for lab in d}
    found, seen = [], set()
    for lab in sorted(labels):
        for prefix, desc, attr in SOURCE_NOTES:
            if lab.startswith(prefix) and prefix not in seen:
                seen.add(prefix)
                found.append((desc, attr))
    return found


def summary_sentence(s: dict, meta: dict) -> str:
    t = s["tier_counts"]
    base = f"The portfolio has {s['n_assets']} assets worth {usd(s['total_replacement_value_usd'])}. "
    if not s.get("loss_publication", {}).get("allowed", s.get("total_expected_loss_usd") is not None):
        base += "Monetary loss estimates are withheld because the damage functions are experimental and not empirically validated. "
    elif s.get("total_expected_loss_usd") is not None:
        base += (f"Under the {meta.get('scenario_label', 'selected')} scenario the screening model estimates a loss of "
                 f"{usd(s['total_expected_loss_usd'])}, or {s['expected_loss_pct_of_value']}% of value. ")
    base += (f"{t.get('Critical', 0)} rated Critical and {t.get('High', 0)} rated High. "
             f"Assets with a Low rating backed by real data on every modelled hazard: {s.get('low_risk_verified_assets', 0)}.")
    return base


def build_html_report(result: dict, brand: dict | None = None) -> str:
    brand = brand or {}
    name, color = brand.get("name") or "Climate Risk Assessor", brand.get("color") or "#1d4ed8"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = "#1d4ed8"
    df: pd.DataFrame = result["assets"]
    s, meta = result["summary"], result["meta"]
    n_ill = int((df["overall_status"] == "illustrative").sum())

    banner = ""
    if meta["confidence"] < 0.3 or n_ill:
        banner = ('<div class="warn"><strong>Synthetic demonstration data.</strong> Some or all hazard values are not real. '
                  'Use this report to see the method only, not for decisions or disclosure.</div>')
    loss_state = s.get("loss_publication", {"allowed": s.get("total_expected_loss_usd") is not None, "override_used": False,
                                           "note": "Monetary estimates are experimental and not validated."})
    loss_banner = ""
    if not loss_state.get("allowed"):
        loss_banner = f'<div class="warn"><strong>Financial estimates withheld.</strong> {esc(loss_state.get("note", ""))}</div>'
    elif loss_state.get("override_used"):
        loss_banner = f'<div class="warn"><strong>INTERNAL OVERRIDE — EXPERIMENTAL ESTIMATES.</strong> {esc(loss_state.get("note", ""))}</div>'

    kpi = [(usd(s["total_replacement_value_usd"]), "Total value")]
    if loss_state.get("allowed") and s.get("total_expected_loss_usd") is not None:
        kpi += [(usd(s["total_expected_loss_usd"]), "Scenario loss"),
                (f"{s['expected_loss_pct_of_value']}%", "Loss, share of value")]
    else:
        kpi += [("Withheld", "Scenario loss")]
    kpi += [(f"{s['value_weighted_risk_score']}", "Value-weighted score"),
            (str(s["tier_counts"]["High"] + s["tier_counts"]["Critical"]), "High or Critical assets"),
            (str(s["low_risk_verified_assets"]), "Verified low risk")]
    kpis = "".join(f'<div class="kpi"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for v, k in kpi)

    hs = s["hazard_summary"]
    sev_rows = []
    for h in ALL_HAZARDS:
        d = hs[h]
        counts = dict(d["severity_counts"])
        counts[NOT_ASSESSED] = d["status_counts"]["not_assessed"]
        sev_rows.append((h, HAZARDS[h].label, counts))
    loss_items = [(h, HAZARDS[h].label, hs[h]["scenario_loss_usd"] or 0.0) for h in DAMAGE_HAZARDS]
    loss_items.sort(key=lambda x: -x[2])
    if not loss_state.get("allowed"):
        loss_items = []

    top = df.sort_values("risk_score", ascending=False, na_position="last").head(10)
    rows = []
    for _, r in top.iterrows():
        dom = r["dominant_hazard"]
        dom_html = chip(dom) if dom in HAZARDS else esc(dom.replace("_", " "))
        sc = f"{r['risk_score']:.0f}" if pd.notna(r["risk_score"]) else "n/a"
        asset_loss = usd(r["expected_loss_usd"]) if loss_state.get("allowed") and pd.notna(r.get("expected_loss_usd")) else "Withheld"
        rows.append(f"<tr><td><strong>{esc(r['name'])}</strong><br><span class='muted'>{esc(r['asset_id'])} · {esc(r['state'])} · {esc(r['asset_class'])}</span></td>"
                    f"<td>{sev_badge(r['risk_tier'], r['overall_status'])} <span class='muted'>{sc}</span></td><td>{dom_html}</td>"
                    f"<td>{esc(asset_loss)}</td></tr>")
    top_html = ("<table><thead><tr><th>Asset</th><th>Overall</th><th>Main hazard</th><th>Scenario loss</th></tr></thead><tbody>"
                + "".join(rows) + "</tbody></table>")

    notes = []
    for h in ALL_HAZARDS:
        d = hs[h]
        usable = d["status_counts"]["assessed"] + d["status_counts"]["illustrative"]
        if not usable:
            notes.append(f"<tr><td>{chip(h)}</td><td colspan='2'><span class='muted'>Not assessed: no data layer or API result. This is not a low-risk finding.</span></td></tr>")
        else:
            notes.append(f"<tr><td>{chip(h)}</td><td>{usable} of {s['n_assets']} assets rated</td>"
                         f"<td class='muted'>{esc(HAZARDS[h].note)}</td></tr>")

    cov = ""
    if "readiness" in meta and result.get("report_log", {}).get("mode") != "llm":  # the AI narrative already carries this section
        cov = f'<div class="narr">{md_to_html(readiness_markdown(meta["readiness"]))}</div>'
    if result.get("report_log", {}).get("mode") == "llm":
        narrative = f'<h2>Analyst narrative</h2><div class="narr">{md_to_html(result["report_md"])}</div><p class="note">Written by an AI model from the figures above. Check it before sharing.</p>'
    else:
        narrative = ""

    src = "".join(f"<li>{esc(d)}. <span class='muted'>{esc(a)}</span></li>" for d, a in _sources(meta))
    loss_section = (
        f"<h2>Where the scenario loss comes from</h2>{svg_bars(loss_items)}"
        if loss_state.get("allowed")
        else '<h2>Financial loss estimates</h2><p class="note">Withheld by the model-publication policy until the damage functions have empirical validation evidence.</p>'
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(name)} - Physical climate risk assessment</title><style>:root{{--brand:{color}}}{CSS}</style></head><body><div class="page">
<div class="cover"><div class="org">{esc(name)}</div><h1>Physical climate risk assessment</h1>
<p>{esc(meta.get('scenario_label', ''))} · {esc(time.strftime('%d %B %Y'))} · {s['n_assets']} assets</p></div>
{banner}{loss_banner}<p>{esc(summary_sentence(s, meta))}</p><div class="kpis">{kpis}</div>
<h2>Severity by hazard</h2>{svg_stacked(sev_rows)}
<p class="note">Severity: Low under 25, Medium 25 to 49, High 50 to 74, Critical 75 and above (screening thresholds). Hatched or dashed means synthetic input or no data.</p>
{loss_section}
<p class="note">Only flood, wind, fire and heat have a damage function. River flood, drought and landslide are hazard indices and add no loss.</p>
<h2>Assets that need attention</h2>{top_html}
{cov}<h2>What each hazard measures</h2><table><tbody>{''.join(notes)}</tbody></table>
{narrative}
<h2>How to read this report</h2>
<p class="note">Model status: experimental. Damage-function parameters are assumed and not validated, so results are not defensible probabilities of damage. This is a screening assessment. Damage curves are transparent defaults, not calibrated to observed losses. Loss is a scenario figure, not an annual expected loss. Source quality ranks data by resolution and directness and is not a probability. Future scenarios use a single climate model or fixed uplifts, not a full ensemble. A qualified professional should review it before external disclosure.</p>
<h2>Data sources and attribution</h2><ul class="note">{src}</ul>
<footer>{esc(brand.get('footer') or name)} · Generated {esc(time.strftime('%Y-%m-%d %H:%M'))}. Not an engineering study, actuarial valuation, or legal advice.</footer>
</div></body></html>"""
