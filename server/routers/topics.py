# server/routers/topics.py
import tomllib
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from server import jobs

router    = APIRouter()
REPO_ROOT = Path(__file__).parent.parent.parent


def _load_topics() -> dict:
    with open(REPO_ROOT / "topics.toml", "rb") as f:
        return tomllib.load(f)


class TopicCreate(BaseModel):
    name:         str
    description:  str = ""
    focus_areas:  str = ""
    accent:       str = "terracotta"
    signal_label: str = "Signal"


def _slugify(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:40]


@router.get("")
async def list_topics() -> dict:
    config = _load_topics()
    topics = {
        slug: {
            "name":         t.get("name", slug),
            "description":  t.get("description", ""),
            "accent":       t.get("accent", "terracotta"),
            "signal_label": t.get("signal_label", "Signal"),
        }
        for slug, t in config.items()
    }
    return {"topics": topics, "count": len(config)}


@router.post("")
async def create_topic(payload: TopicCreate, background_tasks: BackgroundTasks) -> dict:
    from server.pipeline import submit_topic_creation
    slug   = _slugify(payload.name)
    job_id = jobs.create()
    background_tasks.add_task(submit_topic_creation, job_id, slug, payload)
    return {"job_id": job_id, "slug": slug}
