---
name: audit-references
description: "Use when literature notes exist and need citation verification, or before publishing any artifact that cites literature"
complexity: medium
model-minimum: glm-5
disable-model-invocation: false
allowed-tools: ["Read", "Write", "Grep", "Glob", "WebFetch", "Bash(git *)"]
argument-hint: "[project path or publication draft path]"
---

# /audit-references <project path or draft path>

Verify every literature note and cited reference in a project or publication draft by fetching each URL and confirming the paper's identity. This is a mechanical verification procedure — do not rely on memory or judgment about whether a paper is real.

## When to use this

- **Pre-publication gate**: Before committing or sharing any publication draft, run this to verify all cited references.
- **Post-literature-review**: After `/lit-review` produces notes, run this to verify them.
- **Periodic audit**: On any project with a `literature/` directory that hasn't been audited recently.
- **Incident response**: When a hallucination is suspected in any literature note.

## Step 1: Discover literature notes

If the argument is a project directory (e.g., `projects/sample-project/`):
- Glob for `<project>/literature/*.md` (exclude `synthesis.md` or any non-note files)
- These are the notes to audit

If the argument is a publication draft file:
- Read the draft and extract all citation references (author-year style, footnotes, or bibliography entries)
- For each citation, find the corresponding literature note in the project's `literature/` directory
- Flag any citations that have no corresponding literature note

## Step 2: Extract claims from each note

For each literature note, extract:
1. **Claimed title** — from the `Citation:` line or `# <title>` heading
2. **Claimed authors** — from the `Citation:` line
3. **Claimed URL/DOI** — from the `URL/DOI:` line
4. **Claimed venue/year** — from the `Citation:` line
5. **Current `verified` field** — if present in the note

## Step 3: Fetch and verify each URL

For each URL/DOI:

1. **Fetch the URL** using WebFetch. For arxiv URLs, fetch the abstract page (e.g., `https://arxiv.org/abs/XXXX.XXXXX`).
2. **Extract the actual title** from the fetched page.
3. **Extract actual authors** from the fetched page.
4. **Compare title**: Does the fetched title match the claimed title? Use fuzzy matching — minor differences in capitalization, punctuation, or subtitle formatting are acceptable. A completely different topic is a FAIL.
5. **Compare authors**: Does at least one claimed author appear in the fetched author list? One match is sufficient.
6. **Record the result**: PASS (title matches, author matches), FAIL (title or author mismatch), or ERROR (URL unreachable, 404, paywall, etc.).

If a DOI is provided, fetch `https://doi.org/<DOI>` which redirects to the paper page.

## Step 4: Update `verified` field

For each literature note:
- If verification PASSED: add or update `verified: YYYY-MM-DD` below the `CI layers:` line (using today's date).
- If verification FAILED: add or update `verified: false` and add a warning comment explaining the mismatch.
- If verification had an ERROR: add `verified: error — <reason>` and note that manual verification is needed.

## Step 5: Generate audit report

Produce a summary table and save it to `<project>/literature/audit-YYYY-MM-DD.md`:

```
# Literature Audit: <project name>

Date: YYYY-MM-DD
Notes audited: N
Passed: N
Failed: N
Errors: N

## Results

| File | Claimed title | URL | Title match | Author match | Status |
|------|--------------|-----|-------------|--------------|--------|
| <filename> | <claimed title> | <url> | yes/NO | yes/NO | PASS/FAIL/ERROR |

## Failed verifications

### <filename>
- Claimed: "<claimed title>" by <claimed authors>
- Fetched: "<actual title>" by <actual authors>
- Action needed: <remove note / correct URL / flag for human review>

## Notes

<any observations about patterns in failures, e.g., systematic fabrication, stale URLs, minor discrepancies>
```

## Step 6: Flag downstream contamination

If any notes FAILED verification and the argument was a publication draft:
- List every place in the draft where the failed note is cited
- Recommend specific text to remove or flag

If any notes FAILED and there is a `synthesis.md` in the literature directory:
- Check whether the synthesis cites claims from failed notes
- List the contaminated sections

## Judgment rules

- A title mismatch where the fetched page is on a **completely different topic** is a hallucination. Mark as FAIL.
- A title mismatch where the fetched page is **the same paper with a slightly different title** (e.g., camera-ready vs preprint) is acceptable. Mark as PASS with a note.
- An author list where none of the claimed authors appear is a strong hallucination signal. Mark as FAIL.
- A 404 or unreachable URL is not proof of hallucination — the paper may have moved. Mark as ERROR and note that manual verification is needed.
- If you recognize a paper from your training data, that recognition is **not verification**. You must still fetch the URL. The whole point of this skill is to replace judgment with mechanical checking.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "I'm confident this paper is real — I know this work" | Your confidence is not evidence. Parametric memory fabricates plausible-sounding papers. Fetch the URL. |
| "The URL is obviously correct from the authors and year" | Hallucinated papers have plausible-looking URLs too. Fetch it. |
| "Fetching will just confirm what I already know" | Then fetching costs you 5 seconds. Not fetching risks a hallucinated citation in a publication. |
| "This is a well-known landmark paper" | A research project incident fabricated 7 papers, some citing "well-known" venues. Fetch it. |
| "The DOI resolves so it must be correct" | DOIs can point to different papers than claimed. Check the title and authors on the fetched page. |
| "Minor title mismatch is fine, clearly the same paper" | Verify authors too. A different paper on a similar topic can have a similar title. |
| "The URL timed out, but I know this paper exists" | Mark as ERROR and note for manual verification. Do not mark as PASS. |

## Red Flags — STOP

- About to mark a note as "verified" without having used WebFetch in this session
- Reasoning about whether a paper "probably exists" instead of fetching
- Skipping a note because "it was verified last time" (re-verify if re-auditing)
- Marking a failed fetch as PASS because you "recognize" the paper

## Commit

Follow `docs/sops/commit-workflow.md`. Commit message: `audit-references: <project> — N notes audited, N passed, N failed`
