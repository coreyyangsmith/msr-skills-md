---
name: "healthcheck"
description: "Internal codebase and operations health check — the CTO scans technical health, the COO checks operational health. Run bi-weekly to catch internal issues. Lightweight maintenance, not the main event."
---

# Healthcheck — Internal Maintenance

## Role Resolution

Read `.claude/agent-registry.json` to map roles to agent names. Use each agent's `id` as the `subagent_type` when spawning. The CTO handles technical health; the COO handles operational health.

---

Run a healthcheck: the CTO scans codebase health, the COO checks operational health. Findings get triaged by risk: low-risk auto-fixes, medium-risk batched for CEO, high-risk backlogged.

**This is maintenance, not strategy.** For external intelligence gathering (competitors, trends, frameworks), use `/scout`. Healthcheck is the janitor, not the executive.

## Step 1: Read Context

Read these before spawning agents:
- `.context/vision.md` — guardrails (what NOT to break)
- `.context/preferences.md` — CEO standing orders
- `.context/directives/*/directive.json` — current directives (to check for staleness)
- `.context/lessons/orchestration.md`
- `.context/backlog.json` — what's already queued
- Recent directive reports in `.context/reports/` — what was recently done

## Step 2: Spawn Healthcheck Agents (Parallel)

Spawn **2 agents** in parallel: the CTO (technical) and the COO (operational).

Each agent receives:
- Their full personality from `.claude/agents/{name}.md`
- `.context/vision.md` (guardrails are critical)
- `.context/preferences.md`
- `.context/directives/*/directive.json`
- `.context/backlog.json` summary
- Recent directive report summaries (filenames + dates)

**Both agents**: `subagent_type: "general-purpose"`, `model: "opus"`

### CTO — Technical Health

```
You are the CTO. You are running a standing healthcheck of the codebase.

Your job: scan the codebase and infrastructure for internal issues.

CHECK THESE AREAS:
1. **Security**: Run `npm audit` in each app directory. Check for hardcoded credentials (grep for API keys, passwords, tokens in source files). Look for unauthed endpoints, injection vectors.
2. **Dependencies**: Check package.json files for outdated or deprecated packages. Look for packages with known CVEs.
3. **Architecture**: Look for code smells — files over 500 lines, circular imports, inconsistent patterns across apps. Check for dead code (unused exports, unreferenced files).
4. **Type safety**: Run `npm run type-check` and report any errors. Check for `any` type usage, missing type definitions.
5. **Production health**: Check for error handling gaps, missing try/catch around external API calls, unhandled promise rejections.

USE THESE TOOLS: Bash (npm audit, type-check), Grep (security patterns, dead code), Glob (file structure), Read (specific files)

DO NOT fix anything. Report findings only.

{JSON output instructions below}
```

### COO — Operational Health

