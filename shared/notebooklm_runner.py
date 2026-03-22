# shared/notebooklm_runner.py
"""NotebookLM media generation runner.

This is a Plan A STUB. Full implementation in Plan B.
Interface is defined here so pipeline.py can import it without error.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent


def generate_issue_media(slug: str, date: str) -> dict[str, str]:
    """Generate infographic and slides for a newsletter issue.

    Plan A: logs a skip message and returns empty dict.
    Plan B: invokes notebooklm CLI to generate artifacts.

    Args:
        slug: Topic slug (e.g. 'claude-digest')
        date: Issue date in YYYY-MM-DD format

    Returns:
        dict with keys 'infographic', 'slides', 'podcast', 'video'
        (empty in Plan A stub; populated with relative URLs in Plan B)
    """
    logger.info("NotebookLM media generation: Plan A stub — skipping for %s/%s", slug, date)
    return {}
