import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parent.parent


class BuildLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        builder = REPO_ROOT / "shared" / "build.py"
        if not builder.exists():
            raise FileNotFoundError(f"missing builder at {builder}")

        result = subprocess.run(
            [sys.executable, str(builder)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "build failed")

    def test_normalized_layout_builds_expected_dist_outputs(self) -> None:
        expected_files = [
            REPO_ROOT / "shared" / "portal.css",
            REPO_ROOT / "shared" / "assets" / "style.css",
            REPO_ROOT / "shared" / "templates" / "archive.html",
            REPO_ROOT / "shared" / "templates" / "nav.html",
            REPO_ROOT / "shared" / "templates" / "landing.html",
            REPO_ROOT / "topics" / "claude-digest" / "topic.md",
            REPO_ROOT / "topics" / "google-ai" / "topic.md",
            REPO_ROOT / "topics" / "us-iran-war" / "topic.md",
            REPO_ROOT / "shared" / "prompts" / "design-guide.md",
            REPO_ROOT / "shared" / "prompts" / "ops-guide.md",
            REPO_ROOT / "dist" / "index.html",
            REPO_ROOT / "dist" / "archives" / "index.html",
            REPO_ROOT / "dist" / "claude-digest" / "index.html",
            REPO_ROOT / "dist" / "google-ai" / "index.html",
            REPO_ROOT / "dist" / "us-iran-war" / "index.html",
            REPO_ROOT / "dist" / "manage.html",
            REPO_ROOT / "dist" / "style.css",
            REPO_ROOT / "dist" / "portal.css",
            REPO_ROOT / "dist" / ".nojekyll",
        ]

        missing = [str(path.relative_to(REPO_ROOT)) for path in expected_files if not path.exists()]
        self.assertEqual([], missing, f"missing expected files: {missing}")

    def test_archive_page_content(self) -> None:
        """Verify the archive page lists all topics with dates and links."""
        archive_path = REPO_ROOT / "dist" / "archives" / "index.html"
        self.assertTrue(archive_path.exists(), "archive page not found in dist/archives/index.html")

        html = archive_path.read_text()

        # Should contain links to dated topic pages
        self.assertIn("claude-digest/", html, "archive missing claude-digest links")
        self.assertIn("google-ai/", html, "archive missing google-ai links")
        self.assertIn("us-iran-war/", html, "archive missing us-iran-war links")

        # Should contain year in date display
        self.assertRegex(html, r"\b20\d{2}\b", "archive dates should include year")

    def test_landing_page_archive_link(self) -> None:
        """Verify landing page links to the archive."""
        landing_path = REPO_ROOT / "dist" / "index.html"
        self.assertTrue(landing_path.exists(), "landing page not found in dist/index.html")

        html = landing_path.read_text()
        self.assertIn('href="archives/index.html"', html, "landing page should link to archive")

    def test_landing_page_only_lists_built_topics(self) -> None:
        """Verify the landing page does not link to topics skipped during build."""
        landing_path = REPO_ROOT / "dist" / "index.html"
        html = landing_path.read_text()

        self.assertNotIn(
            'href="indian-parliament-session/index.html"',
            html,
            "landing page should not link to a topic without built HTML",
        )
        self.assertIn("5 Active Briefings", html)

    def test_manage_page_resolves_portal_placeholders(self) -> None:
        """Verify the built manage page receives concrete portal config values."""
        manage_path = REPO_ROOT / "dist" / "manage.html"
        self.assertTrue(manage_path.exists(), "manage page not found in dist/manage.html")

        html = manage_path.read_text()
        self.assertNotIn("{{PORTAL_API_BASE_URL}}", html)
        self.assertNotIn("{{PORTAL_MANAGEMENT_MODE}}", html)
        self.assertIn("const PORTAL_API_BASE_URL = '';", html)
        self.assertIn("const PORTAL_MANAGEMENT_MODE = 'server';", html)

    def test_portal_config_switches_to_external_mode_when_api_base_is_set(self) -> None:
        from shared.build import get_portal_config

        with patch.dict(os.environ, {"PORTAL_API_BASE_URL": "https://api.example.com/api"}, clear=False):
            config = get_portal_config()

        self.assertEqual(config["api_base_url"], "https://api.example.com/api")
        self.assertEqual(config["management_mode"], "external")

    def test_portal_config_accepts_static_mode_override(self) -> None:
        from shared.build import get_portal_config

        with patch.dict(
            os.environ,
            {
                "PORTAL_API_BASE_URL": "",
                "PORTAL_MANAGEMENT_MODE": "static",
            },
            clear=False,
        ):
            config = get_portal_config()

        self.assertEqual(config["api_base_url"], "")
        self.assertEqual(config["management_mode"], "static")

    def test_portal_config_rejects_invalid_api_base_url(self) -> None:
        from shared.build import get_portal_config

        with patch.dict(os.environ, {"PORTAL_API_BASE_URL": "javascript:alert(1)"}, clear=False):
            with self.assertRaises(ValueError):
                get_portal_config()


if __name__ == "__main__":
    unittest.main()
