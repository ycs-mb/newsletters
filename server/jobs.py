# server/jobs.py
"""Thread-safe in-memory job store.

Jobs are lost on server restart — this is acceptable since daily runs happen
overnight and on-demand generation is a daytime activity with no overlap.
"""
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done    = "done"
    failed  = "failed"


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: JobStatus = JobStatus.pending
    step: str = ""           # Human-readable current step label
    artifact_url: str = ""   # Populated on done (relative URL to served file)
    error: str = ""          # Populated on failed


_store: dict[str, Job] = {}
_lock  = threading.Lock()


def create() -> str:
    """Create a new pending job. Returns the job ID."""
    job = Job()
    with _lock:
        _store[job.id] = job
    return job.id


def update(job_id: str, **kwargs) -> None:
    """Update job fields by keyword. Thread-safe."""
    with _lock:
        job = _store[job_id]
        for k, v in kwargs.items():
            setattr(job, k, v)


def get(job_id: str) -> Optional[Job]:
    """Return job or None if not found (server restarted, job expired)."""
    return _store.get(job_id)
