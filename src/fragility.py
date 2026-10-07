"""Stage 3 - fragility engine and risk scoring.

Transparent, HAZUS-*inspired* sigmoid curves (NOT calibrated HAZUS parameters):
    P(damage | x) = (S(x) - S(0)) / (1 - S(0)),   S(x) = 1 / (1 + exp(-k (x - x0)))
Normalising by S(0) makes P(0) = 0 so "no hazard" means "no damage".
All parameters are in CURVES below - edit them to calibrate against your own vulnerability data.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

# hazard: (input column, k, x0, max loss ratio if damaged, composite weight, unit)
CURVES = {
    "flood":    dict(col="flood_depth_m_eff", k=1.5,  x0=1.8,  max_loss=0.35, unit="m depth"),
    "wind":     dict(col="wind_ms",           k=0.16, x0=55.0, max_loss=0.40, unit="m/s gust"),
    "wildfire": dict(col="wildfire_score",    k=0.08, x0=70.0, max_loss=0.70, unit="0-100 score"),
    "heat":     dict(col="heat_c",            k=0.50, x0=48.0, max_loss=0.10, unit="deg C"),
}

# multiplier on score and loss (consequence of failure / business interruption)
CRITICALITY = {"hospital": 1.5, "data_center": 1.3, "infrastructure": 1.25, "industrial": 1.05,
               "hotel": 1.0, "office": 1.0, "retail": 1.0, "residential": 0.95, "other": 1.0}

TIERS = [(75, "Critical"), (50, "High"), (25, "Medium"), (0, "Low")]


def sigmoid_damage(x, k: float, x0: float):
    x = np.asarray(x, dtype=float)
    s = lambda v: 1.0 / (1.0 + np.exp(-k * (v - x0)))
    s0 = s(0.0)
    return np.clip((s(x) - s0) / (1 - s0), 0.0, 1.0)


def tier(score: float) -> str:
    for thr, name in TIERS:
        if score >= thr:
            return name
    return "Low"


def score_assets(assets: pd.DataFrame, hazards: pd.DataFrame) -> pd.DataFrame:
    df = assets.merge(hazards, on="asset_id", how="left", suffixes=("", "_h"))
    # low-lying ground inside a mapped flood zone gets extra effective depth
    low = (df["elevation_m"] < 3) & (~df["flood_zone"].isin(["X", "X_SHADED"]))
    df["flood_depth_m_eff"] = df["flood_depth_m"] + np.where(low, 0.3, 0.0)

    surv = np.ones(len(df))
    loss_ratio = np.zeros(len(df))
    for hz, c in CURVES.items():
        if hz == "flood" and "flood_damage_ratio" in df:
            p = df["flood_damage_ratio"].fillna(0.0).clip(0.0, 1.0).values
        else:
            p = sigmoid_damage(df[c["col"]].values, c["k"], c["x0"])
        df[f"p_{hz}"] = np.round(p, 4)
        surv *= (1 - p)
        loss_ratio += p * c["max_loss"]
    crit = df["asset_class"].map(CRITICALITY).fillna(1.0).values
    df["criticality"] = crit
    df["p_any"] = np.round(1 - surv, 4)  # survival model: P(at least one hazard damages the asset)
    df["risk_score"] = np.round(np.minimum(100.0, 100 * df["p_any"].values * crit), 1)
    df["loss_ratio"] = np.minimum(1.0, loss_ratio * crit)
    df["expected_loss_usd"] = np.round(df["loss_ratio"] * df["replacement_value"], 0)
    df["risk_tier"] = df["risk_score"].apply(tier)

    contrib = df[[f"p_{h}" for h in CURVES]].copy()
    contrib.columns = list(CURVES)
    df["dominant_hazard"] = contrib.idxmax(axis=1).where(contrib.max(axis=1) > 0.01, "none")
    return df.drop(columns=["flood_depth_m_eff"])


def portfolio_summary(df: pd.DataFrame, meta: dict) -> dict:
    tv = float(df["replacement_value"].sum())
    el = float(df["expected_loss_usd"].sum())
    by_state = df.groupby("state")["replacement_value"].sum().sort_values(ascending=False)
    top = df.sort_values("risk_score", ascending=False).head(5)
    return {
        "n_assets": int(len(df)),
        "total_replacement_value_usd": tv,
        "total_expected_loss_usd": el,
        "expected_loss_pct_of_value": round(100 * el / tv, 2) if tv else 0.0,
        "value_weighted_risk_score": round(float((df["risk_score"] * df["replacement_value"]).sum() / tv), 1) if tv else 0.0,
        "mean_risk_score": round(float(df["risk_score"].mean()), 1),
        "tier_counts": df["risk_tier"].value_counts().reindex(["Critical", "High", "Medium", "Low"], fill_value=0).to_dict(),
        "mean_hazard_probability": {h: round(float(df[f"p_{h}"].mean()), 3) for h in CURVES},
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
        "flood_aal_usd": round(float(df["flood_aal_usd"].sum()) if "flood_aal_usd" in df else 0.0, 2),
        "flood_pml_100_usd": round(float(df["flood_pml_100_usd"].sum()) if "flood_pml_100_usd" in df else 0.0, 2),
        "flood_pml_500_usd": round(float(df["flood_pml_500_usd"].sum()) if "flood_pml_500_usd" in df else 0.0, 2),
    }
