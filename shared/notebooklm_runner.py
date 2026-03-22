# shared/notebooklm_runner.py
"""NotebookLM media generation runner.

Uses the notebooklm CLI via subprocess.run() to create notebooks,
add newsletter HTML as a source, and generate media artifacts.

Per-issue notebook IDs are cached in topics/<slug>/media/YYYY-MM-DD-notebook-id.txt
so re-runs reuse the same notebook instead of creating duplicates.
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent

# Maps artifact_type → (generate subcommand, download subcommand, file extension)
_ARTIFACT_MAP: dict[str, tuple[str, str, str]] = {
    "infographic": ("infographic", "infographic", ".png"),
    "slides":      ("slide-deck",  "slide-deck",  ".pdf"),
    "podcast":     ("audio",       "audio",       ".mp3"),
    "video":       ("video",       "video",       ".mp4"),
}


def _nlm(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a notebooklm CLI command. Raises subprocess.CalledProcessError on non-zero exit."""
    cmd = ["notebooklm"] + list(args)
    logger.debug("nlm: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)


def _nlm_json(*args: str, timeout: int = 60) -> dict:
    """Run notebooklm CLI command and parse JSON output."""
    result = _nlm(*args, "--json", timeout=timeout)
    return json.loads(result.stdout)


def _get_or_create_notebook(slug: str, date: str) -> str:
    """Return notebook ID for this issue, creating it if it doesn't exist yet.

    On creation: adds the issue HTML (or .md) as a source and waits for processing.
    Caches the ID in topics/<slug>/media/YYYY-MM-DD-notebook-id.txt.
    """
    media_dir = REPO_ROOT / "topics" / slug / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    id_file = media_dir / f"{date}-notebook-id.txt"

    if id_file.exists():
        return id_file.read_text().strip()

    # Find source file: prefer dated HTML, fall back to markdown
    html_file = REPO_ROOT / "topics" / slug / "site" / f"{date}.html"
    md_file   = REPO_ROOT / "topics" / slug / f"{date}.md"
    source_file = html_file if html_file.exists() else md_file
    if not source_file.exists():
        raise FileNotFoundError(
            f"No content file found for {slug}/{date} "
            f"(checked {html_file} and {md_file})"
        )

    # Create notebook
    data = _nlm_json("create", "newsletters")
    notebook_id: str = data["notebook"]["id"]
    logger.info("Created notebook %s for %s/%s", notebook_id, slug, date)

    # Add source
    source_data = _nlm_json(
        "source", "add", str(source_file),
        "--notebook", notebook_id,
        timeout=30,
    )
    source_id: str = source_data["source_id"]
    logger.info("Added source %s, waiting for processing…", source_id)

    # Wait for source to be ready (up to 5 min)
    _nlm("source", "wait", source_id, "-n", notebook_id, "--timeout", "300", timeout=320)

    # Cache ID so subsequent calls reuse the notebook
    id_file.write_text(notebook_id)
    return notebook_id


def _start_artifact(notebook_id: str, artifact_type: str) -> str:
    """Kick off generation of an artifact. Returns task_id."""
    gen_sub, _, _ = _ARTIFACT_MAP[artifact_type]
    data = _nlm_json("generate", gen_sub, "--notebook", notebook_id, timeout=60)
    task_id: str = data["task_id"]
    logger.info("Started %s generation, task_id=%s", artifact_type, task_id)
    return task_id


def _wait_and_download(
    notebook_id: str,
    task_id: str,
    artifact_type: str,
    out_file: Path,
    wait_timeout: int = 900,
) -> None:
    """Wait for artifact completion then download it."""
    _, dl_sub, _ = _ARTIFACT_MAP[artifact_type]
    _nlm(
        "artifact", "wait", task_id, "-n", notebook_id,
        "--timeout", str(wait_timeout),
        timeout=wait_timeout + 30,
    )
    _nlm(
        "download", dl_sub, str(out_file),
        "-a", task_id, "-n", notebook_id,
        timeout=120,
    )
    if not out_file.exists():
        raise RuntimeError(f"Download reported success but file missing: {out_file}")
    logger.info("Downloaded %s → %s", artifact_type, out_file)


def generate_issue_media(slug: str, date: str) -> dict[str, str]:
    """Generate infographic and slides for a newsletter issue (synchronous, automatic).

    Creates (or reuses) a NotebookLM notebook, adds the issue HTML as a source,
    generates an infographic (PNG) and slide deck (PDF), downloads them to
    topics/<slug>/media/, and returns a dict of relative-to-REPO_ROOT paths.

    Podcast and video are NOT generated here — they are on-demand via the API.
    Non-fatal: any per-artifact failure is logged and skipped.

    Returns:
        e.g. {"infographic": "topics/claude-digest/media/2026-03-22-infographic.png",
               "slides": "topics/claude-digest/media/2026-03-22-slides.pdf"}
    """
    media_dir = REPO_ROOT / "topics" / slug / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}

    try:
        notebook_id = _get_or_create_notebook(slug, date)
    except Exception as exc:
        logger.warning("NotebookLM setup failed for %s/%s: %s", slug, date, exc)
        return {}

    for artifact_type in ("infographic", "slides"):
        _, _, ext = _ARTIFACT_MAP[artifact_type]
        out_file = media_dir / f"{date}-{artifact_type}{ext}"

        if out_file.exists():
            # Already generated — reuse
            results[artifact_type] = str(out_file.relative_to(REPO_ROOT))
            logger.info("Reusing existing %s for %s/%s", artifact_type, slug, date)
            continue

        try:
            task_id = _start_artifact(notebook_id, artifact_type)
            _wait_and_download(notebook_id, task_id, artifact_type, out_file)
            results[artifact_type] = str(out_file.relative_to(REPO_ROOT))
        except subprocess.CalledProcessError as exc:
            logger.warning(
                "Generation failed for %s %s/%s: %s",
                artifact_type, slug, date, exc.stderr[:300],
            )
        except Exception as exc:
            logger.warning("Unexpected error for %s %s/%s: %s", artifact_type, slug, date, exc)

    return results


