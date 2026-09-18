"""Tests for src/utils/copy_raw_data_markdown.py."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "utils"))

from copy_raw_data_markdown import copy_markdown_files


class TestCopyMarkdownFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "raw_data"
        self.dest = Path(self.tmp.name) / "raw_data_skills"
        repo = self.src / "Python" / "acme__demo" / "skills" / "foo"
        repo.mkdir(parents=True)
        (repo / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        (repo / "notes.md").write_text("notes\n", encoding="utf-8")
        (repo / "run.py").write_text("print(1)\n", encoding="utf-8")
        (repo / "metadata.json").write_text("{}", encoding="utf-8")
        (self.src / "Python" / "acme__demo" / "metadata.json").write_text(
            '{"skill_count": 1}\n', encoding="utf-8"
        )
        refs = repo / "references"
        refs.mkdir()
        (refs / "guide.md").write_text("guide\n", encoding="utf-8")
        (refs / "schema.json").write_text("{}\n", encoding="utf-8")
        (refs / "skill.md").write_text("wrong case\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_copies_only_skill_md_and_keeps_layout(self) -> None:
        copied = copy_markdown_files(self.src, self.dest)
        self.assertEqual(copied, 1)

        kept = sorted(p.relative_to(self.dest).as_posix() for p in self.dest.rglob("*") if p.is_file())
        self.assertEqual(kept, ["Python/acme__demo/skills/foo/SKILL.md"])
        self.assertFalse((self.dest / "Python" / "acme__demo" / "skills" / "foo" / "notes.md").exists())
        self.assertFalse((self.dest / "Python" / "acme__demo" / "skills" / "foo" / "references" / "guide.md").exists())
        self.assertEqual(
            (self.dest / "Python" / "acme__demo" / "skills" / "foo" / "SKILL.md").read_text(
                encoding="utf-8"
            ),
            "# skill\n",
        )


if __name__ == "__main__":
    unittest.main()
