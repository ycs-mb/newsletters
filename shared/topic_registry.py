# shared/topic_registry.py
"""Centralized topic registry backed by a JSON file.

All topic metadata lives in topics.json at the repo root.  Every consumer
(build.py, server routers, run.sh helper) reads through this module so
there is a single source of truth.

Thread-safe: a threading.Lock protects writes for the FastAPI pipeline.
"""
import json
import threading
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).parent.parent
_REGISTRY_PATH = _REPO_ROOT / "topics.json"
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "description": "",
    "accent": "terracotta",
    "signal_label": "Signal",
    "eyebrow": "Daily Intelligence Brief",
}


def _topic_dir(slug: str) -> Path:
    return _REPO_ROOT / "topics" / slug


def _ensure_folder(slug: str) -> str:
    """Return the canonical folder value for a slug."""
    return f"topics/{slug}"


def _ensure_registry_exists() -> None:
    """Idempotent: ensure topics.json exists, creating it empty if needed."""
    if not _REGISTRY_PATH.exists():
        with _lock:
            # Double-check after acquiring lock
            if not _REGISTRY_PATH.exists():
                _REGISTRY_PATH.write_text("{}\n")

# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def _read_registry() -> dict:
    """Read registry from disk. Thread-safe via lock on writes."""
    if not _REGISTRY_PATH.exists():
        return {}
    return json.loads(_REGISTRY_PATH.read_text())


def list_all() -> dict:
    """Return the full registry: {slug: {name, description, ...}, ...}."""
    return _read_registry()


def get(slug: str) -> Optional[dict]:
    """Return topic metadata for *slug*, or None if not registered."""
    return _read_registry().get(slug)


def exists(slug: str) -> bool:
    """True if *slug* is registered."""
    return slug in _read_registry()


def topic_md_exists(slug: str) -> bool:
    """True if topics/<slug>/topic.md is present on disk."""
    return (_topic_dir(slug) / "topic.md").exists()


def is_ready(slug: str) -> bool:
    """A topic is ready for newsletter generation when it is registered
    AND its topic.md file exists on disk."""
    return exists(slug) and topic_md_exists(slug)


def count_issues(slug: str) -> int:
    """Return the number of dated YYYY-MM-DD.md files for a topic."""
    return len(list(_topic_dir(slug).glob("????-??-??.md")))


def get_status(slug: str) -> dict:
    """Return readiness details for a topic."""
    registered = exists(slug)
    has_topic_md = topic_md_exists(slug) if registered else False
    has_prompt_md = (_topic_dir(slug) / "prompt.md").exists() if registered else False
    has_site = (_topic_dir(slug) / "site" / "index.html").exists() if registered else False
    issue_count = count_issues(slug) if registered else 0
    return {
        "slug": slug,
        "registered": registered,
        "has_topic_md": has_topic_md,
        "has_prompt_md": has_prompt_md,
        "has_site": has_site,
        "ready": registered and has_topic_md,
        "issue_count": issue_count,
    }

# ---------------------------------------------------------------------------
# Write operations (lock-protected)
# ---------------------------------------------------------------------------

def save(slug: str, data: dict) -> dict:
    """Create or update a topic entry.  Returns the saved entry.

    *data* should include at least ``name``.  Missing optional fields are
    filled from ``_DEFAULTS``.  ``folder`` is always derived from the slug.

    Uses atomic writes (temp file + rename) to prevent corruption on crash.
    """
    entry = {**_DEFAULTS, **data, "folder": _ensure_folder(slug)}
    with _lock:
        registry = _read_registry()
        registry[slug] = entry
        # Atomic write: write to temp file, then rename
        tmp_path = _REGISTRY_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n")
        tmp_path.replace(_REGISTRY_PATH)
    return entry


def delete(slug: str) -> bool:
    """Remove a topic from the registry.  Returns True if it existed.

    Uses atomic writes (temp file + rename) to prevent corruption on crash.
    """
    with _lock:
        registry = _read_registry()
        if slug not in registry:
            return False
        del registry[slug]
        # Atomic write: write to temp file, then rename
        tmp_path = _REGISTRY_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n")
        tmp_path.replace(_REGISTRY_PATH)
    return True


# ---------------------------------------------------------------------------
# Migration helper
# ---------------------------------------------------------------------------

def migrate_from_toml(toml_path: Optional[Path] = None) -> dict:
    """One-time migration: read topics.toml and write topics.json.

    Returns the migrated registry dict.  Skips if topics.json already exists.
    Uses atomic writes to prevent corruption on crash.
    """
    if _REGISTRY_PATH.exists():
        return _read_registry()

    import tomllib
    toml_path = toml_path or (_REPO_ROOT / "topics.toml")
    if not toml_path.exists():
        return {}

    with open(toml_path, "rb") as f:
        toml_data = tomllib.load(f)

    registry: dict = {}
    for slug, entry in toml_data.items():
        registry[slug] = {**_DEFAULTS, **entry, "folder": _ensure_folder(slug)}

    # Atomic write: write to temp file, then rename
    tmp_path = _REGISTRY_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n")
    tmp_path.replace(_REGISTRY_PATH)
    return registry
