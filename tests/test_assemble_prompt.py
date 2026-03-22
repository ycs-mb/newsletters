# tests/test_assemble_prompt.py
import sys
import unittest
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.assemble_prompt import assemble


class AssemblePromptTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Create folder structure
        (self.root / "topics" / "test-slug").mkdir(parents=True)
        (self.root / "shared" / "prompts").mkdir(parents=True)
        (self.root / "topics" / "test-slug" / "topic.md").write_text("## Identity\nRole: test")
        (self.root / "shared" / "prompts" / "design-guide.md").write_text("## Design\nTemplate: {SLUG}")
        (self.root / "shared" / "prompts" / "ops-guide.md").write_text("## Ops\nSave to {SLUG}/YYYY-MM-DD.md")

    def tearDown(self):
        self.tmp.cleanup()

    def test_assemble_writes_prompt_md(self):
        result = assemble("test-slug", repo_root=self.root)
        out = self.root / "topics" / "test-slug" / "prompt.md"
        self.assertTrue(out.exists())
        self.assertEqual(result, out)

    def test_assemble_contains_all_three_layers(self):
        assemble("test-slug", repo_root=self.root)
        content = (self.root / "topics" / "test-slug" / "prompt.md").read_text()
        self.assertIn("Role: test", content)
        self.assertIn("## Design", content)
        self.assertIn("## Ops", content)

    def test_assemble_substitutes_slug(self):
        assemble("test-slug", repo_root=self.root)
        content = (self.root / "topics" / "test-slug" / "prompt.md").read_text()
        self.assertIn("test-slug", content)
        self.assertNotIn("{SLUG}", content)

    def test_assemble_raises_if_topic_md_missing(self):
        (self.root / "topics" / "test-slug" / "topic.md").unlink()
        with self.assertRaises(FileNotFoundError):
            assemble("test-slug", repo_root=self.root)

    def test_assemble_raises_if_design_guide_missing(self):
        (self.root / "shared" / "prompts" / "design-guide.md").unlink()
        with self.assertRaises(FileNotFoundError):
            assemble("test-slug", repo_root=self.root)

    def test_assemble_raises_if_ops_guide_missing(self):
        (self.root / "shared" / "prompts" / "ops-guide.md").unlink()
        with self.assertRaises(FileNotFoundError):
            assemble("test-slug", repo_root=self.root)


if __name__ == "__main__":
    unittest.main()
