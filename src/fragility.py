"""Stage 3 - vulnerability, risk scoring and severity.

Layers (kept separate in the output columns):
    Hazard         site intensity (flood depth, gust, temperature, ...) and ``hazard_index_<h>`` (0-100)
                   = the damage curve evaluated at the site intensity for a generic asset.
    Exposure       replacement value and a consequence factor by asset class (``criticality``).
    Vulnerability  mean damage ratio ``vuln_<h>`` (0-1). For flood it is asset-specific when the flood engine
                   produced a return-period event (first-floor height, archetype); otherwise a generic curve.
    Risk           ``risk_<h>`` = 100 x P(damage) x consequence factor, and ``severity_<h>`` from TIERS.
                   ``risk_score`` combines the damage hazards: 100 x P(any) x consequence factor.
    Financial      ``expected_loss_usd`` = scenario loss ratio x replacement value. This is a scenario loss,
                   not an annual expected loss, and it is kept apart from the physical risk score.

Curves are transparent, HAZUS-*inspired* sigmoids (NOT calibrated HAZUS parameters):
    P(damage | x) = (S(x) - S(0)) / (1 - S(0)),   S(x) = 1 / (1 + exp(-k (x - x0)))
All parameters live in CURVES - edit them to calibrate against your own vulnerability data.

Missing data is never scored as zero risk: a hazard without an input is ``not_assessed`` and excluded from
the combined score; a hazard backed only by synthetic input is ``illustrative``.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from .hazard_registry import (
    ALL_HAZARDS,
    DAMAGE_HAZARDS,
    INDEX_HAZARDS,
    NOT_ASSESSED,
    SEVERITY_ORDER,
    source_weight,
)
from .vulnerability_registry import REGISTRY, overall_status

# hazard: input column, k, x0, max loss ratio if damaged, unit
CURVES = {
    "flood":    dict(col="flood_depth_m_eff", k=1.5,  x0=1.8,  max_loss=0.35, unit="m depth"),
    "wind":     dict(col="wind_ms",           k=0.16, x0=55.0, max_loss=0.40, unit="m/s gust"),
    "wildfire": dict(col="wildfire_score",    k=0.08, x0=70.0, max_loss=0.70, unit="0-100 score"),
    "heat":     dict(col="heat_c",            k=0.50, x0=48.0, max_loss=0.10, unit="deg C"),
}

# Optional user calibration: data/calibration/fragility.json, e.g. {"wind": {"k": 0.2, "x0": 60, "max_loss": 0.35}}.
# Use it to replace the uncalibrated defaults with parameters fitted to your own loss or claims data.
def _load_overrides() -> str:
    import json

    from . import config
    path = config.DATA_DIR / "calibration" / "fragility.json"
    if not path.exists():
        return "default (uncalibrated)"
    try:
        data = json.loads(path.read_text())
        for hz, vals in data.items():
            if hz not in CURVES or not isinstance(vals, dict):
                raise ValueError(f"unknown hazard {hz!r}")
            for key, v in vals.items():
                if key not in ("k", "x0", "max_loss") or not isinstance(v, (int, float)) or isinstance(v, bool):
                    raise ValueError(f"bad parameter {hz}.{key}")
            if not 0 < vals.get("max_loss", CURVES[hz]["max_loss"]) <= 1 or vals.get("k", CURVES[hz]["k"]) <= 0:
                raise ValueError(f"{hz}: k must be above 0 and max_loss in (0, 1]")
            CURVES[hz].update(vals)
        return "user calibration file"
    except Exception as e:  # a bad file must not silently change results
        warnings.warn(f"Ignoring {path.name}: {e}", stacklevel=2)
        return "default (uncalibrated)"


# Hazard-only indices: (input column, value at index 0, value at index 100). Linear between. Screening thresholds,
# not validated; the drought index is the length of the dry spell, not a drought anomaly (SPI/SPEI).
INDEX_SCALES = {
    "drought":   dict(col="drought_cdd_days", lo=30.0, hi=180.0),
    "landslide": dict(col="landslide_index",  lo=0.0,   hi=100.0),
    "river":     dict(col="river_flood_ratio", lo=2.0,  hi=20.0),
}

CURVE_SOURCE = _load_overrides()

# Building-attribute adjustment to the wind curve midpoint (m/s). Assumed screening values, NOT calibrated to
# loss data. They apply only when the attribute is supplied; otherwise the generic curve is used.
WIND_CONSTRUCTION_SHIFT = [("mobile", -10.0), ("temporary", -10.0), ("timber", -5.0), ("wood", -5.0),
                           ("light", -5.0), ("unreinforced", -4.0), ("masonry", -3.0), ("brick", -3.0),
                           ("steel", 2.0), ("reinforced", 4.0), ("concrete", 4.0), ("rc", 4.0)]


def wind_vulnerability_shift(df: pd.DataFrame) -> np.ndarray:
    """Shift of the wind-curve midpoint per asset from construction type, year built and height. 0 when unknown."""
    n = len(df)
    shift = np.zeros(n)
    ctype = df["construction_type"].fillna("").astype(str).str.lower() if "construction_type" in df else pd.Series([""] * n)
    for i, t in enumerate(ctype):
        shift[i] += next((v for key, v in WIND_CONSTRUCTION_SHIFT if key in t), 0.0)
    yr = _num(df, "year_built")
    shift += np.where(yr < 1980, -3.0, 0.0) + np.where(yr >= 2010, 2.0, 0.0)
    h = _num(df, "building_height_m")
    st = _num(df, "stories")
    tall = (h >= 30) | (st >= 8)
    shift += np.where(tall, -2.0, 0.0)
    return np.clip(shift, -12.0, 8.0)


# multiplier on score and loss (consequence of failure / business interruption)
CRITICALITY = {"hospital": 1.5, "data_center": 1.3, "infrastructure": 1.25, "industrial": 1.05,
               "hotel": 1.0, "office": 1.0, "retail": 1.0, "residential": 0.95, "other": 1.0}

TIERS = [(75, "Critical"), (50, "High"), (25, "Medium"), (0, "Low")]
SENSITIVITY = 0.15  # +/-15% on hazard intensity (flood engine: on damage ratio). Parameter sensitivity, NOT a confidence interval.


def sigmoid_damage(x, k: float, x0: float):
    x = np.asarray(x, dtype=float)
    s = lambda v: 1.0 / (1.0 + np.exp(-k * (v - x0)))
    s0 = s(0.0)
    return np.clip((s(x) - s0) / (1 - s0), 0.0, 1.0)  # NaN stays NaN


def tier(score: float) -> str:
    if score is None or score != score:
        return NOT_ASSESSED
    for thr, name in TIERS:
        if score >= thr:
            return name
    return "Low"


def _num(df: pd.DataFrame, col: str) -> np.ndarray:
    if col not in df:
        return np.full(len(df), np.nan)
    return pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)


def _status_and_conf(df: pd.DataFrame, hz: str, intensity: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    src = f"src_{hz}"
    conf = (df[src].map(source_weight).to_numpy(dtype=float) if src in df else np.full(len(df), np.nan))
    status = np.where(np.isnan(intensity), "not_assessed", np.where(conf == 0, "illustrative", "assessed"))
    conf = np.where(status == "not_assessed", np.nan, conf)
    return status, conf


def _damage_probs(df: pd.DataFrame, intensities: dict, factor: float = 1.0) -> dict:
    """P(damage) per damage hazard. `factor` scales intensity (flood engine: the damage ratio) for sensitivity runs."""
    probs = {}
    engine = pd.to_numeric(df["flood_damage_ratio"], errors="coerce").to_numpy(dtype=float) \
        if "flood_damage_ratio" in df else np.full(len(df), np.nan)
    for hz, c in CURVES.items():
        x0 = c["x0"] + (df["wind_x0_shift"].to_numpy(dtype=float) if hz == "wind" and "wind_x0_shift" in df else 0.0)
        p = sigmoid_damage(intensities[hz] * factor, c["k"], x0)
        if hz == "flood":
            # Flood engine ratio is already a loss ratio; dividing by max_loss gives a probability comparable with
            # the other hazards (loss ratio = p x max_loss), so the loss is not scaled by max_loss twice.
            eng_p = np.clip(engine * factor / c["max_loss"], 0.0, 1.0)
            p = np.where(np.isnan(engine), p, eng_p)
        probs[hz] = p
    return probs


def _combine(probs: dict, crit: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Survival model over the hazards that have data: P(any) = 1 - prod(1 - p_i). NaN if no hazard has data."""
    arr = np.vstack([probs[h] for h in DAMAGE_HAZARDS])
    have = ~np.isnan(arr)
    p_any = 1 - np.prod(np.where(have, 1 - np.nan_to_num(arr), 1.0), axis=0)
    p_any = np.where(have.any(axis=0), p_any, np.nan)
    return p_any, np.minimum(100.0, 100 * p_any * crit)


