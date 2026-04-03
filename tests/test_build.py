import subprocess
import sys
import unittest
from pathlib import Path


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
            REPO_ROOT / "dist" / "style.css",
            REPO_ROOT / "dist" / "portal.css",
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


if __name__ == "__main__":
    unittest.main()
