"""Single source of truth for hazard metadata, severity scale, source-quality rubric and mitigation text.

Colour identifies the HAZARD only. Severity is a separate channel (text label + ordinal level), so a
colour-blind reader, a printout or a screen reader never has to infer severity from hue.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HazardSpec:
    key: str
    label: str
    code: str          # 3-letter text code shown beside the colour chip (non-colour cue)
    color: str         # hazard identity colour (hex); chosen for contrast on dark and light backgrounds
    intensity_col: str
    unit: str
    basis: str         # "risk" = hazard x vulnerability x consequence; "hazard_only" = hazard index, no damage function
    note: str


HAZARDS: dict[str, HazardSpec] = {
    "flood": HazardSpec("flood", "Flood", "FLD", "#3B82F6", "flood_depth_m", "m depth", "risk",
                        "Depth from a flood-zone proxy or a return-period raster; asset first-floor height used when supplied."),
    "wildfire": HazardSpec("wildfire", "Fire", "FIR", "#EF4444", "wildfire_score", "0-100 score", "risk",
                           "Burn-probability raster, or recent active-fire detections (NASA FIRMS)."),
    "heat": HazardSpec("heat", "Extreme heat", "HET", "#F97316", "heat_c", "deg C", "risk",
                       "Maximum daily temperature over the reference period."),
    "wind": HazardSpec("wind", "Wind", "WND", "#94A3B8", "wind_ms", "m/s gust", "risk",
                       "Maximum daily gust over the reference period (ERA5 reanalysis underestimates local extremes)."),
    "landslide": HazardSpec("landslide", "Landslide", "LSL", "#A855F7", "landslide_index", "0-100 index", "hazard_only",
                            "Susceptibility index from an optional local raster. No vulnerability function is applied."),
    "river": HazardSpec("river", "River flood (discharge)", "RVR", "#06B6D4", "river_flood_ratio", "Q20 / median flow", "hazard_only",
                        "Flood-peak ratio from GloFAS river discharge (about 5 km). Shows how flashy the river is, not flood depth at the site."),
    "drought": HazardSpec("drought", "Drought (dry spell)", "DRT", "#EAB308", "drought_cdd_days", "days", "hazard_only",
                          "Mean annual maximum consecutive dry days (ETCCDI CDD). Measures dry-spell length, not drought anomaly."),
}
# Hazards that have a fragility curve and feed the loss estimate.
DAMAGE_HAZARDS = ["flood", "wind", "wildfire", "heat"]
# Hazards reported as a hazard index only (no damage function, no loss).
INDEX_HAZARDS = ["drought", "landslide", "river"]
ALL_HAZARDS = DAMAGE_HAZARDS + INDEX_HAZARDS

SEVERITY_LEVELS = ["Low", "Medium", "High", "Critical"]  # ordinal 1..4
SEVERITY_ORDER = {s: i + 1 for i, s in enumerate(SEVERITY_LEVELS)}
NOT_ASSESSED = "Not assessed"

STATUS_LABEL = {
    "assessed": "Assessed (real data)",
    "illustrative": "Illustrative (synthetic input)",
    "not_assessed": "Not assessed (no data)",
}

# Judgement-based source-quality rubric (0-1). It ranks data sources by resolution and directness;
# it is NOT a statistical confidence interval. Matched by label prefix, first match wins.
SOURCE_QUALITY: list[tuple[str, float]] = [
    ("Synthetic", 0.0),
    ("JRC_RP20Y_NoMappedDepth", 0.4),     # no mapped depth is not proof of no flood
    ("JRC_Global_FloodHazard", 0.7),
    ("FEMA_NFHL", 0.8),
    ("Copernicus", 1.0),
    ("OpenTopography", 1.0),
    ("OpenMeteo_Elevation", 0.8),
    ("OpenMeteo_ERA5", 0.6),
    ("OpenMeteo_Climate", 0.6),           # CMIP6 HighResMIP delta, one model
    ("OpenMeteo_GloFAS", 0.4),            # discharge, not depth; 5 km cell              # ~10-25 km reanalysis
    ("NOAA_CDO", 0.8),
    ("NASA_FIRMS", 0.3),                  # recent detections, not a long-term hazard probability
    ("Wind_Gust_Raster_Local", 0.9),
    ("Heat_MaxTemp_C_Local", 0.9),
    ("Local_", 0.9),
]
DEFAULT_SOURCE_QUALITY = 0.5


def source_weight(label: object) -> float:
    """Quality weight for a source label. Blends ('A+B') never score above 0.5."""
    s = str(label or "")
    if not s or s.lower() in {"nan", "none", "unavailable"}:
        return 0.0
    w = next((q for prefix, q in SOURCE_QUALITY if s.startswith(prefix)), DEFAULT_SOURCE_QUALITY)
    return min(w, 0.5) if "+" in s and w > 0 else w


def confidence_class(c: float | None) -> str:
    if c is None or c != c:
        return "Unknown"
    return "High" if c >= 0.8 else "Medium" if c >= 0.5 else "Low" if c > 0 else "Synthetic"


MITIGATION: dict[str, list[str]] = {
    "flood": ["Raise critical equipment and electrical gear above the expected flood level.",
              "Fit flood barriers or sealed openings; check drainage and pump capacity.",
              "Confirm flood insurance cover and a continuity plan for the site."],
    "wind": ["Check roof and envelope connections; upgrade to impact-rated glazing or shutters.",
             "Secure or relocate rooftop plant and loose external items."],
    "wildfire": ["Create and maintain defensible space around the building.",
                 "Use ember-resistant vents and non-combustible roofing; confirm fire-service access."],
    "heat": ["Check cooling capacity and redundancy against peak temperatures.",
             "Plan for grid outage: backup power and load shedding."],
    "river": ["Commission a site-specific flood study (depth and extent) before relying on this indicator.",
              "Check the distance to the nearest river or drainage channel and the site's drainage."],
    "drought": ["Review water supply dependence and storage; plan water-use restrictions.",
                "Check for ground-movement and fire-risk effects of prolonged dry spells."],
    "landslide": ["Commission a site-specific slope stability and drainage assessment.",
                  "Avoid new loading on slopes; monitor for ground movement."],
}
MITIGATION_LOW = ["No hazard-specific action needed beyond routine monitoring."]
MITIGATION_NO_DATA = ["Add a hazard data layer or API key (Setup Wizard) before drawing any conclusion for this hazard."]


def mitigation_actions(hazard: str, severity: str, status: str) -> list[str]:
    if status == "not_assessed":
        return MITIGATION_NO_DATA
    if severity == "Low":
        return MITIGATION_LOW
    return MITIGATION.get(hazard, [])