def score_assets(assets: pd.DataFrame, hazards: pd.DataFrame) -> pd.DataFrame:
    df = assets.merge(hazards, on="asset_id", how="left", suffixes=("", "_h"))
    n = len(df)
    # low-lying ground inside a mapped flood zone gets extra effective depth (site rule, applied to the zone proxy)
    elev = _num(df, "elevation_m")
    zone_ok = ~df["flood_zone"].isin(["X", "X_SHADED"]) if "flood_zone" in df else np.zeros(n, bool)
    low = (elev < 3) & zone_ok.to_numpy()
    df["flood_depth_m_eff"] = _num(df, "flood_depth_m") + np.where(low, 0.3, 0.0)

    crit = df["asset_class"].map(CRITICALITY).fillna(1.0).to_numpy(dtype=float)
    df["criticality"] = crit
    value = _num(df, "replacement_value")
    intens = {hz: _num(df, c["col"]) for hz, c in CURVES.items()}
    df["wind_x0_shift"] = wind_vulnerability_shift(df)
    df["vulnerability_basis"] = np.where(df["wind_x0_shift"] != 0, "building attributes (assumed, uncalibrated)", "generic curve")
    probs = _damage_probs(df, intens)

    loss_ratio = np.zeros(n)
    statuses, confs = {}, {}
    for hz, c in CURVES.items():
        p = probs[hz]
        status, conf = _status_and_conf(df, hz, intens[hz])
        statuses[hz], confs[hz] = status, conf
        df[f"p_{hz}"] = np.round(p, 4)
        df[f"hazard_index_{hz}"] = np.round(100 * sigmoid_damage(intens[hz], c["k"], c["x0"]), 1)
        mdr = p * c["max_loss"]
        df[f"vuln_{hz}"] = np.round(mdr, 4)
        risk = np.minimum(100.0, 100 * p * crit)
        df[f"risk_{hz}"] = np.round(risk, 1)
        df[f"loss_{hz}_usd"] = np.round(np.minimum(1.0, mdr * crit) * value, 0)
        loss_ratio += np.nan_to_num(mdr)
    for hz in INDEX_HAZARDS:
        sc = INDEX_SCALES[hz]
        x = _num(df, sc["col"])
        idx = np.clip(100 * (x - sc["lo"]) / (sc["hi"] - sc["lo"]), 0, 100)
        status, conf = _status_and_conf(df, hz, x)
        statuses[hz], confs[hz] = status, conf
        df[f"hazard_index_{hz}"] = np.round(idx, 1)
        df[f"risk_{hz}"] = np.round(idx, 1)  # hazard-only: severity follows the hazard index (see HazardSpec.basis)

    for hz in ALL_HAZARDS:
        df[f"status_{hz}"] = statuses[hz]
        df[f"confidence_{hz}"] = np.round(confs[hz], 2)
        df[f"severity_{hz}"] = [tier(v) if s != "not_assessed" else NOT_ASSESSED
                                for v, s in zip(df[f"risk_{hz}"], statuses[hz])]

    # ---- combined (damage hazards only) ----
    p_any, score = _combine(probs, crit)
    df["p_any"] = np.round(p_any, 4)
    df["risk_score"] = np.round(score, 1)
    lo_f, hi_f = 1 - SENSITIVITY, 1 + SENSITIVITY
    df["risk_score_low"] = np.round(_combine(_damage_probs(df, intens, lo_f), crit)[1], 1)
    df["risk_score_high"] = np.round(_combine(_damage_probs(df, intens, hi_f), crit)[1], 1)
    df["loss_ratio"] = np.minimum(1.0, loss_ratio * crit)
    df["expected_loss_usd"] = np.round(df["loss_ratio"] * value, 0)
    df["risk_tier"] = df["risk_score"].apply(tier)

    st = np.vstack([statuses[h] for h in DAMAGE_HAZARDS])
    n_ass, n_ill, n_na = (st == "assessed").sum(0), (st == "illustrative").sum(0), (st == "not_assessed").sum(0)
    df["n_hazards_assessed"] = n_ass + n_ill
    df["overall_status"] = np.select(
        [n_ass + n_ill == 0, n_ass == 0, (n_ill == 0) & (n_na == 0)],
        ["not_assessed", "illustrative", "assessed"], default="partial")
    cf = np.vstack([confs[h] for h in DAMAGE_HAZARDS])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN column = no hazard assessed -> NaN confidence
        overall_conf = np.nanmean(cf, axis=0)
    df["overall_confidence"] = np.round(overall_conf, 2)
    # Green "Low" is only earned with real data on every damage hazard and at least medium source quality.
    df["low_risk_verified"] = ((df["risk_tier"] == "Low") & (df["overall_status"] == "assessed")
                               & (df["overall_confidence"] >= 0.5))

    # dominant hazard = highest per-hazard score among hazards that have data
    risks = pd.DataFrame({h: np.where(statuses[h] == "not_assessed", np.nan, df[f"risk_{h}"]) for h in ALL_HAZARDS})
    top = risks.max(axis=1)
    dom = risks.fillna(-1).idxmax(axis=1)
    df["dominant_hazard"] = np.where(top.isna(), "not_assessed", np.where(top >= 1, dom, "none"))
    return df.drop(columns=["flood_depth_m_eff"])


