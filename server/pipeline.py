# server/pipeline.py
"""Background job orchestration.

All long-running operations (topic creation) run in a shared ThreadPoolExecutor.
Claude is invoked via subprocess.run() — no Python SDK needed.
topics.toml writes are protected by a threading.Lock().
"""
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from server import jobs
from server.jobs import JobStatus

if TYPE_CHECKING:
    from server.routers.topics import TopicCreate

REPO_ROOT  = Path(__file__).parent.parent
_executor  = ThreadPoolExecutor(max_workers=4)
_toml_lock = threading.Lock()


def _update(job_id: str, step: str, status: JobStatus = JobStatus.running) -> None:
    jobs.update(job_id, step=step, status=status)


def _run_claude(task: str, max_turns: int = 10) -> None:
    """Invoke claude CLI via subprocess. Raises RuntimeError on non-zero exit."""
    result = subprocess.run(
        ["claude", "--task", task, "--dangerously-skip-permissions",
         "--max-turns", str(max_turns)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude exited {result.returncode}: {(result.stderr or result.stdout)[:500]}"
        )


def _append_topic_toml(slug: str, name: str, description: str,
                        accent: str, signal_label: str) -> None:
    """Append a new topic entry to topics.toml. Thread-safe via _toml_lock."""
    entry = (
        f'\n[{slug}]\n'
        f'name = "{name}"\n'
        f'description = "{description}"\n'
        f'accent = "{accent}"\n'
        f'signal_label = "{signal_label}"\n'
        f'folder = "topics/{slug}"\n'
        f'eyebrow = "Daily Intelligence Brief"\n'
    )
    with _toml_lock:
        with open(REPO_ROOT / "topics.toml", "a") as f:
            f.write(entry)


def _create_topic_job(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Full new-topic creation pipeline. Runs in thread pool."""
    try:
        _update(job_id, "Scaffolding topic folder\u2026")
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

        _update(job_id, "Generating research prompt\u2026")
        _run_claude(
            f"Use the newsletter-create skill to generate a topic.md file for a new newsletter.\n"
            f"Topic name: {payload.name}\n"
            f"Description: {payload.description}\n"
            f"Focus areas: {payload.focus_areas}\n"
            f"Output path: topics/{slug}/topic.md\n"
            f"Format: Identity section (role, audience, signal label) + Sources + Sections only.\n"
            f"Do NOT include HTML output instructions, build steps, or Telegram delivery steps.\n"
            f"Do NOT generate prompt.md. Write topic.md only.",
            max_turns=10,
        )
        topic_md = topic_dir / "topic.md"
        if not topic_md.exists():
            raise RuntimeError(
                f"newsletter-create did not produce topics/{slug}/topic.md"
            )

        _append_topic_toml(
            slug, payload.name, payload.description,
            payload.accent, payload.signal_label,
        )

        _update(job_id, "Assembling prompt\u2026")
        from shared.assemble_prompt import assemble
        assemble(slug)

        _update(job_id, "Running first newsletter issue\u2026")
        prompt_text = (topic_dir / "prompt.md").read_text()
        _run_claude(prompt_text, max_turns=25)

        _update(job_id, "Generating NotebookLM media\u2026")
        try:
            from shared.notebooklm_runner import generate_issue_media
            today = datetime.now().strftime("%Y-%m-%d")
            generate_issue_media(slug, today)
        except Exception as nlm_err:
            # Non-fatal: media generation failure does not abort topic creation
            import logging
            logging.getLogger(__name__).warning("NotebookLM skipped: %s", nlm_err)

        _update(job_id, "Building portal\u2026")
        subprocess.run(
            ["uv", "run", "shared/build.py"],
            cwd=REPO_ROOT,
            check=True,
        )

        jobs.update(job_id, step="Done \u2713", status=JobStatus.done)

    except Exception as e:
        jobs.update(job_id, status=JobStatus.failed, error=str(e))


def submit_topic_creation(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Submit topic creation to the thread pool. Called by FastAPI background task."""
    _executor.submit(_create_topic_job, job_id, slug, payload)
