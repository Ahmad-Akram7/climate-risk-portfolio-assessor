"""Connector logic tested against synthetic responses. No network calls are made."""
import numpy as np
import pandas as pd

from src import config, hazards, manual_entry


def _dates(y0, y1):
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(f"{y0}-01-01", f"{y1}-12-31")]


def test_openmeteo_url_free_and_paid(monkeypatch):
    monkeypatch.delenv("OPEN_METEO_API_KEY", raising=False)
    url, extra = hazards.openmeteo_url("flood", "/v1/flood")
    assert url.startswith("https://") and "customer-" not in url and extra == {}
    monkeypatch.setenv("OPEN_METEO_API_KEY", "abc123")
    url, extra = hazards.openmeteo_url("flood", "/v1/flood")
    assert "customer-" in url and extra == {"apikey": "abc123"}


def test_series_handles_model_suffix():
    assert list(hazards._series({"temperature_2m_max_EC_Earth3P_HR": [1, 2]}, "temperature_2m_max")) == [1.0, 2.0]


def test_climate_delta_detects_warming_and_short_record():
    d = _dates(1991, 2050)
    yr = np.array([int(x[:4]) for x in d])
    tmax = 30 + 0.05 * (yr - 1991)
    wmax = np.full(len(d), 10.0)
    out = hazards.climate_delta(d, tmax, wmax)
    assert out is not None and 1.4 < out["dT"] < 1.6 and abs(out["wind_ratio"] - 1.0) < 1e-9
    assert hazards.climate_delta(_dates(2000, 2005), np.ones(len(_dates(2000, 2005))), np.ones(len(_dates(2000, 2005)))) is None


def test_river_stats_ratio_and_short_record():
    d = _dates(1990, 2020)
    rng = np.random.default_rng(1)
    q = 50 + rng.gamma(2, 20, len(d))
    st = hazards.river_stats(d, q)
    assert st and st["q20"] > st["q50"] > 0
    assert hazards.river_stats(_dates(2000, 2003), np.ones(len(_dates(2000, 2003)))) is None


def test_to_state():
    assert manual_entry.to_state("Texas", "US") == "TX"
    assert manual_entry.to_state("Punjab", "PK") in manual_entry.STATE_OPTIONS
    assert manual_entry.to_state("Bavaria", "DE") is None


def test_geocode_offline_and_short_query(monkeypatch):
    assert manual_entry.geocode("a")[1]
    monkeypatch.setattr(config, "OFFLINE", True)
    res, err = manual_entry.geocode("Lahore")
    assert res == [] and "Offline" in err


def test_geocode_parses_response(monkeypatch):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"results": [{"name": "Houston", "admin1": "Texas", "country": "United States", "country_code": "US", "latitude": 29.76, "longitude": -95.37}, {"name": "bad"}]}
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(manual_entry.requests, "get", lambda *a, **k: R())
    res, err = manual_entry.geocode("Houston")
    assert err is None and len(res) == 1 and res[0]["state"] == "TX"


def test_manual_rows_validate_through_ingest():
    from src import ingestion
    df = manual_entry.rows_to_dataframe([{"name": "A", "asset_class": "office", "replacement_value": 1e6, "state": "TX", "lat": 29.7, "lon": -95.3}])
    assert df.loc[0, "asset_id"] == "M-001"
    assert ingestion.ingest(df).n_valid == 1


def test_landslide_class_raster_maps_to_index(monkeypatch):
    calls = {"landslide_susceptibility": None, "pakistan_landslide": 4.0}
    monkeypatch.setattr(hazards, "local_raster", lambda name, lat, lon, nodata_default=None: calls.get(name))
    assert hazards.LANDSLIDE_CLASS_INDEX[4] == 70.0
    assert calls["pakistan_landslide"] == 4.0
