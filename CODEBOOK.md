# Codebook

Qualitative annotation codebook for SDLC-oriented `SKILL.md` files.

## Summary

| Group | Tags |
|---|---|
| Instruction Types | `purpose`, `activation`, `exclusion`, `workflow`, `decision-rule`, `action-directive`, `positive-example`, `negative-example`, `reference` |
| SDLC Stages | `documentation`, `requirement`, `design`, `code-implementation`, `program-analysis`, `testing`, `maintenance`, `debugging`, `devops` |
| Filter Out | `agent-skill`, `wrong-language` |

## Labeling Task

RQ2 already analyzes the `SKILL.md` name and description. For this qualitative analysis, we annotate SDLC-oriented `SKILL.md` files as instructions that the model should follow once the skill is in use.

- Use the `SKILL.md` **body** as the primary evidence.
- **Two exceptions:** `activation` and `exclusion` may also be coded from the YAML frontmatter `description`, or from a "When to Use" / "When NOT to Use" section, when that text says when the skill should or should not be used. Agent Skills usually put invocation criteria in `description`, so do not ignore it.
- Do not code the skill name alone as `purpose`, and do not treat a one-line title as enough evidence for any tag.
- If the file is out of scope, apply only a filter-out tag. Do **not** also apply instruction-type or SDLC tags.

## Instruction Types (8)

### 1. Purpose / Overview (`purpose`)

Describes what the skill does, its goal, or the capability it provides, without saying when it should activate or exactly how to perform the task.

Examples:
- "This skill provides a workflow for repository threat modeling."
- "This guide covers PDF creation and analysis."
- "The skill helps produce accessible frontend interfaces."

### 2. Activation Criteria (`activation`)

Defines the situations, user requests, file types, keywords, or conditions under which the skill should be used. Apply this tag whenever the skill says when to use it, even if `purpose`, `workflow`, or example tags already apply.

Include:
- "Use this skill when..."
- "Trigger when the user asks..."
- "Use whenever a .docx file is involved."
- "When to use: ..."
- A frontmatter `description` that names triggers, file types, or user intents.
- A dedicated "When to Use This Skill" / "When this applies" section.

Do not require a heading named "Activation." A description that only says what the skill does, with no when-to-use language, is `purpose`, not `activation`.

### 3. Exclusion Criteria (`exclusion`)

Defines conditions under which the skill should not activate, or circumstances outside its scope. This means the skill as a whole is out of scope. It is not an ordinary operational "do not" during the workflow, and it is not a negative example.

Include:
- "Do not use for PDFs."
- "Do not trigger for general code review."
- "This skill does not handle deployment."
- "When NOT to use..."
- "Do not use for photos, raster artwork, or quantitative data charts."
- Eligibility gates that abort the skill (e.g., do not review closed, merged, or draft PRs; abort if the issue is a duplicate).

Do **not** tag as `exclusion`:
- Step-level prohibitions such as "do not push," "do not guess URLs," or "do not install other packages at this stage."
- Behavioral constraints such as "Do not make claims without repository evidence."

These are `decision-rule`, `action-directive`, or workflow constraints unless they also define when the skill itself should not be used.

### 4. Procedural Workflow (`workflow`)

Defines an ordered or partially ordered process for the agent to follow. A workflow does not have to use "first, then, finally." It may be expressed through headings, branching rules, state transitions, or other structure. Use this tag when the skill lays out a procedure, not when it is self-contained or open-ended.

Include:
- Numbered steps
- Named phases or stages
- Explicit ordering
- Iterative loops
- Exit conditions
- Required sequencing

Examples:
- "Collect the inputs, analyze the repository, then generate the report."
- "Repeat until all validation checks pass."
- "Proceed to Stage 2 after sufficient context has been gathered."

### 5. Decision Rules and Conditional Logic (`decision-rule`)

Defines how the agent chooses between actions or adapts the workflow.

Examples:
- "If the document already exists, edit the XML directly."
- "Use pypdf for extraction, but use rendering when layout matters."
- "If the user declines the structured workflow, continue freeform."
- "Only install the dependency if the import fails."

This category matters because many skills are not simple linear procedures. They behave more like decision trees.

### 6. Tool and Action Directives (`action-directive`)

Directs the agent to perform a concrete action with a tool, command, API, script, file operation, or integration.

Include:
- Run a CLI command
- Execute a script
- Read or edit a file
- Call an API or MCP tool
- Search a repository
- Create an artifact
- Use a specific library

Examples:
- "Run `pytest tests/unit`."
- "Use pdfplumber to extract text."
- "Call `search_design_system` before creating components."
- "Write the final report to `<repository>-threat-model.md`."

### 7. Examples / Demonstrations (`positive-example`, `negative-example`)

Contains a concrete illustration of an input, output, command, interaction, or implementation pattern.

Tag `positive-example` only for an explicit worked example, a template of the desired output, a labeled good case, or a demonstration.

Do **not** tag:
- Numbered workflow commands that only tell the agent what to run.
- Pointers to external "examples" pages (those are `reference`).
- Unlabeled API snippets that specify a step rather than demonstrate a good result.

