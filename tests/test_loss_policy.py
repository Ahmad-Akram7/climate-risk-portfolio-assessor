import os

import pandas as pd

from src.loss_policy import apply_loss_publication_policy, can_publish_losses, publication_state


def test_experimental_registry_hides_losses_by_default(monkeypatch):
    monkeypatch.delenv("CRPA_ALLOW_EXPERIMENTAL_LOSSES", raising=False)
    funcs = [{"validation_status": "experimental", "validation_reference": None}]
    assert not can_publish_losses(funcs)
    assert publication_state(funcs)["status"] == "withheld_experimental"


def test_override_is_explicit_and_does_not_change_validation(monkeypatch):
    monkeypatch.setenv("CRPA_ALLOW_EXPERIMENTAL_LOSSES", "1")
    funcs = [{"validation_status": "experimental", "validation_reference": None}]
    state = publication_state(funcs)
    assert can_publish_losses(funcs)
    assert state["override_used"] is True
    assert "INTERNAL OVERRIDE" in state["note"]
    assert funcs[0]["validation_status"] == "experimental"


def test_mixed_or_missing_registry_metadata_fails_closed(monkeypatch):
    monkeypatch.delenv("CRPA_ALLOW_EXPERIMENTAL_LOSSES", raising=False)
    assert not can_publish_losses([
        {"validation_status": "empirically_validated", "validation_reference": "study"},
        {"validation_status": "experimental", "validation_reference": None},
    ])
    assert not can_publish_losses([])
    assert not can_publish_losses([{"validation_status": "empirically_validated"}])


def test_loss_gate_masks_usd_losses_everywhere_but_keeps_risk_metrics(monkeypatch):
    monkeypatch.delenv("CRPA_ALLOW_EXPERIMENTAL_LOSSES", raising=False)
    summary = {
        "total_replacement_value_usd": 1000,
        "total_expected_loss_usd": 120,
        "expected_loss_pct_of_value": 12.0,
        "hazard_summary": {"flood": {"scenario_loss_usd": 90}},
        "top_assets": [{"expected_loss_usd": 120}],
        "flood_aal_usd": 20,
        "mean_risk_score": 55,
    }
    assets = pd.DataFrame({"replacement_value": [1000], "expected_loss_usd": [120], "loss_flood_usd": [90], "risk_score": [55]})
    safe_summary, safe_assets, state = apply_loss_publication_policy(
        summary, assets, [{"validation_status": "experimental", "validation_reference": None}]
    )
    assert state["allowed"] is False
    assert safe_summary["total_replacement_value_usd"] == 1000
    assert safe_summary["total_expected_loss_usd"] is None
    assert safe_summary["expected_loss_pct_of_value"] is None
    assert safe_summary["hazard_summary"]["flood"]["scenario_loss_usd"] is None
    assert safe_summary["top_assets"][0]["expected_loss_usd"] is None
    assert safe_summary["flood_aal_usd"] is None
    assert safe_summary["mean_risk_score"] == 55
    assert pd.isna(safe_assets.loc[0, "expected_loss_usd"])
    assert pd.isna(safe_assets.loc[0, "loss_flood_usd"])
    assert safe_assets.loc[0, "risk_score"] == 55


def test_override_keeps_figures_but_marks_them_experimental(monkeypatch):
    monkeypatch.setenv("CRPA_ALLOW_EXPERIMENTAL_LOSSES", "1")
    summary = {"total_expected_loss_usd": 120}
    assets = pd.DataFrame({"expected_loss_usd": [120]})
    safe_summary, safe_assets, state = apply_loss_publication_policy(
        summary, assets, [{"validation_status": "experimental", "validation_reference": None}]
    )
    assert safe_summary["total_expected_loss_usd"] == 120
    assert safe_assets.loc[0, "expected_loss_usd"] == 120
    assert state["override_used"] is True