def start_on_demand_artifact(slug: str, date: str, artifact_type: str) -> tuple[str, str]:
    """Start on-demand generation of podcast or video.

    Returns (notebook_id, task_id) immediately — caller is responsible for
    waiting and downloading (use wait_and_download_on_demand).

    Args:
        slug: Topic slug
        date: Issue date YYYY-MM-DD
        artifact_type: 'podcast' or 'video'

    Raises:
        ValueError: if artifact_type is not 'podcast' or 'video'
        FileNotFoundError: if no content file exists for this issue
    """
    if artifact_type not in ("podcast", "video"):
        raise ValueError(f"on-demand artifact_type must be 'podcast' or 'video', got {artifact_type!r}")

    media_dir = REPO_ROOT / "topics" / slug / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    notebook_id = _get_or_create_notebook(slug, date)
    task_id = _start_artifact(notebook_id, artifact_type)
    return notebook_id, task_id


def wait_and_download_on_demand(
    slug: str,
    date: str,
    artifact_type: str,
    notebook_id: str,
    task_id: str,
) -> str:
    """Wait for an on-demand artifact and download it.

    Blocks until complete (up to 20 min for podcast, 45 min for video).

    Returns:
        Relative path from REPO_ROOT to the downloaded file.
    """
    _, _, ext = _ARTIFACT_MAP[artifact_type]
    out_file = REPO_ROOT / "topics" / slug / "media" / f"{date}-{artifact_type}{ext}"
    wait_timeout = 1200 if artifact_type == "podcast" else 2700
    _wait_and_download(notebook_id, task_id, artifact_type, out_file, wait_timeout=wait_timeout)
    return str(out_file.relative_to(REPO_ROOT))
