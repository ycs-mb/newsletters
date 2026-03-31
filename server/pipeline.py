# server/pipeline.py
"""Background job orchestration.

All long-running operations (topic creation, newsletter generation) run in a
shared ThreadPoolExecutor. OpenRouter API calls are made via shared modules.

Topic metadata is managed through shared.topic_registry (topics.json).
"""
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from server import jobs
from server.jobs import JobStatus
from shared.newsletter_generation import generate_newsletter_issue
from shared.topic_md_generation import generate_topic_md

if TYPE_CHECKING:
    from server.routers.topics import TopicCreate

REPO_ROOT = Path(__file__).parent.parent
_executor = ThreadPoolExecutor(max_workers=4)


def _update(job_id: str, step: str, status: JobStatus = JobStatus.running) -> None:
    jobs.update(job_id, step=step, status=status)




def _build_portal() -> None:
    """Run the static site builder."""
    subprocess.run(["uv", "run", "shared/build.py"], cwd=REPO_ROOT, check=True)


def _create_topic_job(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Full new-topic creation pipeline. Runs in thread pool."""
    from shared.topic_registry import save as registry_save

    try:
        _update(job_id, "Scaffolding topic folder…")
        topic_dir = REPO_ROOT / "topics" / slug
        (topic_dir / "site").mkdir(parents=True, exist_ok=True)
        (topic_dir / "media").mkdir(exist_ok=True)

        # Copy shared template
        tmpl_src = REPO_ROOT / "shared" / "templates" / "topic-template.html"
        css_src  = REPO_ROOT / "shared" / "assets" / "style.css"
        if tmpl_src.exists():
            shutil.copy2(tmpl_src, topic_dir / "site" / "template.html")
        if css_src.exists():
            shutil.copy2(css_src, topic_dir / "site" / "style.css")

        _update(job_id, "Generating topic.md…")
        topic_md_content = generate_topic_md(
            payload.name,
            payload.description,
            payload.focus_areas,
            slug
        )
        topic_md = topic_dir / "topic.md"
        topic_md.write_text(topic_md_content)

        # Register in topics.json (replaces _append_topic_toml)
        registry_save(slug, {
            "name": payload.name,
            "description": payload.description,
            "accent": payload.accent,
            "signal_label": payload.signal_label,
        })

        _update(job_id, "Assembling prompt…")
        from shared.assemble_prompt import assemble
        assemble(slug)

        _update(job_id, "Running first newsletter issue…")
        generate_newsletter_issue(slug)

        _update(job_id, "Generating NotebookLM media…")
        try:
            from shared.notebooklm_runner import generate_issue_media
            today = datetime.now().strftime("%Y-%m-%d")
            generate_issue_media(slug, today)
        except Exception as nlm_err:
            import logging
            logging.getLogger(__name__).warning("NotebookLM skipped: %s", nlm_err)

        _update(job_id, "Building portal…")
        _build_portal()

        jobs.update(job_id, step="Done ✓", status=JobStatus.done)

    except Exception as e:
        jobs.update(job_id, status=JobStatus.failed, error=str(e))


def _newsletter_generation_job(job_id: str, slug: str) -> None:
    """Generate a newsletter for an existing topic that has topic.md.

    This is the decoupled generation path: the topic must already be
    registered and have topic.md on disk.
    """
    try:
        topic_dir = REPO_ROOT / "topics" / slug

        _update(job_id, "Assembling prompt…")
        from shared.assemble_prompt import assemble
        assemble(slug)

        prompt_path = topic_dir / "prompt.md"
        if not prompt_path.exists():
            raise RuntimeError(f"Prompt assembly failed — no topics/{slug}/prompt.md")

        _update(job_id, "Running newsletter generation…")
        generate_newsletter_issue(slug)

        _update(job_id, "Generating NotebookLM media…")
        try:
            from shared.notebooklm_runner import generate_issue_media
            today = datetime.now().strftime("%Y-%m-%d")
            generate_issue_media(slug, today)
        except Exception as nlm_err:
            import logging
            logging.getLogger(__name__).warning("NotebookLM skipped: %s", nlm_err)

        _update(job_id, "Building portal…")
        _build_portal()

        jobs.update(job_id, step="Done ✓", status=JobStatus.done)

    except Exception as e:
        jobs.update(job_id, status=JobStatus.failed, error=str(e))


def _media_generation_job(job_id: str, slug: str, date: str, artifact_type: str) -> None:
    """Generate one on-demand media artifact (podcast or video). Runs in thread pool."""
    try:
        jobs.update(job_id, step=f"Setting up NotebookLM notebook…", status=JobStatus.running)
        from shared.notebooklm_runner import start_on_demand_artifact, wait_and_download_on_demand
        notebook_id, task_id = start_on_demand_artifact(slug, date, artifact_type)

        label = "podcast" if artifact_type == "podcast" else "video"
        jobs.update(job_id, step=f"Generating {label} (this takes 10–45 min)…")
        rel_path = wait_and_download_on_demand(slug, date, artifact_type, notebook_id, task_id)

        jobs.update(job_id, step="Building portal…")
        subprocess.run(["uv", "run", "shared/build.py"], cwd=REPO_ROOT, check=True)

        artifact_url = f"/{slug}/media/{Path(rel_path).name}"
        jobs.update(job_id, step="Done ✓", status=JobStatus.done, artifact_url=artifact_url)

    except Exception as e:
        jobs.update(job_id, status=JobStatus.failed, error=str(e))


def submit_media_generation(job_id: str, slug: str, date: str, artifact_type: str) -> None:
    """Submit on-demand media generation to the thread pool."""
    _executor.submit(_media_generation_job, job_id, slug, date, artifact_type)


def submit_topic_creation(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Submit topic creation to the thread pool. Called by FastAPI background task."""
    _executor.submit(_create_topic_job, job_id, slug, payload)


def _topic_md_generation_job(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Generate topic.md for an already-registered topic. Best-effort."""
    try:
        _update(job_id, "Generating topic.md…")
        topic_md_content = generate_topic_md(
            payload.name,
            payload.description,
            payload.focus_areas,
            slug
        )
        topic_md = REPO_ROOT / "topics" / slug / "topic.md"
        topic_md.write_text(topic_md_content)
        jobs.update(job_id, step="Done ✓", status=JobStatus.done)
    except Exception as e:
        jobs.update(job_id, status=JobStatus.failed, error=str(e))


def submit_topic_md_generation(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Submit topic.md generation to the thread pool."""
    _executor.submit(_topic_md_generation_job, job_id, slug, payload)


def submit_newsletter_generation(job_id: str, slug: str) -> None:
    """Submit newsletter generation for an existing topic with topic.md."""
    _executor.submit(_newsletter_generation_job, job_id, slug)
