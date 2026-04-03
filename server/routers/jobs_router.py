# server/routers/jobs_router.py
from fastapi import APIRouter, HTTPException, Query
from server.jobs import get, Job

router = APIRouter()


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    job = get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found — session may have expired")
    return {
        "id":           job.id,
        "status":       job.status.value,
        "step":         job.step,
        "artifact_url": job.artifact_url,
        "error":        job.error,
    }


@router.get("/{job_id}/log")
async def get_job_log(job_id: str, from_: int = Query(0, alias="from")) -> dict:
    """Return log lines starting at offset `from`. Supports incremental polling."""
    job = get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found — session may have expired")
    lines = job.log_lines[from_:]
    return {
        "lines": lines,
        "total": len(job.log_lines),
        "status": job.status.value,
    }
