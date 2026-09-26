#!/usr/bin/env python3
"""RQ2: size (words, headings) and dependency/coupling profile of SKILL.md artifacts.

Every path-like mention in a SKILL.md is resolved against the files on disk:
  bundle     -> resolves to a file shipped inside the skill folder (intra-skill dependency)
  outside    -> resolves to an existing file outside the skill folder, or escapes it via ../
                (cross-skill / repo coupling; the skill is no longer self-contained)
  dangling   -> looks like a bundle path (./, scripts/, references/, ...) but no file exists
                (upper bound on broken dependencies: also catches repo-root paths and runtime outputs)
  agent_config -> agent configuration files (CLAUDE.md, AGENTS.md, .mcp.json, .claude/...)
  unverified -> any other file mention (src/index.ts, docs/graph.json, ...); raw_data only holds
                skill folders, so these cannot be checked
Mentions that are not dependencies of the skill are filtered out (counted separately, excluded from references):
  filtered_project     -> the target project's own manifests/config/standard docs (package.json, README.md, CI files)
  filtered_library     -> library names caught by the .js extension (Three.js, Vue.js)
  filtered_placeholder -> placeholders and pattern/template fragments (file.py, path/to/x.ts, .test.ts, /SKILL.md)
URLs are counted separately as external dependencies. Bundled files never mentioned in SKILL.md are orphans.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_skill_documents import collect_markdown_structure, extract_file_paths, extract_urls  # noqa: E402

BUNDLE_DIRS = ("scripts", "references", "assets", "templates", "examples")
BUNDLE_PREFIXES = ("./",) + tuple(d + "/" for d in BUNDLE_DIRS)
REF_KINDS = ["bundle", "outside", "dangling", "agent_config", "unverified"]
FILTERED_KINDS = ["filtered_project", "filtered_library", "filtered_placeholder"]

PROJECT_FILES = {
    "package.json", "package-lock.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "yarn.lock", "bun.lock",
    "pyproject.toml", "setup.py", "requirements.txt", "requirements-dev.txt", "pipfile.lock", "poetry.lock",
    "uv.lock", "cargo.toml", "cargo.lock", "pom.xml", "tsconfig.json", "jsconfig.json", "deno.json",
    "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", ".gitlab-ci.yml",
    ".pre-commit-config.yaml", "nx.json", "turbo.json", "lerna.json", "components.json", "vercel.json",
    "netlify.toml", "wrangler.toml", "mkdocs.yml", "conftest.py", "__init__.py", "manage.py",
    "readme.md", "changelog.md", "contributing.md", "license.md", "license.txt", "code_of_conduct.md",
    "security.md", "robots.txt",
}
PROJECT_CONFIG_RE = re.compile(
    r"(vite|vitest|jest|playwright|tailwind|next|webpack|babel|eslint|postcss|rollup|svelte|astro|nuxt"
    r"|drizzle|prettier|cypress|tsup|esbuild|karma|metro|app)\.config\.\w+$|^\.(eslintrc|prettierrc|babelrc)(\.\w+)?$"
)
LIBRARY_NAMES = {
    "three", "vue", "d3", "chart", "express", "alpine", "anime", "ember", "backbone", "p5", "react", "angular",
    "nuxt", "nest", "svelte", "solid", "preact", "pixi", "phaser", "tone", "paper", "fabric", "leaflet", "moment",
    "day", "lodash", "jquery", "require", "ml5", "tensorflow", "brain", "cytoscape", "sigma", "vis", "video",
    "hls", "pdf", "highlight", "prism", "marked", "babylon", "cannon", "matter", "knockout", "handlebars",
    "mustache", "underscore", "lit", "htmx", "meteor", "electron", "fastify", "koa", "hono", "plotly", "echarts",
    "reveal", "impress", "mermaid", "katex", "mathjax", "ogl", "regl", "rough", "gsap", "lottie", "howler",
    "cheerio", "zod", "remix", "gatsby", "sails", "feathers", "strapi", "popper", "swiper", "socket", "pdfkit",
}
PLACEHOLDER_STEM_RE = re.compile(r"^(file|foo|bar|baz|qux|filename|my[-_]?file|your[-_]?file|some[-_]?file|name)\d*$")
AGENT_CONFIG_FILES = {"claude.md", "claude.local.md", "agents.md", "gemini.md", "copilot-instructions.md",
                      ".mcp.json", "mcp.json", ".claude.json"}
AGENT_CONFIG_DIRS = {".claude", ".cursor", ".codex", ".windsurf", ".gemini", ".opencode", ".kiro"}

METRICS = [
    ("words", "Words"),
    ("headings", "Headings (H1--H6)"),
    ("h1", "\\quad H1"),
    ("h2", "\\quad H2"),
    ("h3", "\\quad H3"),
    ("bundled_files", "Bundled files"),
    ("all_refs", "All references"),
    ("local_refs", "\\quad File references"),
    ("refs_bundle", "\\qquad Resolved in bundle"),
    ("refs_outside", "\\qquad Outside bundle"),
    ("refs_dangling", "\\qquad Dangling"),
    ("refs_agent_config", "\\qquad Agent config files"),
    ("refs_unverified", "\\qquad Unverified"),
    ("refs_url", "\\quad URL references"),
    ("filtered_mentions", "Filtered mentions"),
    ("refs_filtered_project", "\\quad Project files"),
    ("refs_filtered_library", "\\quad Library names"),
    ("refs_filtered_placeholder", "\\quad Placeholders/patterns"),
    ("orphan_files", "Orphan bundled files"),
]
REF_METRICS = {"all_refs", "local_refs", "refs_url"} | {f"refs_{k}" for k in REF_KINDS}
FILTERED_METRICS = {"filtered_mentions"} | {f"refs_{k}" for k in FILTERED_KINDS}


def bundled_files(skill_dir: Path) -> list[str]:
    """Files in the skill folder (posix, relative), excluding SKILL.md and nested skill folders."""
    out: list[str] = []
    for root, dirs, files in os.walk(skill_dir):
        root_path = Path(root)
        if root_path != skill_dir and any(f.lower() == "skill.md" for f in files):
            dirs[:] = []
            continue
        for name in files:
            if root_path == skill_dir and name.lower() == "skill.md":
                continue
            out.append((root_path / name).relative_to(skill_dir).as_posix())
    return out


def classify_path(mention: str, skill_dir: Path, bundle: list[str]) -> str:
    rel = mention[2:] if mention.startswith("./") else mention
    if rel in bundle or any(b.endswith("/" + rel) for b in bundle):
        return "bundle"
    if "/" not in rel and any(b.rsplit("/", 1)[-1] == rel for b in bundle):
        return "bundle"
    target = os.path.normpath(os.path.join(skill_dir, mention))
    # Absolute mentions ("/etc/x.conf", "//host/x") must not hit the filesystem: on Windows "//host" is a UNC lookup.
    if not mention.startswith("/") and os.path.isfile(target):
        inside = os.path.commonpath([target, os.path.normpath(skill_dir)]) == os.path.normpath(skill_dir)
        return "bundle" if inside else "outside"
    if mention.startswith("../"):
        return "outside"

    # "/x.md" is what the regex leaves of "{root}/x.md": a real file at an unknown root, classified by name.
    if re.fullmatch(r"/[^/]+", mention):
        rel = mention[1:]
    name = rel.rsplit("/", 1)[-1]
    lower = name.lower()
    stem = lower.split(".", 1)[0]
    if (
        mention == "/SKILL.md"
        or PLACEHOLDER_STEM_RE.match(stem)
        or "path/to/" in rel.lower()
        or re.search(r"yyyy|xxx", lower)
        or name.startswith("-")
        or re.fullmatch(r"\.(test|spec|d|stories|module|e2e|min)\.\w+", lower)
    ):
        return "filtered_placeholder"
    if "/" not in rel and lower.count(".") == 1 and lower.endswith(".js") and stem in LIBRARY_NAMES:
        return "filtered_library"
    if mention.startswith(BUNDLE_PREFIXES):
        return "dangling"
    if lower in PROJECT_FILES or PROJECT_CONFIG_RE.search(lower) or ".github/workflows/" in rel:
        return "filtered_project"
    if name == "SKILL.md":
        return "outside"
    if lower in AGENT_CONFIG_FILES or AGENT_CONFIG_DIRS & set(rel.split("/")[:-1]):
        return "agent_config"
    return "unverified"


def analyze_skill(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8", errors="ignore")
    skill_dir = skill_md.parent
    bundle = bundled_files(skill_dir)
    # A bare "SKILL.md" mention is almost always self-referential ("this SKILL.md"), not a dependency.
    mentions = [p for p in extract_file_paths(text) if p != "SKILL.md"]
    counts = dict.fromkeys(REF_KINDS + FILTERED_KINDS, 0)
    for mention in mentions:
        counts[classify_path(mention, skill_dir, bundle)] += 1
    local_refs = sum(counts[k] for k in REF_KINDS)
    urls = len(extract_urls(text))
    orphans = [b for b in bundle if b not in text and b.rsplit("/", 1)[-1] not in text]
    structure = collect_markdown_structure(text)
    return {
        "words": len(text.split()),
        "headings": structure["heading_count"],
        "h1": structure["heading_h1_count"],
        "h2": structure["heading_h2_count"],
        "h3": structure["heading_h3_count"],
        "bundled_files": len(bundle),
        "all_refs": local_refs + urls,
        "local_refs": local_refs,
        **{f"refs_{k}": v for k, v in counts.items()},
        "refs_url": urls,
        "filtered_mentions": sum(counts[k] for k in FILTERED_KINDS),
        "orphan_files": len(orphans),
    }


def spearman(xs: list[float], ys: list[float]) -> float:
    from scipy.stats import spearmanr

    return float(spearmanr(xs, ys).statistic)


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    summary = {"n": n, "metrics": {}}
    for key, _ in METRICS:
        values = [r[key] for r in rows]
        summary["metrics"][key] = {
            "min": min(values), "median": median(values), "mean": mean(values), "max": max(values),
            "pct_nonzero": 100 * sum(v > 0 for v in values) / n,
            "total": sum(values),
        }
    total_refs = summary["metrics"]["all_refs"]["total"]
    total_mentions = summary["metrics"]["local_refs"]["total"] + summary["metrics"]["filtered_mentions"]["total"]
    for key in REF_METRICS:
        summary["metrics"][key]["pct_of_refs"] = 100 * summary["metrics"][key]["total"] / max(1, total_refs)
    for key in FILTERED_METRICS:
        summary["metrics"][key]["pct_of_file_mentions"] = (
            100 * summary["metrics"][key]["total"] / max(1, total_mentions)
        )
    with_bundle = [r for r in rows if r["bundled_files"] > 0]
    summary["bundled_skills"] = {
        "n": len(with_bundle),
        "pct_bundle_files_orphaned": 100 * sum(r["orphan_files"] for r in with_bundle)
        / max(1, sum(r["bundled_files"] for r in with_bundle)),
        "pct_skills_with_orphan": 100 * sum(r["orphan_files"] > 0 for r in with_bundle) / max(1, len(with_bundle)),
    }
    summary["spearman"] = {
        f"{a}~{b}": spearman([r[a] for r in rows], [r[b] for r in rows])
        for a in ("words", "headings")
        for b in ("bundled_files", "local_refs", "refs_url")
    }
    return summary


def write_tex(path: Path, summary: dict) -> None:
    def fmt(v: float) -> str:
        return f"{v:,.2f}" if isinstance(v, float) and not v.is_integer() else f"{int(v):,}"

    groups = {"words": "Size and packaging", "all_refs": "References", "filtered_mentions": "Filtered (non-dependency) mentions"}
    lines = [
        "\\begin{tabular}{lrrrr}", "\\toprule",
        "\\textbf{Metric} & \\textbf{Median} & \\textbf{Mean} & \\textbf{\\% Skills} & \\textbf{\\% Refs} \\\\",
    ]
    for key, label in METRICS:
        if key == "orphan_files":
            continue
        if key in groups:
            lines += ["\\midrule", f"\\multicolumn{{5}}{{l}}{{\\textit{{{groups[key]}}}}} \\\\"]
        m = summary["metrics"][key]
        share = m.get("pct_of_refs")
        lines.append(f"{label} & {fmt(m['median'])} & {m['mean']:,.2f} & {m['pct_nonzero']:.1f} "
                     f"& {'--' if share is None else f'{share:.1f}'} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-data-dir", default="outputs/raw_data")
    parser.add_argument("--out-dir", default="outputs/rq2/dependencies")
    args = parser.parse_args(argv)

    raw = Path(args.raw_data_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for skill_md in sorted(p for p in raw.rglob("SKILL.md") if p.is_file()):
        parts = skill_md.relative_to(raw).parts
        if len(parts) < 3:
            continue
        rows.append({"language": parts[0], "repo": parts[1], "path": Path(*parts[2:]).as_posix(),
                     **analyze_skill(skill_md)})

    with (out / "skill_dependencies.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = summarize(rows)
    (out / "skill_dependencies_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_tex(out / "table_skillmd_dependencies.tex", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
