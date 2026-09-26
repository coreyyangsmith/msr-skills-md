from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))

from constrain_dataset_languages import (
    ALLOWED_MAIN_LANGUAGES,
    count_duplicate_keys,
    filter_csv_rows,
    filter_raw_data_dirs,
    normalize_languages,
    remaining_languages,
    snapshot_refuses_nonempty,
)


class TestConstrainDatasetLanguages(unittest.TestCase):
    def test_normalize_languages_is_case_insensitive_and_stable(self) -> None:
        self.assertEqual(
            normalize_languages([" python", "TypeScript", "PYTHON"]),
            ["Python", "TypeScript"],
        )

    def test_filter_csv_rows_keeps_schema_order_and_duplicates(self) -> None:
        rows = [
            {"repo": "a/one", "skill_path": "skills/a/SKILL.md", "mainLanguage": "Python"},
            {"repo": "b/two", "skill_path": "skills/b/SKILL.md", "mainLanguage": "Rust"},
            {"repo": "a/one", "skill_path": "skills/a/SKILL.md", "mainLanguage": "python"},
            {"repo": "c/three", "skill_path": "skills/c/SKILL.md", "mainLanguage": "TypeScript"},
        ]
        fieldnames = ["repo", "skill_path", "mainLanguage"]
        kept = filter_csv_rows(rows, fieldnames, ["Python", "TypeScript"])
        self.assertEqual(
            [row["repo"] for row in kept],
            ["a/one", "a/one", "c/three"],
        )
        self.assertEqual(list(kept[0].keys()), fieldnames)

    def test_filter_csv_rows_applies_repo_filter_and_keeps_last_skill_row(self) -> None:
        rows = [
            {"repo": "a/one", "skill_path": "s/SKILL.md", "mainLanguage": "Python", "scanned_at_utc": "old"},
            {"repo": "a/agent-kit", "skill_path": "s/SKILL.md", "mainLanguage": "Python", "scanned_at_utc": "x"},
            {"repo": "a/one", "skill_path": "s/SKILL.md", "mainLanguage": "Python", "scanned_at_utc": "new"},
            {"repo": "a/one", "skill_path": "t/SKILL.md", "mainLanguage": "Python", "scanned_at_utc": "x"},
        ]
        fieldnames = ["repo", "skill_path", "mainLanguage", "scanned_at_utc"]
        kept = filter_csv_rows(
            rows,
            fieldnames,
            ["Python"],
            exclude_repo=lambda repo: "agent" in repo.split("/", 1)[-1],
            dedupe_skill_rows=True,
        )
        self.assertEqual(
            [(row["skill_path"], row["scanned_at_utc"]) for row in kept],
            [("s/SKILL.md", "new"), ("t/SKILL.md", "x")],
        )

    def test_repo_filter_matches_population_name_column(self) -> None:
        from constrain_dataset_languages import row_repo

        self.assertEqual(row_repo({"name": "a/b"}), "a/b")

    def test_count_duplicate_keys_does_not_drop_rows(self) -> None:
        rows = [
            {"repo": "a/one", "skill_path": "skills/a/SKILL.md"},
            {"repo": "a/one", "skill_path": "skills/a/SKILL.md"},
            {"repo": "b/two", "skill_path": "skills/b/SKILL.md"},
        ]
        self.assertEqual(count_duplicate_keys(rows, ("repo", "skill_path")), 1)
        self.assertEqual(len(rows), 3)

    def test_filter_raw_data_dirs_copies_only_selected_languages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "raw"
            dest = Path(tmp) / "filtered"
            (src / "Python" / "acme__demo").mkdir(parents=True)
            (src / "Python" / "acme__demo" / "SKILL.md").write_text("py\n", encoding="utf-8")
            (src / "TypeScript" / "acme__web").mkdir(parents=True)
            (src / "TypeScript" / "acme__web" / "SKILL.md").write_text("ts\n", encoding="utf-8")
            (src / "Rust" / "acme__cli").mkdir(parents=True)
            (src / "Rust" / "acme__cli" / "SKILL.md").write_text("rs\n", encoding="utf-8")

            copied = filter_raw_data_dirs(src, dest, ["Python", "TypeScript"], dry_run=False)
            self.assertEqual(sorted(copied), ["Python", "TypeScript"])
            self.assertTrue((dest / "Python" / "acme__demo" / "SKILL.md").exists())
            self.assertTrue((dest / "TypeScript" / "acme__web" / "SKILL.md").exists())
            self.assertFalse((dest / "Rust").exists())
            self.assertEqual(remaining_languages(dest), {"Python", "TypeScript"})

    def test_filter_raw_data_dirs_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "raw"
            dest = Path(tmp) / "filtered"
            (src / "Python" / "acme__demo").mkdir(parents=True)
            (src / "Python" / "acme__demo" / "SKILL.md").write_text("py\n", encoding="utf-8")
            copied = filter_raw_data_dirs(src, dest, ["Python"], dry_run=True)
            self.assertEqual(copied, ["Python"])
            self.assertFalse(dest.exists())

    def test_snapshot_refuses_nonempty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "archive"
            dest.mkdir()
            (dest / "already.txt").write_text("nope\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                snapshot_refuses_nonempty(dest)

    def test_allowed_main_languages_are_python_and_typescript(self) -> None:
        self.assertEqual(ALLOWED_MAIN_LANGUAGES, ("Python", "TypeScript"))

    def test_filter_csv_roundtrip_preserves_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.csv"
            dest = Path(tmp) / "out.csv"
            with src.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["repo", "mainLanguage"])
                writer.writeheader()
                writer.writerow({"repo": "a/one", "mainLanguage": "Go"})
                writer.writerow({"repo": "b/two", "mainLanguage": "TypeScript"})
            from constrain_dataset_languages import filter_csv_file

            n_kept, n_total = filter_csv_file(src, dest, ["typescript"], dry_run=False)
            self.assertEqual((n_kept, n_total), (1, 2))
            with dest.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [{"repo": "b/two", "mainLanguage": "TypeScript"}])


if __name__ == "__main__":
    unittest.main()
