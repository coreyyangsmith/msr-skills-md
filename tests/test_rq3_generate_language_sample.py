from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq3.generate_language_sample import (
    collect_skill_files,
    filter_skill_files_by_allowed_repos,
    group_skills_by_repo,
    sample_and_copy,
)


def _write_skill(root: Path, repo_folder: str, *parts: str) -> Path:
    """Create a SKILL.md under root/<repo_folder>/<parts...>/SKILL.md."""
    skill_dir = root.joinpath(repo_folder, *parts)
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(f"# {repo_folder} {'/'.join(parts)}\n", encoding="utf-8")
    return path


def _repo_folders_in_sample(sampled: list[Path], root: Path) -> list[str]:
    return [src.relative_to(root).parts[0] for src in sampled]


class TestRq3GenerateLanguageSample(unittest.TestCase):
    def test_group_skills_by_repo_keys_on_top_level_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a1 = _write_skill(root, "alice__repo-a", "skill-one")
            a2 = _write_skill(root, "alice__repo-a", "skill-two")
            b1 = _write_skill(root, "bob__repo-b", "only")

            grouped = group_skills_by_repo(root, [a1, a2, b1])

            self.assertEqual(set(grouped), {"alice__repo-a", "bob__repo-b"})
            self.assertEqual(len(grouped["alice__repo-a"]), 2)
            self.assertEqual(len(grouped["bob__repo-b"]), 1)

    def test_sample_returns_one_skill_per_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            _write_skill(root, "alice__repo-a", "skill-one")
            _write_skill(root, "alice__repo-a", "skill-two")
            _write_skill(root, "alice__repo-a", "skill-three")
            _write_skill(root, "bob__repo-b", "only")
            _write_skill(root, "carol__repo-c", "x")
            _write_skill(root, "carol__repo-c", "y")

            all_files = collect_skill_files(root)
            sampled = sample_and_copy(all_files, root, n=2, out_dir=out, seed=42)

            self.assertEqual(len(sampled), 2)
            folders = _repo_folders_in_sample(sampled, root)
            self.assertEqual(len(folders), len(set(folders)))
            for src in sampled:
                dst = out / src.relative_to(root)
                self.assertTrue(dst.is_file())

    def test_dominant_repo_never_contributes_two_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            for i in range(20):
                _write_skill(root, "heavy__repo", f"skill-{i}")
            _write_skill(root, "light__a", "s")
            _write_skill(root, "light__b", "s")
            _write_skill(root, "light__c", "s")

            all_files = collect_skill_files(root)
            # File-level sampling of n=3 would almost always pick from heavy__;
            # repo-first must still return three distinct repos.
            sampled = sample_and_copy(all_files, root, n=3, out_dir=out, seed=7)

            self.assertEqual(len(sampled), 3)
            folders = _repo_folders_in_sample(sampled, root)
            self.assertEqual(len(set(folders)), 3)

    def test_same_seed_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for repo in ("a__one", "b__two", "c__three", "d__four"):
                _write_skill(root, repo, "skill-a")
                _write_skill(root, repo, "skill-b")

            all_files = collect_skill_files(root)
            first = sample_and_copy(
                all_files, root, n=3, out_dir=root / "out1", seed=99
            )
            second = sample_and_copy(
                all_files, root, n=3, out_dir=root / "out2", seed=99
            )

            self.assertEqual(
                [p.relative_to(root) for p in first],
                [p.relative_to(root) for p in second],
            )

    def test_n_larger_than_repo_count_clamps_to_all_repos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            _write_skill(root, "a__one", "s1")
            _write_skill(root, "a__one", "s2")
            _write_skill(root, "b__two", "s1")

            all_files = collect_skill_files(root)
            sampled = sample_and_copy(all_files, root, n=50, out_dir=out, seed=1)

            self.assertEqual(len(sampled), 2)
            folders = _repo_folders_in_sample(sampled, root)
            self.assertEqual(set(folders), {"a__one", "b__two"})

    def test_allowed_repos_filter_excludes_before_sampling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            _write_skill(root, "keep__repo", "s1")
            _write_skill(root, "keep__repo", "s2")
            _write_skill(root, "drop__repo", "s1")
            _write_skill(root, "also__keep", "s1")

            csv_path = root / "allowed.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["name", "mainLanguage"])
                writer.writeheader()
                writer.writerow({"name": "keep/repo", "mainLanguage": "Python"})
                writer.writerow({"name": "also/keep", "mainLanguage": "Python"})
                writer.writerow({"name": "drop/repo", "mainLanguage": "Go"})

            from rq3.generate_language_sample import load_allowed_repos_from_csv

            allowed = load_allowed_repos_from_csv(csv_path, "Python")
            all_files = collect_skill_files(root)
            filtered = filter_skill_files_by_allowed_repos(all_files, root, allowed)
            sampled = sample_and_copy(filtered, root, n=10, out_dir=out, seed=3)

            folders = set(_repo_folders_in_sample(sampled, root))
            self.assertEqual(folders, {"keep__repo", "also__keep"})
            self.assertNotIn("drop__repo", folders)


if __name__ == "__main__":
    unittest.main()
