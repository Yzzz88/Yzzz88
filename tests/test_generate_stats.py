import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "generate_stats", Path(__file__).resolve().parents[1] / "scripts/generate_stats.py"
)
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        root_patch = patch.object(stats, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.data = {
            "updated_at": "2026-10-30T08:25:00+08:00",
            "repos": {"example/project": {"stars": 10, "url": "https://github.com/example/project"}},
            "pulls": [{
                "number": number, "title": f"Fix {number}",
                "html_url": f"https://github.com/example/project/pull/{number}",
                "repository_url": "https://api.github.com/repos/example/project",
                "state": "open", "pull_request": {"merged_at": None},
            } for number in (1, 2)],
        }
        stats.render(self.data)
        self.next = deepcopy(self.data)
        self.next["updated_at"] = "2026-10-30T09:25:00+08:00"

    def files(self):
        return {p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def refresh(self):
        with patch.object(stats, "collect", return_value=self.next):
            return stats.refresh()

    def test_unchanged_data_does_not_write_files(self):
        before = self.files()
        self.next["pulls"].reverse()
        self.next["pulls"][0]["updated_at"] = "ignored API metadata"
        self.assertFalse(self.refresh())
        self.assertEqual(before, self.files())

    def test_star_change_updates_snapshot_once(self):
        self.next["repos"]["example/project"]["stars"] += 1
        self.assertTrue(self.refresh())
        snapshot = json.loads((self.root / "data/stats.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["updated_at"], self.next["updated_at"])
        self.assertEqual(snapshot["repos"]["example/project"]["stars"], 11)
        before = self.files()
        self.assertFalse(self.refresh())
        self.assertEqual(before, self.files())

    def test_merge_updates_counts_and_links(self):
        pull = self.next["pulls"][0]
        pull["state"] = "closed"
        pull["pull_request"]["merged_at"] = "2026-10-30T01:00:00Z"
        self.assertTrue(self.refresh())
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        self.assertIn("已合并 1 个 PR · 待合并 1 个 PR", readme)
        self.assertIn(pull["html_url"], readme)

    def test_first_run_creates_snapshot(self):
        (self.root / "data/stats.json").unlink()
        self.assertTrue(self.refresh())
        self.assertTrue((self.root / "data/stats.json").exists())

    def test_api_failure_keeps_existing_files(self):
        before = self.files()
        with patch.object(stats, "collect", side_effect=RuntimeError("API failed")):
            with self.assertRaisesRegex(RuntimeError, "API failed"):
                stats.refresh()
        self.assertEqual(before, self.files())


if __name__ == "__main__":
    unittest.main()
