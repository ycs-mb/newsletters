# server/routers/generate.py
"""Generate router — on-demand NotebookLM media generation.

Endpoints return 501 Not Implemented in Plan A.
Full implementation in Plan B (notebooklm_runner.py).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/{slug}/{date}/podcast")
async def start_podcast(slug: str, date: str):
    return JSONResponse({"error": "NotebookLM integration not yet available"}, status_code=501)


@router.post("/{slug}/{date}/video")
async def start_video(slug: str, date: str):
    return JSONResponse({"error": "NotebookLM integration not yet available"}, status_code=501)


@router.post("/{slug}/{date}/infographic")
async def start_infographic(slug: str, date: str):
    return JSONResponse({"error": "NotebookLM integration not yet available"}, status_code=501)
