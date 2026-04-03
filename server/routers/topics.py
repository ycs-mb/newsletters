# server/routers/topics.py
"""Topic CRUD router — backed by shared.topic_registry (topics.json)."""
import json
import re
import shutil
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from server import jobs
from shared.topic_registry import (
    list_all, get as registry_get, save as registry_save,
    delete as registry_delete, get_status, is_ready, exists as registry_exists,
)

router    = APIRouter()
REPO_ROOT = Path(__file__).parent.parent.parent


class TopicCreate(BaseModel):
    name:         str
    description:  str = ""
    focus_areas:  str = ""
    accent:       str = "terracotta"
    signal_label: str = "Signal"
    topic_md:     str = ""  # optional: provide topic.md content directly


class TopicMdUpdate(BaseModel):
    content: str


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:40]


def _scaffold_topic(slug: str) -> Path:
    """Create topic folder structure. Returns the topic directory."""
    topic_dir = REPO_ROOT / "topics" / slug
    (topic_dir / "site").mkdir(parents=True, exist_ok=True)
    (topic_dir / "media").mkdir(exist_ok=True)
    # Copy shared template if available
    tmpl_src = REPO_ROOT / "shared" / "templates" / "topic-template.html"
    css_src  = REPO_ROOT / "shared" / "assets" / "style.css"
    if tmpl_src.exists():
        shutil.copy2(tmpl_src, topic_dir / "site" / "template.html")
    if css_src.exists():
        shutil.copy2(css_src, topic_dir / "site" / "style.css")
    return topic_dir


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
    """Create a new topic.

    1. Immediately registers in topics.json and scaffolds the folder.
    2. If topic_md content is provided, writes it to disk (topic is ready).
    3. If topic_md is empty and focus_areas is given, kicks off a background
       job to generate topic.md via Claude CLI (best-effort).
    4. Otherwise, topic is registered but not ready — user must provide topic.md.
    """
    slug = _slugify(payload.name)
    if registry_exists(slug):
        raise HTTPException(status_code=409, detail=f"Topic '{slug}' already exists")

    # Step 1: Register immediately
    registry_save(slug, {
        "name": payload.name,
        "description": payload.description,
        "accent": payload.accent,
        "signal_label": payload.signal_label,
    })

    # Step 2: Scaffold folder
    topic_dir = _scaffold_topic(slug)

    # Step 3: Handle topic.md
    result: dict = {"slug": slug, "registered": True}

    if payload.topic_md.strip():
        # User provided topic.md content directly
        (topic_dir / "topic.md").write_text(payload.topic_md)
        result["topic_md_written"] = True
        result["ready"] = True
    elif payload.focus_areas.strip():
        # Attempt background generation via Claude
        job_id = jobs.create()
        from server.pipeline import submit_topic_md_generation
        background_tasks.add_task(submit_topic_md_generation, job_id, slug, payload)
        result["job_id"] = job_id
        result["ready"] = False
    else:
        result["ready"] = False
        result["message"] = "Topic registered. Provide topic.md via PUT /api/topics/{slug}/topic-md to make it ready."

    return result


@router.put("/{slug}/topic-md")
async def update_topic_md(slug: str, body: TopicMdUpdate) -> dict:
    """Upload or replace topic.md content for an existing topic."""
    if not registry_exists(slug):
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' not found")
    topic_dir = REPO_ROOT / "topics" / slug
    topic_dir.mkdir(parents=True, exist_ok=True)
    (topic_dir / "topic.md").write_text(body.content)
    status = get_status(slug)
    return {"slug": slug, "topic_md_written": True, **status}


@router.get("/{slug}/topic-md")
async def get_topic_md(slug: str) -> dict:
    """Read the current topic.md content."""
    if not registry_exists(slug):
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' not found")
    topic_md_path = REPO_ROOT / "topics" / slug / "topic.md"
    if not topic_md_path.exists():
        raise HTTPException(status_code=404, detail=f"No topic.md for '{slug}'")
    return {"slug": slug, "content": topic_md_path.read_text()}


class TopicMdGenerateRequest(BaseModel):
    name:        str
    description: str = ""
    focus_areas: str = ""
    slug:        str = ""


@router.post("/generate-topic-md")
async def stream_generate_topic_md(payload: TopicMdGenerateRequest) -> StreamingResponse:
    """Stream topic.md generation token-by-token via SSE.

    Accepts topic metadata, streams OpenRouter tokens as SSE `data:` events,
    then writes the completed topic.md to disk and emits a final `data: [DONE]`
    event. The slug must belong to an already-registered topic.

    SSE event format:
        data: <token text>\\n\\n
        data: [DONE]\\n\\n         (on completion — topic.md written)
        data: [ERROR] <msg>\\n\\n  (on failure)
    """
    slug = payload.slug or _slugify(payload.name)

    from shared.topic_md_generation import _build_topic_md_prompt

    prompt = _build_topic_md_prompt(
        payload.name,
        payload.description,
        payload.focus_areas,
        slug,
    )

    def event_stream():
        from shared.openrouter_client import chat_completion_stream
        accumulated: list[str] = []
        try:
            for token in chat_completion_stream(prompt):
                accumulated.append(token)
                # Escape newlines so each SSE message stays on one data: line
                safe = token.replace("\n", "\\n")
                yield f"data: {safe}\n\n"
        except Exception as exc:
            yield f"data: [ERROR] {exc}\n\n"
            return

        # Write topic.md to disk
        topic_dir = REPO_ROOT / "topics" / slug
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "topic.md").write_text("".join(accumulated))

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
        },
    )


@router.delete("/{slug}")
async def delete_topic(slug: str) -> dict:
    removed = registry_delete(slug)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' not found")
    return {"deleted": slug}


@router.post("/{slug}/newsletter")
async def generate_newsletter(
    slug: str,
    background_tasks: BackgroundTasks,
    agent: str = "openrouter",
    model: str = "",
) -> dict:
    """Request newsletter generation for a topic.

    Requires topic.md to exist — the app will NOT generate a newsletter
    for a topic that has no research prompt source.

    Query params:
        agent: 'openrouter' (default) | 'claude' | 'gemini' | 'copilot' | 'opencode'
        model: OpenRouter model ID (only used when agent='openrouter').
               Defaults to OPENROUTER_MODEL_NEWSLETTER env var.
    """
    entry = registry_get(slug)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' not found")
    if not is_ready(slug):
        raise HTTPException(
            status_code=409,
            detail=f"Topic '{slug}' is not ready: topics/{slug}/topic.md must exist",
        )

    valid_agents = {"openrouter", "claude", "gemini", "copilot", "opencode"}
    if agent not in valid_agents:
        raise HTTPException(status_code=400, detail=f"Invalid agent '{agent}'. Valid: {sorted(valid_agents)}")

    from server.pipeline import submit_newsletter_generation
    job_id = jobs.create()
    background_tasks.add_task(submit_newsletter_generation, job_id, slug, agent, model or None)
    return {"job_id": job_id, "slug": slug, "agent": agent, "model": model or None}
