# server/routers/jobs_router.py
from fastapi import APIRouter, HTTPException
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
