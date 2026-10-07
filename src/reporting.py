"""Stage 4 - disclosure-style report. LLM (OpenAI-compatible, default NVIDIA Nemotron 3.5) with deterministic fallback."""
from __future__ import annotations

import json
import time

import requests

from . import config


def _llm_error(exc: Exception, response: requests.Response | None = None) -> str:
    """Return an actionable provider error without exposing credentials."""
    if isinstance(exc, requests.ReadTimeout):
        return (f"NVIDIA did not respond within {config.LLM_TIMEOUT:g}s. "
                "Retry once; if it persists, set LLM_MODEL to a faster NVIDIA hosted model or use the deterministic report.")
    if isinstance(exc, requests.HTTPError) and response is not None:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        if response.status_code == 401 or response.status_code == 403:
            return (f"NVIDIA authorization failed ({response.status_code}): {detail or 'invalid or expired API key'}. "
                    "Create a new NVIDIA API key and replace NVIDIA_API_KEY in .env, then restart the app.")
        if detail:
            return f"NVIDIA request failed ({response.status_code}): {detail}"
    return f"{type(exc).__name__}: {exc}"

FRAMEWORKS = {
    "SEC": "SEC climate-related disclosure (Regulation S-K style: material physical risks, location/concentration, financial impact)",
    "CSRD": "EU CSRD / ESRS E1 (physical risk exposure by hazard, asset-level analysis, scenario analysis)",
    "ISSB": "ISSB IFRS S2 (climate-related physical risks, scenario analysis, financial effects)",
}
DISCLAIMER = ("This report is an automated screening-level assessment generated from the supplied asset list. It is not "
              "an engineering study, actuarial valuation, or legal/regulatory advice. Review by qualified professionals "
              "is required before any external disclosure.")


def _usd(x: float) -> str:
    return f"${x/1e9:.2f}B" if x >= 1e9 else f"${x/1e6:.1f}M" if x >= 1e6 else f"${x:,.0f}"


def _confidence_text(meta: dict) -> str:
    c = meta["confidence"]
    if c >= 0.8:
        return f"Hazard inputs are predominantly real data (confidence {c:.2f})."
    if c >= 0.3:
        return f"Hazard inputs are a mix of real and synthetic data (confidence {c:.2f}); treat results as indicative."
    return (f"**Hazard inputs are mostly SYNTHETIC demo data (confidence {c:.2f}). "
            "Results illustrate the method only and must not be used for decisions or disclosure.**")