A `negative-example` must demonstrate an undesirable case. Containing the words "do not" is not enough.

### 8. References (`reference`)

Points to external or internal documentation, referenced files, web URLs, reference tables, or supplemental background material that provides context or supporting detail.

Examples:
- "Refer to `docs/architecture.md` for complete system details."
- "See https://example.com/api-spec for full API specifications."
- "Consult the attached schema reference table for field definitions."

## SDLC Stages (9)

We also code each skill against stages of the Software Development Life Cycle (SDLC). The stages cover the whole SDLC, with some tasks and categories subdivided further.

### 1. Software Documentation (`documentation`)

Creating, modifying, or maintaining project documentation, both human-readable and agent-facing. This may include documenting ongoing code and tests, or larger files such as `.md` or `.txt` files.

Examples:
- Create or update the project README and system architecture guides
- Write inline code comments
- Configure `CLAUDE.md` or `AGENTS.md`

### 2. Software Requirements and Planning (`requirement`)

Defining system specifications, gathering requirements, project planning, and task breakdown.

Examples:
- Drafting user stories and acceptance criteria for a new feature
- Planning sprint backlogs and release milestones
- Extracting functional requirements from stakeholder notes
- Creating and writing tickets

### 3. Software Design (`design`)

Structuring and architecting systems, defining component boundaries, designing interfaces or schemas, and establishing architectural patterns.

Examples:
- Designing RESTful API endpoints and JSON request/response schemas
- Designing database schemas
- Establishing a microservices architecture layout
- Selecting design patterns

### 4. Code Implementation (`code-implementation`)

Generating, implementing, or modifying primary source code across core modules, functions, or classes. This may include connecting to external APIs, third-party services, SDKs, libraries, or authentication mechanisms.

Examples:
- Implementing a helper function for string manipulation

### 5. Program Analysis (`program-analysis`)

Inspecting, parsing, reverse engineering, or understanding existing codebases and execution logic.

Examples:
- Analyzing repository structure to map system dependencies
- Tracing data flow across components to identify bottlenecks
- Decompiling or reverse engineering components

### 6. Testing (`testing`)

Creating, modifying, configuring, executing, or evaluating software tests and test suites, including unit, integration, end-to-end, regression, and other automated testing.

Tag `testing` only when the skill contains an explicit test procedure: generating tests, running a named test command, configuring a test framework, or evaluating coverage as a required step.

Do **not** tag `testing` for:
- Optional "test later if asked" notes
- Reviewing whether someone else's PR has tests
- Mentioning tests only as background

Examples:
- Generating unit tests with pytest for a scoring module
- Writing integration tests for database persistence layers
- Checking that coverage stays above 80%
- Running pytest after modifying the implementation
- Running the integration test suite before committing
- Configuring an end-to-end testing framework

### 7. Software Maintenance and Quality (`maintenance`)

Improving, modernizing, reviewing, or maintaining an existing codebase, where the main goal is neither new functionality nor diagnosing a specific observed defect. This may include static analysis, linting, dependency updates, tech-debt remediation, code modernization, dead-code removal, maintainability improvements, and optimization.

Tag `maintenance` when the skill's job is upgrading, migrating, refactoring, linting, or reviewing the quality of existing code. Do **not** tag it for a security or access audit, a convention like "reuse this prop type," or instructions that only upgrade the skill itself.

Examples:
- Running ESLint and fixing style-rule violations (linting)
- Consolidating duplicate methods into reusable helper utilities (refactoring)
- Migrating Tailwind utilities to StyleX as a behavior-preserving refactor
- Reviewing a pull request for adherence to clean-code standards (code review)

### 8. Debugging (`debugging`)

Identifying, isolating, diagnosing, and fixing runtime errors, bugs, or unexpected system behavior.

Examples:
- Investigating a null pointer exception in the order-processing pipeline
- Analyzing stack traces to locate memory leaks
- Fixing edge-case failure conditions in payment handling

### 9. Software Deployment and Infrastructure (`devops`)

CI/CD pipelines, infrastructure as code (IaC), containerization, configuration, and version-control workflows.

Tag `devops` only when the skill's job is deployment, CI/CD, containers, or infrastructure. Do **not** tag it just because the agent uses `gh` to open a PR, post a review, or draft release notes, or because the product being extended is a deployment platform.

Examples:
- Writing Dockerfiles and docker-compose deployment configurations
- Setting up GitHub Actions workflows for CI
- Managing Git branch operations and writing standardized commit messages

## Filter Out (1)

We only want SDLC-oriented skills written in English. Apply a filter-out tag in either case below. Use it on its own; do not combine it with instruction-type or SDLC tags.

1. **Agent-Internal Skill (`agent-skill`):** The skill is about the agent itself, or covers functionality outside software engineering.
2. **Wrong Language (`wrong-language`):** The content is not in English, or it targets an out-of-scope programming language. Skills are scraped based on each repository's dominant programming language, so some target a different language; tag those `wrong-language`.
