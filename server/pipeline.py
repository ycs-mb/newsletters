# server/pipeline.py
"""Background job orchestration.

All long-running operations (topic creation, newsletter generation) run in a
shared ThreadPoolExecutor.  Claude is invoked via subprocess.run().

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

if TYPE_CHECKING:
    from server.routers.topics import TopicCreate

REPO_ROOT = Path(__file__).parent.parent
_executor = ThreadPoolExecutor(max_workers=4)


def _update(job_id: str, step: str, status: JobStatus = JobStatus.running) -> None:
    jobs.update(job_id, step=step, status=status)


def _run_claude(task: str, max_turns: int = 10) -> None:
    """Invoke claude CLI via subprocess. Raises RuntimeError on non-zero exit."""
    result = subprocess.run(
        ["claude", "-p", task, "--dangerously-skip-permissions",
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

        _update(job_id, "Generating research prompt…")
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
        prompt_text = (topic_dir / "prompt.md").read_text()
        _run_claude(prompt_text, max_turns=25)

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
        _run_claude(prompt_path.read_text(), max_turns=25)

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


_TOPIC_MD_PROMPT = """\
Write a topic.md file for a newsletter automation system.
Output ONLY the file `topics/{slug}/topic.md` using the Write tool. Do not create any other files.

## Newsletter Details

Topic name: {name}
Description: {description}
Signal label: {signal_label}

## Focus Areas Provided by User

{focus_areas}

## Required topic.md Structure

The file must follow this EXACT structure (three sections, nothing else):

```
# {name} — Topic Brief

## Identity
- Role: newsletter curator covering [concise role description derived from the topic]
- Audience: [who reads this newsletter]
- Signal label: {signal_label} (1–5, where 5 = [describe what a 5 means for this topic])

## Sources

[Categorized, specific sources to monitor — real URLs where possible]
**Official / Primary:**
- ...

**GitHub / Open Source:**
- ...

**Community:**
- Subreddits, Discord servers, X/Twitter accounts, HN searches

**Research & Publications:**
- Journals, preprints, conference proceedings

## Sections

### Section 01: [Adapt title — official releases, core updates, or breaking news]
[Research instructions: what to search for, how many items, what to include per item]

### Section 02: [Highlights / Major Announcements]
[Research instructions. Highlight card categories: `voice` (people/opinion), `model` (tech/products), `company` (org news), `promo` (partnerships). Aim for 4–6 cards.]

### Section 03: GitHub Picks (past 7 days)
[Search terms, repo criteria, what to include per repo. Aim for 5–8 repos.]

### Section 04: Community & Research (past 24 hours)
[Which communities to check, what to surface, how to format entries]

### Section 05: Tip of the Day
[What kind of tip fits this topic. One actionable, non-obvious insight with an example if applicable.]
```

Use the focus areas above to fill in all the topic-specific content — real source URLs, adapted section titles, and precise research instructions. The file must be immediately usable as a newsletter research brief.
"""


def _topic_md_generation_job(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Generate topic.md for an already-registered topic via Claude CLI."""
    try:
        _update(job_id, "Generating topic.md via Claude…")
        prompt = _TOPIC_MD_PROMPT.format(
            slug=slug,
            name=payload.name,
            description=payload.description or payload.name,
            signal_label=payload.signal_label or "Signal",
            focus_areas=payload.focus_areas.strip() or "(none provided — use best judgement)",
        )
        _run_claude(prompt, max_turns=10)
        topic_md = REPO_ROOT / "topics" / slug / "topic.md"
        if not topic_md.exists():
            raise RuntimeError(f"Claude did not produce topics/{slug}/topic.md")
        jobs.update(job_id, step="Done ✓", status=JobStatus.done)
    except Exception as e:
        jobs.update(job_id, status=JobStatus.failed, error=str(e))


def submit_topic_md_generation(job_id: str, slug: str, payload: "TopicCreate") -> None:
    """Submit topic.md generation to the thread pool."""
    _executor.submit(_topic_md_generation_job, job_id, slug, payload)


def submit_newsletter_generation(job_id: str, slug: str) -> None:
    """Submit newsletter generation for an existing topic with topic.md."""
    _executor.submit(_newsletter_generation_job, job_id, slug)
