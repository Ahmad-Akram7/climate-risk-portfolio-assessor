import pytest

from src import config


@pytest.fixture(autouse=True)
def _empty_hazard_dir(tmp_path_factory, monkeypatch):
    """Tests must not depend on rasters that happen to be in data/hazards."""
    monkeypatch.setattr(config, "HAZARD_DIR", tmp_path_factory.mktemp("hazards"))
