# tests/test_topics_router.py
"""HTTP-level tests for /api/topics using FastAPI TestClient."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


class TopicsRouterTest(unittest.TestCase):
    """Test /api/topics endpoints with an isolated temp registry."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "topics").mkdir(parents=True)

        # Patch topic_registry to use temp directory
        from shared import topic_registry
        self._orig_root = topic_registry._REPO_ROOT
        self._orig_path = topic_registry._REGISTRY_PATH
        topic_registry._REPO_ROOT = self.root
        topic_registry._REGISTRY_PATH = self.root / "topics.json"

        # Also patch the router's REPO_ROOT so scaffold goes to temp dir
        from server.routers import topics as topics_router
        self._orig_router_root = topics_router.REPO_ROOT
        topics_router.REPO_ROOT = self.root

        from fastapi.testclient import TestClient
        from server.main import app
        self.client = TestClient(app, raise_server_exceptions=True)

    def tearDown(self):
        from shared import topic_registry
        topic_registry._REPO_ROOT = self._orig_root
        topic_registry._REGISTRY_PATH = self._orig_path

        from server.routers import topics as topics_router
        topics_router.REPO_ROOT = self._orig_router_root

        self.tmp.cleanup()

    # ── GET /api/topics ────────────────────────────────────────────────

    def test_list_empty(self):
        r = self.client.get("/api/topics")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["topics"], {})
        self.assertEqual(data["total_issues"], 0)

    def test_list_with_topics(self):
        from shared.topic_registry import save
        save("alpha", {"name": "Alpha"})
        r = self.client.get("/api/topics")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["count"], 1)
        self.assertIn("alpha", data["topics"])
        self.assertEqual(data["topics"]["alpha"]["name"], "Alpha")

    def test_list_includes_issue_count(self):
        from shared.topic_registry import save
        save("alpha", {"name": "Alpha"})
        topic_dir = self.root / "topics" / "alpha"
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "2026-01-01.md").write_text("# Issue 1")
        r = self.client.get("/api/topics")
        data = r.json()
        self.assertEqual(data["topics"]["alpha"]["issue_count"], 1)
        self.assertEqual(data["total_issues"], 1)

    # ── GET /api/topics/{slug} ─────────────────────────────────────────

    def test_get_existing(self):
        from shared.topic_registry import save
        save("beta", {"name": "Beta News"})
        r = self.client.get("/api/topics/beta")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["slug"], "beta")
        self.assertEqual(data["name"], "Beta News")

    def test_get_nonexistent(self):
        r = self.client.get("/api/topics/nope")
        self.assertEqual(r.status_code, 404)

    # ── POST /api/topics ───────────────────────────────────────────────

    def test_create_with_topic_md(self):
        payload = {
            "name": "Alpha News",
            "description": "Test topic",
            "accent": "sage",
            "signal_label": "Signal",
            "topic_md": "# Alpha\nThis is the topic.",
        }
        r = self.client.post("/api/topics", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["slug"], "alpha-news")
        self.assertTrue(data["ready"])
        self.assertTrue(data["topic_md_written"])
        # Verify topic.md is on disk
        self.assertTrue((self.root / "topics" / "alpha-news" / "topic.md").exists())

    def test_create_with_focus_areas_generates_topic_md(self):
        payload = {
            "name": "Quantum Computing",
            "description": "A newsletter on quantum breakthroughs.",
            "focus_areas": "- Superconducting qubits\n- IBM, Google, Microsoft\n- Post-quantum cryptography",
        }
        r = self.client.post("/api/topics", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ready"])
        self.assertTrue(data["topic_md_written"])
        content = (self.root / "topics" / "quantum-computing" / "topic.md").read_text()
        self.assertIn("Quantum Computing", content)
        self.assertIn("Superconducting qubits", content)

    def test_create_minimal_no_topic_md(self):
        payload = {"name": "Bare Topic"}
        r = self.client.post("/api/topics", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["slug"], "bare-topic")
        self.assertFalse(data["ready"])
        self.assertIn("message", data)

    def test_create_duplicate_slug(self):
        payload = {"name": "Alpha", "topic_md": "# content"}
        self.client.post("/api/topics", json=payload)
        r = self.client.post("/api/topics", json=payload)
        self.assertEqual(r.status_code, 409)

    def test_create_scaffolds_site_folder(self):
        payload = {"name": "New Brief", "topic_md": "# content"}
        self.client.post("/api/topics", json=payload)
        self.assertTrue((self.root / "topics" / "new-brief" / "site").exists())
        self.assertTrue((self.root / "topics" / "new-brief" / "media").exists())

    # ── PUT /api/topics/{slug}/topic-md ───────────────────────────────

    def test_update_topic_md(self):
        from shared.topic_registry import save
        save("alpha", {"name": "Alpha"})
        (self.root / "topics" / "alpha").mkdir(exist_ok=True)
        r = self.client.put("/api/topics/alpha/topic-md", json={"content": "# New content"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["topic_md_written"])
        self.assertEqual(
            (self.root / "topics" / "alpha" / "topic.md").read_text(), "# New content"
        )

    def test_update_topic_md_nonexistent_slug(self):
        r = self.client.put("/api/topics/ghost/topic-md", json={"content": "# x"})
        self.assertEqual(r.status_code, 404)

    # ── GET /api/topics/{slug}/topic-md ───────────────────────────────

    def test_get_topic_md(self):
        from shared.topic_registry import save
        save("alpha", {"name": "Alpha"})
        (self.root / "topics" / "alpha").mkdir(exist_ok=True)
        (self.root / "topics" / "alpha" / "topic.md").write_text("# Alpha topic")
        r = self.client.get("/api/topics/alpha/topic-md")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["content"], "# Alpha topic")

    def test_get_topic_md_missing_file(self):
        from shared.topic_registry import save
        save("alpha", {"name": "Alpha"})
        r = self.client.get("/api/topics/alpha/topic-md")
        self.assertEqual(r.status_code, 404)

    # ── DELETE /api/topics/{slug} ─────────────────────────────────────

    def test_delete_existing(self):
        from shared.topic_registry import save
        save("alpha", {"name": "Alpha"})
        r = self.client.delete("/api/topics/alpha")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["deleted"], "alpha")
        # Verify removed from registry
        r2 = self.client.get("/api/topics/alpha")
        self.assertEqual(r2.status_code, 404)

    def test_delete_nonexistent(self):
        r = self.client.delete("/api/topics/ghost")
        self.assertEqual(r.status_code, 404)

    # ── POST /api/topics/{slug}/newsletter ────────────────────────────

    def test_newsletter_requires_topic_md(self):
        from shared.topic_registry import save
        save("alpha", {"name": "Alpha"})
        r = self.client.post("/api/topics/alpha/newsletter")
        self.assertEqual(r.status_code, 409)
        self.assertIn("not ready", r.json()["detail"])

    def test_newsletter_dispatches_job_when_ready(self):
        from shared.topic_registry import save
        save("alpha", {"name": "Alpha"})
        (self.root / "topics" / "alpha").mkdir(exist_ok=True)
        (self.root / "topics" / "alpha" / "topic.md").write_text("# Alpha")

        # Patch the pipeline submit so we don't actually run Claude
        with patch("server.pipeline.submit_newsletter_generation"):
            r = self.client.post("/api/topics/alpha/newsletter")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("job_id", data)
        self.assertEqual(data["slug"], "alpha")

    def test_newsletter_nonexistent_slug(self):
        r = self.client.post("/api/topics/ghost/newsletter")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
