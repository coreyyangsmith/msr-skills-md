import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "rq2"))
from analyze_skill_dependencies import analyze_skill


def test_analyze_skill_reference_classification():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill = root / "skills" / "demo"
        (skill / "scripts").mkdir(parents=True)
        (skill / "scripts" / "run.py").write_text("")
        (skill / "unused.json").write_text("")
        (root / "skills" / "other").mkdir()
        (root / "skills" / "other" / "SKILL.md").write_text("# other")
        (skill / "nested").mkdir()
        (skill / "nested" / "SKILL.md").write_text("# nested skill, not part of the bundle")
        (skill / "SKILL.md").write_text(
            "# Demo\n## Use\nRun `scripts/run.py`, then run.py again.\n"
            "See ../other/SKILL.md, skills/missing/SKILL.md and references/missing.md.\n"
            "Follow CLAUDE.md and .claude/settings.json. Keep references/README.md current.\n"
            "Edit package.json and vite.config.ts. Read src/index.ts. Uses Three.js.\n"
            "Example: path/to/file.ts, file.py, *.test.ts, {root}/SKILL.md. Load {root}/AGENTS.md; svelte.config.js.\n"
            "Docs: https://example.com/guide.html\n"
        )
        r = analyze_skill(skill / "SKILL.md")
    expected = {
        "headings": 2, "h1": 1, "h2": 1, "h3": 0, "bundled_files": 2,
        "refs_bundle": 2, "refs_outside": 2, "refs_dangling": 2, "refs_agent_config": 3, "refs_unverified": 1,
        "refs_filtered_project": 3, "refs_filtered_library": 1, "refs_filtered_placeholder": 4,
        "local_refs": 10, "refs_url": 1, "all_refs": 11, "filtered_mentions": 8, "orphan_files": 1,
    }
    assert {k: r[k] for k in expected} == expected
