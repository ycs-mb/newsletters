# tests/test_jobs_router.py
"""HTTP-level tests for /api/jobs endpoints."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient
from server.main import app
from server import jobs


class JobsRouterTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=True)

    # ── GET /api/jobs/{id} ─────────────────────────────────────────────

    def test_get_unknown_job_returns_404(self):
        res = self.client.get("/api/jobs/no-such-id")
        self.assertEqual(res.status_code, 404)

    def test_get_existing_job_returns_fields(self):
        jid = jobs.create()
        res = self.client.get(f"/api/jobs/{jid}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], jid)
        self.assertIn("status", data)
        self.assertIn("step", data)
        self.assertIn("artifact_url", data)
        self.assertIn("error", data)

    # ── GET /api/jobs/{id}/log ─────────────────────────────────────────

    def test_log_unknown_job_returns_404(self):
        res = self.client.get("/api/jobs/no-such-id/log")
        self.assertEqual(res.status_code, 404)

    def test_log_empty_for_new_job(self):
        jid = jobs.create()
        res = self.client.get(f"/api/jobs/{jid}/log")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["lines"], [])
        self.assertEqual(data["total"], 0)
        self.assertIn("status", data)

    def test_log_returns_all_lines(self):
        jid = jobs.create()
        jobs.append_log(jid, "🔍 Searching: quantum")
        jobs.append_log(jid, "✍ Writing: topic.md")
        res = self.client.get(f"/api/jobs/{jid}/log")
        data = res.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["lines"], ["🔍 Searching: quantum", "✍ Writing: topic.md"])

    def test_log_from_offset_returns_tail(self):
        jid = jobs.create()
        jobs.append_log(jid, "line-0")
        jobs.append_log(jid, "line-1")
        jobs.append_log(jid, "line-2")
        res = self.client.get(f"/api/jobs/{jid}/log?from=1")
        data = res.json()
        self.assertEqual(data["lines"], ["line-1", "line-2"])
        self.assertEqual(data["total"], 3)

    def test_log_from_beyond_end_returns_empty(self):
        jid = jobs.create()
        jobs.append_log(jid, "only-line")
        res = self.client.get(f"/api/jobs/{jid}/log?from=5")
        data = res.json()
        self.assertEqual(data["lines"], [])
        self.assertEqual(data["total"], 1)

    def test_log_reflects_job_status(self):
        jid = jobs.create()
        jobs.update(jid, status=jobs.JobStatus.done, step="Done ✓")
        res = self.client.get(f"/api/jobs/{jid}/log")
        data = res.json()
        self.assertEqual(data["status"], "done")


if __name__ == "__main__":
    unittest.main()
