# server/routers/topics.py
"""Topic CRUD router — backed by shared.topic_registry (topics.json)."""
import re
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from server import jobs
from shared.topic_registry import (
    list_all, get as registry_get, save as registry_save,
    delete as registry_delete, get_status, is_ready,
)

router    = APIRouter()
REPO_ROOT = Path(__file__).parent.parent.parent


class TopicCreate(BaseModel):
    name:         str
    description:  str = ""
    focus_areas:  str = ""
    accent:       str = "terracotta"
    signal_label: str = "Signal"


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:40]


@router.get("")
async def list_topics() -> dict:
    config = list_all()
    topics = {}
    for slug, t in config.items():
        status = get_status(slug)
        topics[slug] = {
            "name":         t.get("name", slug),
            "description":  t.get("description", ""),
            "accent":       t.get("accent", "terracotta"),
            "signal_label": t.get("signal_label", "Signal"),
            "ready":        status["ready"],
            "has_topic_md": status["has_topic_md"],
        }
    return {"topics": topics, "count": len(config)}


@router.get("/{slug}")
async def get_topic(slug: str) -> dict:
    entry = registry_get(slug)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' not found")
    status = get_status(slug)
    return {"slug": slug, **entry, **status}


@router.post("")
async def create_topic(payload: TopicCreate, background_tasks: BackgroundTasks) -> dict:
    from server.pipeline import submit_topic_creation
    slug   = _slugify(payload.name)
    job_id = jobs.create()
    background_tasks.add_task(submit_topic_creation, job_id, slug, payload)
    return {"job_id": job_id, "slug": slug}


@router.delete("/{slug}")
async def delete_topic(slug: str) -> dict:
    removed = registry_delete(slug)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' not found")
    return {"deleted": slug}


@router.post("/{slug}/newsletter")
async def generate_newsletter(slug: str, background_tasks: BackgroundTasks) -> dict:
    """Request newsletter generation for a topic.

    Requires topic.md to exist — the app will NOT generate a newsletter
    for a topic that has no research prompt source.
    """
    entry = registry_get(slug)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' not found")
    if not is_ready(slug):
        raise HTTPException(
            status_code=409,
            detail=f"Topic '{slug}' is not ready: topics/{slug}/topic.md must exist",
        )
    from server.pipeline import submit_newsletter_generation
    job_id = jobs.create()
    background_tasks.add_task(submit_newsletter_generation, job_id, slug)
    return {"job_id": job_id, "slug": slug}
