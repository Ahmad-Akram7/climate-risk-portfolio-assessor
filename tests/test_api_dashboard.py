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
