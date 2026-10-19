"""Publication policy for experimental monetary loss estimates.

Risk indices remain available for screening. Monetary loss outputs are withheld unless
all registered damage functions are empirically validated with an evidence reference,
or an explicit internal-only environment override is set.
"""
from __future__ import annotations

import copy
import logging
import os

import pandas as pd

from .vulnerability_registry import REGISTRY


OVERRIDE_ENV = "CRPA_ALLOW_EXPERIMENTAL_LOSSES"
_VALIDATED = "empirically_validated"


def allow_experimental_losses() -> bool:
    """Explicit opt-in for internal research only; default is fail-closed."""
    return os.getenv(OVERRIDE_ENV, "").strip() == "1"


def can_publish_losses(functions=None) -> bool:
    """Return true only when every function has empirical validation evidence, or override is explicit."""
    entries = list(REGISTRY if functions is None else functions)
    if entries and all(
        f.get("validation_status") == _VALIDATED and bool(f.get("validation_reference"))
        for f in entries
    ):
        return True
    return allow_experimental_losses()


def publication_state(functions=None) -> dict:
    entries = list(REGISTRY if functions is None else functions)
    empirically_validated = bool(entries) and all(
        f.get("validation_status") == _VALIDATED and bool(f.get("validation_reference"))
        for f in entries
    )
    override = allow_experimental_losses()
    allowed = empirically_validated or override
    if override and not empirically_validated:
        logging.getLogger(__name__).warning("%s=1: exposing experimental, unvalidated monetary loss estimates; internal research only", OVERRIDE_ENV)
    if empirically_validated:
        status = "published_validated"
        note = "Monetary estimates are enabled because all registered damage functions have empirical validation references."
    elif override:
        status = "override_experimental"
        note = "INTERNAL OVERRIDE: monetary estimates use experimental, unvalidated damage functions. Do not use for client reporting or disclosure."
    else:
        status = "withheld_experimental"
        note = "Monetary loss estimates are withheld because one or more damage functions are experimental or lack empirical validation evidence. Hazard metrics and screening risk scores remain available."
    return {"allowed": allowed, "status": status, "override_used": bool(override and not empirically_validated), "note": note}


def _mask_summary(value):
    """Recursively suppress USD loss values and loss-share percentages, preserving asset replacement values."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "total_replacement_value_usd":
                out[key] = item
            elif key.endswith("_usd") or key == "expected_loss_pct_of_value":
                out[key] = None
            else:
                out[key] = _mask_summary(item)
        return out
    if isinstance(value, list):
        return [_mask_summary(item) for item in value]
    return value


def apply_loss_publication_policy(summary: dict, assets: pd.DataFrame, functions=None):
    """Return safe copies for reports, exports, dashboard and API; never mutate calculation inputs."""
    state = publication_state(functions)
    safe_summary = copy.deepcopy(summary)
    safe_assets = assets.copy()
    safe_summary["loss_publication"] = state
    if not state["allowed"]:
        safe_summary = _mask_summary(safe_summary)
        safe_summary["loss_publication"] = state
        for col in safe_assets.columns:
            if col.endswith("_usd") and col != "total_replacement_value_usd":
                safe_assets[col] = float("nan")
            else:
                # Flood-event details are nested dictionaries inside a DataFrame object column.
                safe_assets[col] = safe_assets[col].map(
                    lambda item: _mask_summary(item) if isinstance(item, (dict, list)) else item
                )
    return safe_summary, safe_assets, state
