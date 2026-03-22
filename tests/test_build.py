import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class BuildLayoutTest(unittest.TestCase):
    def test_normalized_layout_builds_expected_dist_outputs(self) -> None:
        builder = REPO_ROOT / "shared" / "build.py"
        self.assertTrue(builder.exists(), f"missing builder at {builder}")

        result = subprocess.run(
            [sys.executable, str(builder)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            self.fail(result.stderr or result.stdout or "build failed")

        expected_files = [
            REPO_ROOT / "shared" / "portal.css",
            REPO_ROOT / "shared" / "assets" / "style.css",
            REPO_ROOT / "shared" / "templates" / "nav.html",
            REPO_ROOT / "shared" / "templates" / "landing.html",
            REPO_ROOT / "topics" / "claude-digest" / "topic.md",
            REPO_ROOT / "topics" / "google-ai" / "topic.md",
            REPO_ROOT / "topics" / "us-iran-war" / "topic.md",
            REPO_ROOT / "shared" / "prompts" / "design-guide.md",
            REPO_ROOT / "shared" / "prompts" / "ops-guide.md",
            REPO_ROOT / "dist" / "index.html",
            REPO_ROOT / "dist" / "claude-digest" / "index.html",
            REPO_ROOT / "dist" / "google-ai" / "index.html",
            REPO_ROOT / "dist" / "us-iran-war" / "index.html",
            REPO_ROOT / "dist" / "style.css",
            REPO_ROOT / "dist" / "portal.css",
        ]

        missing = [str(path.relative_to(REPO_ROOT)) for path in expected_files if not path.exists()]
        self.assertEqual([], missing, f"missing expected files: {missing}")


if __name__ == "__main__":
    unittest.main()
