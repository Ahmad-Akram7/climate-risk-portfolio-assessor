"""FastAPI backend with async (background) processing.  Run:  uvicorn api.main:app --port 8000"""
from __future__ import annotations

import threading
import uuid

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src import config, hazards
from src.orchestrator import run_assessment

app = FastAPI(title="Climate Risk Portfolio Assessor", version="1.0.0",
              description="Upload a portfolio CSV, get multi-hazard risk scores and a disclosure-style report.")
JOBS: dict[str, dict] = {}
_lock = threading.Lock()


def _run(job_id: str, data: bytes, scenario: str, use_llm: bool):
    def prog(stage, frac):
        with _lock:
            JOBS[job_id].update(stage=stage, progress=round(frac, 2))
    try:
        r = run_assessment(data, scenario, use_llm, progress=prog)
        with _lock:
            JOBS[job_id].update(status="done", progress=1.0, run_id=r["run_id"], out_dir=r["out_dir"],
                                summary=r["summary"], meta=r["meta"], qa=r["qa"], files=r["files"],
                                elapsed_s=r["elapsed_s"])
    except Exception as e:
        with _lock:
            JOBS[job_id].update(status="failed", error=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "layers": hazards.layer_status()}


@app.post("/api/v1/assess", status_code=202)
async def assess(bg: BackgroundTasks, file: UploadFile = File(...), scenario: str = Form("current"),
                 use_llm: bool = Form(True)):
    if scenario not in hazards.SCENARIOS:
        raise HTTPException(422, f"scenario must be one of {list(hazards.SCENARIOS)}")
    data = await file.read()
    if not data:
        raise HTTPException(422, "empty file")
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = dict(job_id=job_id, status="running", progress=0.0, stage="queued")
    bg.add_task(_run, job_id, data, scenario, use_llm)
    return {"job_id": job_id, "status_url": f"/api/v1/jobs/{job_id}"}


@app.get("/api/v1/jobs/{job_id}")
def job(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "unknown job")
    return j


@app.get("/api/v1/jobs/{job_id}/files/{name}")
def job_file(job_id: str, name: str):
    j = JOBS.get(job_id)
    if not j or j.get("status") != "done":
        raise HTTPException(404, "job not finished")
    allowed = set(j["files"].values())
    if name not in allowed:
        raise HTTPException(404, "no such file")
    return FileResponse(f"{j['out_dir']}/{name}")
