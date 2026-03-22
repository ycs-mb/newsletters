# tests/test_jobs.py
import sys
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from server.jobs import create, update, get, JobStatus


class JobStoreTest(unittest.TestCase):

    def test_create_returns_string_id(self):
        job_id = create()
        self.assertIsInstance(job_id, str)
        self.assertGreater(len(job_id), 0)

    def test_new_job_is_pending(self):
        job_id = create()
        job = get(job_id)
        self.assertEqual(job.status, JobStatus.pending)
        self.assertEqual(job.step, "")
        self.assertEqual(job.artifact_url, "")
        self.assertEqual(job.error, "")

    def test_get_returns_none_for_unknown_id(self):
        self.assertIsNone(get("does-not-exist"))

    def test_update_status(self):
        job_id = create()
        update(job_id, status=JobStatus.running, step="Doing something...")
        job = get(job_id)
        self.assertEqual(job.status, JobStatus.running)
        self.assertEqual(job.step, "Doing something...")

    def test_update_done_with_artifact_url(self):
        job_id = create()
        update(job_id, status=JobStatus.done, artifact_url="/dist/media/test.mp3")
        job = get(job_id)
        self.assertEqual(job.status, JobStatus.done)
        self.assertEqual(job.artifact_url, "/dist/media/test.mp3")

    def test_update_failed_with_error(self):
        job_id = create()
        update(job_id, status=JobStatus.failed, error="Timeout after 600s")
        job = get(job_id)
        self.assertEqual(job.status, JobStatus.failed)
        self.assertEqual(job.error, "Timeout after 600s")

    def test_concurrent_creates_are_unique(self):
        ids = []
        lock = threading.Lock()

        def make():
            jid = create()
            with lock:
                ids.append(jid)

        threads = [threading.Thread(target=make) for _ in range(50)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(len(ids), len(set(ids)), "Duplicate job IDs created concurrently")

    def test_concurrent_updates_are_safe(self):
        job_id = create()
        errors = []

        def do_update(i):
            try:
                update(job_id, step=f"step-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_update, args=(i,)) for i in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