```
You are the COO. You are running a standing healthcheck of project operations.

Your job: audit project operations for stale goals, blocked work, and resource gaps.

CHECK THESE AREAS:
1. **Directive freshness**: Read all directives in `.context/directives/*/directive.json`. Are any stale (no progress in 2+ weeks)?
2. **Backlog health**: Read `.context/backlog.json`. Are items prioritized? Are there items marked done that should be cleaned up? Any duplicates?
3. **Active work**: Check `.context/directives/*/projects/*/project.json` for active projects. Is anything in progress but stuck? Any projects without recent file changes?
4. **Recent directives**: Read `.context/reports/`. Were there failures or follow-ups that haven't been addressed?
5. **Process gaps**: Check if lessons.md is up to date. Are there patterns emerging from recent work that should be captured?
6. **Backlog health (structured checks)**:
   - Read `.context/backlog.json` — check for stale items older than 30 days.
   - Count items per priority (P0/P1/P2). Flag any category with 0 prioritized items.
   - Check for duplicate items (same item title appearing multiple times).
7. **Partially-done project detection**:
   - Read ALL `.context/directives/*/projects/*/project.json` files (tasks are embedded)
   - For each: count completed vs total tasks, compute completion percentage
   - Flag if completion > 50% but the project's most recently modified file is > 14 days old
   - Flag if completion is 100% but project status is still "active" (should be "completed")
8. **Index accuracy**:
   - Verify that project statuses in project.json match actual task completion
   - Flag any mismatches between directive status and project statuses
   - Verify project.json files match filesystem structure
9. **Active/done duplicates**:
   - Check for projects with contradictory status vs task completion
   - Flag as: "project {name} has status {status} but tasks show {completion}% complete"

USE THESE TOOLS: Read (context files, reports), Glob (directive structure, projects), Grep (stale dates, TODO items)

DO NOT fix anything. Report findings only.

{JSON output instructions below}
```

### JSON Output Format (same for both agents)

Append these instructions to each agent's prompt:

```
CRITICAL OUTPUT FORMAT: Your response must contain ONLY valid JSON. No prose, no analysis summary, no markdown fences, no text before or after the JSON. The very first character of your response must be `{` and the very last must be `}`.

Your output must follow this schema:

{
  "agent": "cto-id | coo-id",
  "domain": "technical | operations",
  "healthcheck_date": "YYYY-MM-DD",
  "findings": [
    {
      "id": "finding-slug",
      "severity": "critical | high | medium | low | info",
      "area": "Which area this falls under (e.g., security, dependencies, goal-freshness)",
      "title": "Short description of the finding",
      "detail": "What you found — be specific with file paths, line numbers, counts",
      "evidence": "The grep output, command output, or file content that proves this",
      "suggested_fix": "What should be done about this (1-2 sentences)",
      "risk_level": "low | medium | high",
      "already_tracked": "If this is already in a backlog or OKR, reference it here. Otherwise null."
    }
  ],
  "summary": "2-3 sentence overview of domain health"
}

SEVERITY GUIDE:
- critical: Active security vulnerability, data exposure, broken production feature
- high: Significant technical debt, degraded user experience, stale critical goals
- medium: Code quality issues, minor gaps, optimization opportunities
- low: Nice-to-have improvements, minor inconsistencies
- info: Observations, no action needed

RISK LEVEL (for triage):
- low: Safe to auto-fix (dead code deletion, unused import cleanup, minor config fixes)
- medium: Needs CEO awareness (dependency updates, backlog reorganization, goal reprioritization)
- high: Needs CEO decision (architectural changes, security patches, goal changes)
```

**Parse each agent's response** as JSON. If any fails to parse, log the error and continue.

## Step 3: Triage Findings

After both agents return, triage all findings by risk level:

### Low-risk (auto-fixable)
- Dead code deletion, unused imports, minor config fixes
- Present to CEO as: "Auto-fixing {N} low-risk items: {list}"
- Execute the fixes immediately (spawn an engineer if needed)

### Medium-risk (CEO batch approval)
- Dependency updates, backlog cleanup, stale goal flagging
- Present as a batch: "Found {N} medium-risk items that need your approval"
- CEO approves/rejects the batch

### High-risk (CEO decides)
- Security patches, architectural changes, goal modifications
- Add to `.context/backlog.json`
- Flag for CEO attention in the next `/report`

## Step 4: Present Results

```
# Healthcheck Report — {date}

## Summary
- **Technical (CTO)**: {summary}
- **Operational (COO)**: {summary}

## Auto-Fixed (low-risk)
{list of low-risk items that were automatically fixed, or "None"}

## Needs Your Approval ({count} medium-risk)
{list of medium-risk items with suggested fixes}

## Backlogged ({count} high-risk)
{list of high-risk items added to backlogs}

## All Clear
{any areas where no issues were found}
```

## Step 5: Save Results

Write each agent's raw JSON output to `.context/healthchecks/latest/{agent}.json`, overwriting any previous file.

If the `latest/` directory already has files, move them to `archive/{date}/` first.

Create directories if needed: `mkdir -p .context/healthchecks/latest .context/healthchecks/archive`

## Failure Handling

| Situation | Action |
|-----------|--------|
| An agent's output doesn't parse as JSON | Log the error, continue with the other agent. |
| An agent finds no issues | Include their "all clear" summary. Good outcome. |
| npm audit fails to run | Note the error, skip security section. |
| Type-check fails to run | Note the error, skip type safety section. |
| All findings are low-risk | Auto-fix all, report clean bill of health. |

## Rules

### NEVER
- Fix high-risk issues without CEO approval
- Skip the CTO (always run technical health)
- Propose strategic initiatives (that's /scout's job)
- Overwrite previous healthcheck results without archiving

### ALWAYS
- Read context files before spawning agents
- Include personality files in agent prompts
- Auto-fix low-risk items (that's the whole point of healthcheck being lightweight)
- Save results to healthchecks/latest/ for /report to read
- Keep it fast — healthcheck should complete in under 10 minutes
