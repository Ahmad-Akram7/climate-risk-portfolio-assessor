import os
import time

os.environ["CRPA_OFFLINE"] = "1"

from fastapi.testclient import TestClient

from api.main import app

TEMPLATE = "data/templates/portfolio_upload_template.csv"


def test_api_flow():
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"
    with open(TEMPLATE, "rb") as f:
        r = c.post("/api/v1/assess", files={"file": ("p.csv", f, "text/csv")}, data={"use_llm": "false"})
    assert r.status_code == 202
    jid = r.json()["job_id"]
    for _ in range(50):
        j = c.get(f"/api/v1/jobs/{jid}").json()
        if j["status"] != "running":
            break
        time.sleep(0.1)
    assert j["status"] == "done" and j["summary"]["n_assets"] == 15
    assert c.get(f"/api/v1/jobs/{jid}/files/portfolio_risk_report.md").status_code == 200
    assert c.get(f"/api/v1/jobs/{jid}/files/../../etc/passwd").status_code in (404, 422)


def test_api_bad_scenario():
    c = TestClient(app)
    with open(TEMPLATE, "rb") as f:
        assert c.post("/api/v1/assess", files={"file": ("p.csv", f)}, data={"scenario": "nope"}).status_code == 422


def test_dashboard_runs():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(__import__("pathlib").Path(__file__).resolve().parent.parent / "app" / "dashboard.py"), default_timeout=60).run()
    assert not at.exception
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert any("Assets" == m.label for m in at.metric)


def _run_job(c, data=None):
    with open(TEMPLATE, "rb") as f:
        r = c.post("/api/v1/assess", files={"file": ("p.csv", data or f.read(), "text/csv")}, data={"use_llm": "false"})
    assert r.status_code == 202
    jid = r.json()["job_id"]
    for _ in range(100):
        j = c.get(f"/api/v1/jobs/{jid}").json()
        if j["status"] != "running":
            return jid, j
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_api_does_not_leak_server_paths_and_serves_assets():
    c = TestClient(app)
    jid, j = _run_job(c)
    assert j["status"] == "done" and "out_dir" not in j
    allr = c.get(f"/api/v1/jobs/{jid}/assets").json()
    assert allr["count"] == 15
    a = allr["assets"][0]
    assert {"risk_score", "severity_flood", "status_drought", "confidence_flood"} <= a.keys()
    assert a["severity_drought"] == "Not assessed" and a["risk_drought"] is None  # missing data stays missing
    sub = c.get(f"/api/v1/jobs/{jid}/assets", params={"hazard": "wind", "severity": "High"}).json()
    assert all(x["severity_wind"] == "High" for x in sub["assets"])
    assert c.get(f"/api/v1/jobs/{jid}/assets", params={"hazard": "nope"}).status_code == 422
    assert c.get(f"/api/v1/jobs/{jid}/assets", params={"severity": "Extreme"}).status_code == 422


def test_api_rejects_oversized_upload(monkeypatch):
    from src import config
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0.0001)
    c = TestClient(app)
    r = c.post("/api/v1/assess", files={"file": ("p.csv", b"x" * 500, "text/csv")})
    assert r.status_code == 413


def test_api_bad_csv_reports_validation_error_without_internals():
    c = TestClient(app)
    _, j = _run_job(c, b"a,b\n1,2\n")
    assert j["status"] == "failed" and "missing required columns" in j["error"] and "Traceback" not in j["error"]


def test_api_job_store_is_bounded(monkeypatch):
    from api import main
    from src import config
    monkeypatch.setattr(config, "MAX_JOBS", 2)
    with main._lock:
        main.JOBS.clear()
        for i in range(5):
            main.JOBS[f"j{i}"] = {"status": "done"}
        main._evict_finished()
    assert list(main.JOBS) == ["j3", "j4"]


def test_hazard_legend_endpoint():
    j = TestClient(app).get("/api/v1/hazards").json()
    assert {h["key"] for h in j["hazards"]} == {"flood", "wildfire", "heat", "wind", "landslide", "drought"}
    assert j["severity_levels"] == ["Low", "Medium", "High", "Critical"]


def test_dashboard_hazard_risk_tab_renders_legend_and_matrix():
    from streamlit.testing.v1 import AppTest
    path = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "app" / "dashboard.py")
    at = AppTest.from_file(path, default_timeout=90).run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "Hazard (colour)" in html and 'scope="row"' in html and "No data" in html
    assert len(at.tabs) == 6