def _sum(df: pd.DataFrame, col: str) -> float:
    return float(pd.to_numeric(df[col], errors="coerce").sum()) if col in df else 0.0


def portfolio_summary(df: pd.DataFrame, meta: dict) -> dict:
    tv = float(df["replacement_value"].sum())
    el = float(df["expected_loss_usd"].sum())
    by_state = df.groupby("state")["replacement_value"].sum().sort_values(ascending=False)
    top = df.sort_values("risk_score", ascending=False, na_position="last").head(5)
    hazard_summary = {}
    for h in ALL_HAZARDS:
        stat = df[f"status_{h}"].value_counts()
        sev = df.loc[df[f"status_{h}"] != "not_assessed", f"severity_{h}"].value_counts()
        hazard_summary[h] = {
            "status_counts": {k: int(stat.get(k, 0)) for k in ("assessed", "illustrative", "not_assessed")},
            "severity_counts": {k: int(sev.get(k, 0)) for k in SEVERITY_ORDER},
            "mean_hazard_index": (None if df[f"status_{h}"].eq("not_assessed").all()
                                  else round(float(df.loc[df[f"status_{h}"] != "not_assessed", f"hazard_index_{h}"].mean()), 1)),
            "scenario_loss_usd": round(_sum(df, f"loss_{h}_usd"), 0) if h in DAMAGE_HAZARDS else None,
        }
    return {
        "n_assets": len(df),
        "total_replacement_value_usd": tv,
        "total_expected_loss_usd": el,
        "expected_loss_pct_of_value": round(100 * el / tv, 2) if tv else 0.0,
        "value_weighted_risk_score": round(float((df["risk_score"].fillna(0) * df["replacement_value"]).sum() / tv), 1) if tv else 0.0,
        "mean_risk_score": round(float(df["risk_score"].mean()), 1) if df["risk_score"].notna().any() else None,
        "tier_counts": df["risk_tier"].value_counts().reindex(["Critical", "High", "Medium", "Low"], fill_value=0).to_dict(),
        "not_assessed_assets": int((df["risk_tier"] == NOT_ASSESSED).sum()),
        "low_risk_verified_assets": int(df["low_risk_verified"].sum()),
        "overall_status_counts": df["overall_status"].value_counts().to_dict(),
        "hazard_summary": hazard_summary,
        "hazards_not_assessed": meta.get("hazards_not_assessed", []),
        "mean_hazard_probability": {h: round(float(df[f"p_{h}"].mean()), 3) for h in DAMAGE_HAZARDS},
        "dominant_hazard_counts": df["dominant_hazard"].value_counts().to_dict(),
        "state_concentration_pct": {s: round(100 * v / tv, 1) for s, v in by_state.items()},
        "top_assets": top[["asset_id", "name", "state", "asset_class", "risk_score", "risk_tier",
                           "dominant_hazard", "expected_loss_usd"]].to_dict("records"),
        "data_confidence": meta["confidence"],
        "scenario": meta["scenario"],
        "model_tier": meta.get("model_tier", "SCREENING"),
        "quality_gate": meta.get("quality_gate", "SCREENING ONLY"),
        "method_note": ("Current release is a transparent screening model. It uses documented hazard-specific "
                        "screening functions and asset-class modifiers; it is not a calibrated catastrophe or "
                        "actuarial annual-loss model. Missing exposure attributes remain explicit."),
        # AAL needs at least three return periods per asset; otherwise it is withheld, never shown as 0.
        "flood_aal_usd": round(_sum(df, "flood_aal_usd"), 2) if "flood_aal_usd" in df and df["flood_aal_usd"].notna().any() else None,
        "flood_aal_flat_tail_usd": round(_sum(df, "flood_aal_flat_tail_usd"), 2) if "flood_aal_flat_tail_usd" in df and df["flood_aal_flat_tail_usd"].notna().any() else None,
        "flood_event_loss_usd": round(_sum(df, "flood_event_loss_usd"), 2) if "flood_event_loss_usd" in df and df["flood_event_loss_usd"].notna().any() else None,
        "flood_loss_coverage_assets": int(df["flood_event_loss_usd"].notna().sum()) if "flood_event_loss_usd" in df else 0,
        "flood_loss_coverage_pct": round(100 * float(df["flood_event_loss_usd"].notna().mean()), 1) if "flood_event_loss_usd" in df and len(df) else 0.0,
        "model_status": overall_status(),
        "model_status_note": ("Experimental: damage-function parameters are assumed, not validated. Results are exploratory "
                              "screening, not defensible probabilities of damage or engineering-grade losses."),
        "vulnerability_functions": [{k: e[k] for k in ("function_id", "hazard", "parameter_source", "validation_status")}
                                    for e in REGISTRY],
        "loss_basis": ("Flood loss is the highest supplied return-period event (see flood_event_return_period). Wind, heat and fire "
                       "use the worst value in the climate record. These are not one common return period."),
        "flood_pml_100_usd": round(_sum(df, "flood_pml_100_usd"), 2),
        "flood_pml_500_usd": round(_sum(df, "flood_pml_500_usd"), 2),
    }
