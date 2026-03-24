# tests/test_topic_registry.py
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared import topic_registry


class RegistryTest(unittest.TestCase):
    """Test topic_registry CRUD against a temp directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "topics" / "alpha").mkdir(parents=True)
        # Patch module-level paths
        self._orig_root = topic_registry._REPO_ROOT
        self._orig_path = topic_registry._REGISTRY_PATH
        topic_registry._REPO_ROOT = self.root
        topic_registry._REGISTRY_PATH = self.root / "topics.json"

    def tearDown(self):
        topic_registry._REPO_ROOT = self._orig_root
        topic_registry._REGISTRY_PATH = self._orig_path
        self.tmp.cleanup()

    def test_empty_registry(self):
        self.assertEqual(topic_registry.list_all(), {})
        self.assertIsNone(topic_registry.get("alpha"))
        self.assertFalse(topic_registry.exists("alpha"))

    def test_save_and_get(self):
        topic_registry.save("alpha", {"name": "Alpha News", "accent": "sage"})
        entry = topic_registry.get("alpha")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["name"], "Alpha News")
        self.assertEqual(entry["accent"], "sage")
        self.assertEqual(entry["folder"], "topics/alpha")

    def test_save_fills_defaults(self):
        topic_registry.save("alpha", {"name": "Alpha"})
        entry = topic_registry.get("alpha")
        self.assertEqual(entry["signal_label"], "Signal")
        self.assertEqual(entry["eyebrow"], "Daily Intelligence Brief")

    def test_delete_existing(self):
        topic_registry.save("alpha", {"name": "Alpha"})
        self.assertTrue(topic_registry.delete("alpha"))
        self.assertFalse(topic_registry.exists("alpha"))

    def test_delete_nonexistent(self):
        self.assertFalse(topic_registry.delete("nope"))

    def test_list_all(self):
        topic_registry.save("alpha", {"name": "Alpha"})
        topic_registry.save("beta", {"name": "Beta"})
        all_topics = topic_registry.list_all()
        self.assertEqual(set(all_topics.keys()), {"alpha", "beta"})

    def test_topic_md_exists(self):
        topic_registry.save("alpha", {"name": "Alpha"})
        self.assertFalse(topic_registry.topic_md_exists("alpha"))
        (self.root / "topics" / "alpha" / "topic.md").write_text("# Alpha")
        self.assertTrue(topic_registry.topic_md_exists("alpha"))

    def test_is_ready_requires_both(self):
        # Not registered
        self.assertFalse(topic_registry.is_ready("alpha"))
        # Registered but no topic.md
        topic_registry.save("alpha", {"name": "Alpha"})
        self.assertFalse(topic_registry.is_ready("alpha"))
        # Registered AND topic.md exists
        (self.root / "topics" / "alpha" / "topic.md").write_text("# Alpha")
        self.assertTrue(topic_registry.is_ready("alpha"))

    def test_get_status(self):
        (self.root / "topics" / "alpha" / "topic.md").write_text("# Alpha")
        topic_registry.save("alpha", {"name": "Alpha"})
        status = topic_registry.get_status("alpha")
        self.assertTrue(status["registered"])
        self.assertTrue(status["has_topic_md"])
        self.assertFalse(status["has_prompt_md"])
        self.assertTrue(status["ready"])

    def test_concurrent_saves(self):
        errors = []

        def do_save(i):
            try:
                topic_registry.save(f"topic-{i}", {"name": f"Topic {i}"})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_save, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual([], errors)
        self.assertEqual(len(topic_registry.list_all()), 20)

    def test_migrate_from_toml(self):
        toml_path = self.root / "topics.toml"
        toml_path.write_text(
            '[test-topic]\nname = "Test"\ndescription = "A test"\n'
            'accent = "gold"\nsignal_label = "Signal"\n'
            'folder = "topics/test-topic"\neyebrow = "Brief"\n'
        )
        # Remove existing JSON to trigger migration
        json_path = self.root / "topics.json"
        if json_path.exists():
            json_path.unlink()
        result = topic_registry.migrate_from_toml(toml_path)
        self.assertIn("test-topic", result)
        self.assertTrue(json_path.exists())

    def test_migrate_skips_if_json_exists(self):
        topic_registry.save("alpha", {"name": "Alpha"})
        toml_path = self.root / "topics.toml"
        toml_path.write_text('[beta]\nname = "Beta"\n')
        result = topic_registry.migrate_from_toml(toml_path)
        # Should return existing JSON (alpha), not TOML (beta)
        self.assertIn("alpha", result)
        self.assertNotIn("beta", result)

    def test_ensure_registry_exists(self):
        # Registry file doesn't exist yet
        self.assertFalse(topic_registry._REGISTRY_PATH.exists())
        topic_registry._ensure_registry_exists()
        # Should be created
        self.assertTrue(topic_registry._REGISTRY_PATH.exists())
        # Should be valid empty JSON
        self.assertEqual(topic_registry.list_all(), {})

    def test_ensure_registry_exists_idempotent(self):
        # Create it once
        topic_registry._ensure_registry_exists()
        self.assertTrue(topic_registry._REGISTRY_PATH.exists())
        # Save something
        topic_registry.save("alpha", {"name": "Alpha"})
        # Ensure again (should not overwrite)
        topic_registry._ensure_registry_exists()
        self.assertIn("alpha", topic_registry.list_all())


if __name__ == "__main__":
    unittest.main()