def deterministic_report(summary: dict, meta: dict, frameworks: list[str]) -> str:
    s = summary
    tiers = s["tier_counts"]
    hz = sorted(s["mean_hazard_probability"].items(), key=lambda kv: -kv[1])
    conc = list(s["state_concentration_pct"].items())[:3]
    top = s["top_assets"][:3]
    L = [f"# Physical Climate Risk Assessment", "",
         f"*Scenario: {meta['scenario_label']} - generated {time.strftime('%Y-%m-%d')}*", "",
         "## 1. Executive summary", "",
         f"The portfolio contains {s['n_assets']} assets with a total replacement value of "
         f"{_usd(s['total_replacement_value_usd'])}. Modelled scenario expected loss is "
         f"{_usd(s['total_expected_loss_usd'])} ({s['expected_loss_pct_of_value']}% of value). "
         f"The value-weighted risk score is {s['value_weighted_risk_score']}/100. "
         f"{tiers.get('Critical', 0)} asset(s) are rated Critical, {tiers.get('High', 0)} High, "
         f"{tiers.get('Medium', 0)} Medium and {tiers.get('Low', 0)} Low.", "",
         _confidence_text(meta), "",
         "## 2. Methodology and data sources", "",
         "Assets are validated and spatially quality-checked, then hazard intensities are attached for flood, wind, "
         "wildfire, extreme heat and elevation. Intensities are converted to damage probabilities with sigmoid "
         "fragility curves, combined across hazards with a survival model, and multiplied by an asset-class "
         "criticality factor. Expected loss is probability x loss ratio x replacement value.", ""]
    srcs = meta.get("source_counts", {})
    for h, d in srcs.items():
        L.append(f"- {h}: " + ", ".join(f"{k} ({v} assets)" for k, v in d.items()))
    L += ["", "## 3. Material risk findings", "",
          "Average damage probability by hazard: " + ", ".join(f"{h} {p:.1%}" for h, p in hz) + ".", ""]
    if conc:
        L.append("Geographic concentration: " + ", ".join(f"{st} {p}% of value" for st, p in conc) + ".")
        L.append("")
    L.append("Highest-risk assets:")
    L.append("")
    for t in top:
        L.append(f"- {t['name']} ({t['asset_id']}, {t['state']}, {t['asset_class']}): score {t['risk_score']}, "
                 f"{t['risk_tier']}, driven by {t['dominant_hazard']}, modelled loss {_usd(t['expected_loss_usd'])}.")
    L += ["", "## 4. Recommended mitigation strategies", ""]
    dom = max(s["dominant_hazard_counts"].items(), key=lambda kv: kv[1])[0] if s["dominant_hazard_counts"] else "none"
    tips = {"flood": "elevate critical equipment, install flood barriers, review flood insurance and drainage.",
            "wind": "upgrade roof and envelope connections, shutters/impact glazing, and wind-rated rooftop equipment.",
            "wildfire": "create defensible space, use ember-resistant vents and Class A roofing, and review brigade access.",
            "heat": "review cooling capacity and redundancy, and plan for grid-outage resilience.",
            "none": "no dominant hazard identified; maintain monitoring."}
    L.append(f"The most common dominant hazard is {dom}: {tips.get(dom, tips['none'])} "
             "Prioritise Critical and High tier assets and reassess after mitigation.")
    L += ["", "## 5. Framework alignment", ""]
    for f in frameworks:
        L.append(f"- {f}: {FRAMEWORKS.get(f, f)}.")
    L += ["", "## 6. Limitations and caveats", "",
          "Fragility parameters are uncalibrated defaults; the loss figure is scenario-based, not annual expected loss. "
          "Coordinates are treated as points; building-level attributes (age, construction, floor height) are not used. "
          "Future scenarios apply simple parametric uplifts rather than downscaled climate-model output. "
          "Regulatory requirements change; confirm current applicability of each framework with counsel.", "",
          f"> {DISCLAIMER}"]
    return "\n".join(L)


def _llm_prompt(summary: dict, meta: dict, frameworks: list[str]) -> list[dict]:
    ctx = json.dumps({"summary": summary, "data_meta": meta}, default=str)[:12000]
    sys = ("You are a climate-risk analyst writing a screening-level physical climate risk report. Use ONLY the figures in "
           "the JSON provided; never invent numbers, sources or regulations. If data confidence is below 0.8 say so "
           "prominently. Write in prose with markdown headings.")
    usr = (f"Write a report aligned to: {', '.join(frameworks)}. Sections: Executive summary; Methodology and data "
           "sources; Material risk findings; Recommended mitigation strategies; Limitations and caveats. "
           f"End with this disclaimer verbatim: {DISCLAIMER}\n\nDATA:\n{ctx}")
    return [{"role": "system", "content": sys}, {"role": "user", "content": usr}]


def generate_report(summary: dict, meta: dict, frameworks: list[str] | None = None, use_llm: bool = True) -> dict:
    frameworks = frameworks or ["SEC", "CSRD", "ISSB"]
    log = {"mode": "deterministic", "model": None, "tokens": None, "error": None, "frameworks": frameworks}
    key = config.key("NVIDIA_API_KEY") or config.key("LLM_API_KEY")
    md = None
    if use_llm and key and not config.OFFLINE:
        msgs = _llm_prompt(summary, meta, frameworks)
        log["prompt"] = msgs
        try:
            r = requests.post(f"{config.LLM_BASE_URL}/chat/completions", timeout=config.LLM_TIMEOUT,
                              headers={"Authorization": f"Bearer {key}"},
                              json={"model": config.LLM_MODEL, "messages": msgs, "temperature": 0.2, "max_tokens": 1200,
                                    "stream": False})
            r.raise_for_status()
            j = r.json()
            md = j["choices"][0]["message"]["content"].strip()
            log.update(mode="llm", model=config.LLM_MODEL, tokens=j.get("usage"), response=md)
            if DISCLAIMER not in md:
                md += f"\n\n> {DISCLAIMER}"
            if meta["confidence"] < 0.8 and "synthetic" not in md.lower():
                md = f"> **Data note:** {_confidence_text(meta)}\n\n" + md
        except Exception as e:  # network, auth, schema - always fall back
            log["error"] = _llm_error(e, locals().get("r"))
            md = None
    if md is None:
        md = deterministic_report(summary, meta, frameworks)
    return {"markdown": md, "log": log}
