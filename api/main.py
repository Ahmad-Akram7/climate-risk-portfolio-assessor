"""FastAPI backend with async (background) processing.  Run:  uvicorn api.main:app --port 8000"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict

import pandas as pd
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse

from src import config, hazards
from src.hazard_registry import ALL_HAZARDS, HAZARDS, SEVERITY_LEVELS, STATUS_LABEL
from src.orchestrator import _json_safe, run_assessment
from src.readiness import readiness

app = FastAPI(title="Climate Risk Portfolio Assessor", version="1.1.0",
              description="Upload a portfolio CSV, get multi-hazard risk scores and a disclosure-style report.")
JOBS: dict[str, dict] = {}
_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)  # shortcut: per-process memory, resets on restart; use a shared store behind several workers
PUBLIC_HIDDEN = {"out_dir", "owner", "created"}  # server paths are not returned to clients
ASSET_FIELDS = ["asset_id", "name", "state", "asset_class", "lat", "lon", "replacement_value", "scenario",
                "assessment_basis", "risk_score", "risk_score_low", "risk_score_high", "risk_tier", "overall_status",
                "overall_confidence", "low_risk_verified", "dominant_hazard", "expected_loss_usd"] + [
    f"{k}_{h}" for h in ALL_HAZARDS for k in ("hazard_index", "risk", "severity", "status", "confidence")]


def _owner(x_api_key: str | None = Header(None)) -> str:
    """Caller identity. With CRPA_API_KEYS set (comma separated) every private route needs a valid X-API-Key.

    shortcut: shared static keys, no rotation or per-key limits; swap for real auth before a multi-tenant launch.
    """
    keys = [k.strip() for k in os.getenv("CRPA_API_KEYS", "").split(",") if k.strip()]
    if not keys:
        return "open"  # local development only
    if not x_api_key or not any(secrets.compare_digest(x_api_key, k) for k in keys):
        raise HTTPException(401, "missing or invalid X-API-Key")
    return hashlib.sha256(x_api_key.encode()).hexdigest()[:16]


def _ttl_s() -> float:
    return float(os.getenv("CRPA_JOB_TTL_HOURS", "24")) * 3600


def _drop(job_id: str) -> None:
    """Remove a job and its files. Caller holds _lock."""
    j = JOBS.pop(job_id, None)
    if j and j.get("out_dir"):
        shutil.rmtree(j["out_dir"], ignore_errors=True)


def _rate_limit(owner: str) -> None:
    limit, now = int(os.getenv("CRPA_RATE_LIMIT_PER_MIN", "30")), time.time()
    with _lock:
        q = _hits[owner]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, f"rate limit: at most {limit} assessments per minute")
        q.append(now)


def _evict_finished() -> None:
    """Keep memory bounded: drop the oldest finished jobs beyond MAX_JOBS. Caller holds _lock."""
    now = time.time()
    for k in [k for k, v in JOBS.items() if v.get("status") != "running" and now - v.get("created", now) > _ttl_s()]:
        _drop(k)
    finished = [k for k, v in JOBS.items() if v.get("status") != "running"]
    for k in finished[:max(0, len(finished) - config.MAX_JOBS)]:
        _drop(k)


def _run(job_id: str, data: bytes, scenario: str, use_llm: bool):
    def prog(stage, frac):
        with _lock:
            JOBS[job_id].update(stage=stage, progress=round(frac, 2))
    try:
        r = run_assessment(data, scenario, use_llm, progress=prog)
        with _lock:
            JOBS[job_id].update(status="done", progress=1.0, run_id=r["run_id"], out_dir=r["out_dir"],
                                summary=_json_safe(r["summary"]), meta=_json_safe(r["meta"]), qa=_json_safe(r["qa"]),
                                files=r["files"], elapsed_s=r["elapsed_s"])
            _evict_finished()
    except ValueError as e:  # validation problems are safe and useful to show
        with _lock:
            JOBS[job_id].update(status="failed", error=str(e)[:2000])
    except Exception:  # unexpected: do not leak internals to the client
        with _lock:
            JOBS[job_id].update(status="failed", error="Internal error while running the assessment. See server logs.")
        raise


@app.get("/health")
def health():
    return {"status": "ok", "auth_required": bool(os.getenv("CRPA_API_KEYS", "").strip()), "layers": hazards.layer_status()}


@app.get("/api/v1/readiness")
def data_readiness(owner: str = Depends(_owner)):
    """Which data files and keys are present, what is missing, and known defects."""
    return _json_safe(readiness())


@app.get("/api/v1/hazards")
def hazard_legend():
    """Hazard identity colours, units and the severity scale, for building legends in any client."""
    return {"hazards": [asdict(HAZARDS[h]) for h in ALL_HAZARDS], "severity_levels": SEVERITY_LEVELS,
            "status": STATUS_LABEL}


@app.post("/api/v1/assess", status_code=202)
async def assess(bg: BackgroundTasks, file: UploadFile = File(...), scenario: str = Form("current"),
                 use_llm: bool = Form(False), owner: str = Depends(_owner)):  # off by default: it sends a summary to a third party
    if scenario not in hazards.SCENARIOS:
        raise HTTPException(422, f"scenario must be one of {list(hazards.SCENARIOS)}")
    limit = int(config.MAX_UPLOAD_MB * 1024 * 1024)
    data = await file.read(limit + 1)
    if not data:
        raise HTTPException(422, "empty file")
    if len(data) > limit:
        raise HTTPException(413, f"file larger than {config.MAX_UPLOAD_MB:g} MB (set CRPA_MAX_UPLOAD_MB to change)")
    _rate_limit(owner)
    job_id = uuid.uuid4().hex  # 128 bits; the owner check is still what protects a job
    with _lock:
        JOBS[job_id] = dict(job_id=job_id, owner=owner, created=time.time(), status="running", progress=0.0, stage="queued")
    bg.add_task(_run, job_id, data, scenario, use_llm)
    return {"job_id": job_id, "status_url": f"/api/v1/jobs/{job_id}"}


def _get_job(job_id: str, owner: str) -> dict:
    with _lock:
        j = JOBS.get(job_id)
        if j and j.get("status") != "running" and time.time() - j.get("created", 0) > _ttl_s():
            _drop(job_id)
            j = None
        j = dict(j) if j else None
    if not j or j.get("owner") != owner:  # same answer for unknown and foreign jobs
        raise HTTPException(404, "unknown job")
    return j


@app.get("/api/v1/jobs/{job_id}")
def job(job_id: str, owner: str = Depends(_owner)):
    return {k: v for k, v in _get_job(job_id, owner).items() if k not in PUBLIC_HIDDEN}


@app.get("/api/v1/jobs/{job_id}/assets")
def job_assets(job_id: str, hazard: str | None = None, severity: str | None = None, owner: str = Depends(_owner)):
    """Per-asset results with hazard, severity, status and confidence. Optional filters: hazard, severity."""
    j = _get_job(job_id, owner)
    if j.get("status") != "done":
        raise HTTPException(404, "job not finished")
    if hazard is not None and hazard not in ALL_HAZARDS:
        raise HTTPException(422, f"hazard must be one of {ALL_HAZARDS}")
    if severity is not None and severity not in SEVERITY_LEVELS + ["Not assessed"]:
        raise HTTPException(422, f"severity must be one of {SEVERITY_LEVELS + ['Not assessed']}")
    df = pd.read_csv(f"{j['out_dir']}/{j['files']['csv']}")
    if hazard and severity:
        df = df[df[f"severity_{hazard}"] == severity]
    elif severity:
        df = df[df["risk_tier"] == severity]
    elif hazard:
        df = df[df[f"status_{hazard}"] != "not_assessed"]
    cols = [c for c in ASSET_FIELDS if c in df.columns]
    return {"count": len(df), "assets": json.loads(json.dumps(_json_safe(df[cols].to_dict("records")), allow_nan=False))}


@app.get("/api/v1/jobs/{job_id}/files/{name}")
def job_file(job_id: str, name: str, owner: str = Depends(_owner)):
    j = _get_job(job_id, owner)
    if j.get("status") != "done":
        raise HTTPException(404, "job not finished")
    allowed = set(j["files"].values())
    if name not in allowed:
        raise HTTPException(404, "no such file")
    return FileResponse(f"{j['out_dir']}/{name}")
