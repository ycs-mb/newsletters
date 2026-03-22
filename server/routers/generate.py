# server/routers/generate.py
"""Generate router — on-demand NotebookLM media generation."""
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from server import jobs

router = APIRouter()


def _start(slug: str, date: str, artifact_type: str, background_tasks: BackgroundTasks) -> dict:
    from server.pipeline import submit_media_generation
    job_id = jobs.create()
    background_tasks.add_task(submit_media_generation, job_id, slug, date, artifact_type)
    return {"job_id": job_id, "slug": slug, "date": date, "type": artifact_type}


@router.post("/{slug}/{date}/podcast")
async def start_podcast(slug: str, date: str, background_tasks: BackgroundTasks) -> dict:
    return _start(slug, date, "podcast", background_tasks)


@router.post("/{slug}/{date}/video")
async def start_video(slug: str, date: str, background_tasks: BackgroundTasks) -> dict:
    return _start(slug, date, "video", background_tasks)


@router.post("/{slug}/{date}/infographic")
async def start_infographic(slug: str, date: str, background_tasks: BackgroundTasks) -> dict:
    return _start(slug, date, "infographic", background_tasks)
