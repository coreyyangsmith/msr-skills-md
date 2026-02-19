---
name: test-driven-development
description: use during regular development workflow when generating new code or modifying feature behavior.
---
## Description
Implement changes using a strict Test-Driven Development loop: write or update a failing automated test that captures the desired behavior, implement the smallest change to make it pass, then refactor while keeping the test suite green.

This skill is designed for AI coding agents and developers working in existing codebases where correctness, regression prevention, and maintainability matter.

---

## When to use this skill
Use this skill when you are:
- Adding a feature, fixing a bug, or changing behavior in a codebase with an automated test framework.
- Working in a system where regressions are costly or difficult to detect manually.
- Refactoring logic that has edge cases or complex branching.
- Developing libraries, APIs, parsers, data pipelines, or any function with clear inputs and outputs.

Do not use this skill as the only approach for:
- Pure exploratory spikes where requirements are unknown.
- UI-only styling changes with no behavioral outcome.
- One-off throwaway scripts where tests would exceed the value of the script.

---

## Inputs

### Required
1. **Change intent**
   - What behavior should exist after the change (feature/bugfix/refactor goal).

2. **Test harness**
   - Existing test runner and framework, or a plan to introduce a minimal one.

3. **Execution method**
   - How tests are run locally or in CI (command, environment, containers, etc.).

### Optional configuration
- `test_scope`: default `unit`
  - `unit | integration | e2e`
- `coverage_target`: default `0` (no explicit requirement)
- `allow_new_dependency`: default `false`
- `max_test_runtime_seconds`: default `60`
- `use_golden_files`: default `false`
- `use_property_tests`: default `false`
- `seed_reproducibility`: default `true`
- `flaky_test_policy`: default `fail_fast`

---

## Outputs

### Code outputs
- One or more new or updated test files.
- Minimal production code changes that make tests pass.
- Optional refactor commits that improve clarity without changing behavior.

### Evidence outputs
- A record of executed test commands.
- Before/after test results (fail then pass).
- Notes on any risk areas or deferred improvements.

---

## Core principles

### 1) Tests are the contract
- Tests define behavior at a level users and maintainers care about.
- Prefer testing public interfaces over internal details.
- If behavior is unclear, encode the clarified behavior in tests.

### 2) Red, Green, Refactor is mandatory
- **Red:** Add a failing test that demonstrates the gap.
- **Green:** Implement the smallest change to pass.
- **Refactor:** Improve structure while keeping all tests passing.

Skipping steps is allowed only if the codebase has no viable automated test harness and you must first create a minimal harness.

### 3) Make failures diagnostic
- A failing test should clearly indicate what is wrong.
- Use explicit assertions and readable fixture setup.
- Prefer targeted checks over broad snapshot dumps.

### 4) Keep tests deterministic
- No reliance on wall clock time, random seeds without control, external network, or nondeterministic ordering.
- Use stable seeds when randomness is required.
- Use hermetic fakes or local test doubles for external services.

---

## Workflow

### Step 0: Triage the change
1. Identify whether this is:
   - bugfix (existing behavior wrong),
   - feature (new behavior),
   - refactor (same behavior, improved structure).
2. Locate the closest existing tests for the affected behavior.
3. Confirm how to run tests in this repo.

### Step 1: Reproduce (for bugfixes)
1. Write a test that reproduces the bug using the smallest possible input.
2. Confirm it fails for the right reason.
3. Avoid testing the bug via indirect side effects when a direct assertion is possible.

### Step 2: Write the failing test (Red)
Rules for the test:
- Minimal setup and minimal input.
- Only one conceptual reason to fail.
- Assertion reflects the desired behavior.

Preferred test location order:
1. Existing test module closest to the code under test.
2. New test file in the same test suite category.

### Step 3: Make it pass (Green)
Rules for implementation:
- Make the smallest change that satisfies the test.
- Avoid premature refactors, optimizations, or API redesign.
- If you must change behavior broadly, add tests to lock down the expected behavior.

### Step 4: Refactor safely (Refactor)
Refactor goals:
- Remove duplication.
- Improve naming and readability.
- Extract helpers for repeated test setup.
- Simplify branching and reduce cyclomatic complexity.

Refactor rules:
- No behavioral changes without new tests.
- Keep tests green at all times.

### Step 5: Expand coverage for edge cases
Add tests for:
- Boundary values.
- Error handling paths.
- Null/empty inputs.
- Input normalization.
- Performance-sensitive cases (only if cheap and stable).

### Step 6: Confirm integration and CI expectations
- Run the full targeted suite (unit plus relevant integration).
- Confirm new tests do not require special local state.
- If CI exists, ensure your changes match CI commands and environment.

---

## Test design guidelines

### Unit tests
Use when:
- Pure functions or local logic.
- Minimal dependencies.
- You want fast, isolated feedback.

Guidelines:
- Mock at boundaries, not internals.
- Prefer dependency injection over patching globals.
- Assert on outputs and observable effects.

### Integration tests
Use when:
- Validating wiring between components.
- Data serialization, database queries, message passing.

Guidelines:
- Use ephemeral local resources (sqlite, temp dirs, containers) when possible.
- Keep them fewer, slower, and more scenario-driven.

### End-to-end tests
Use when:
- Validating critical user flows.
- Confirming deployment-like behavior.

Guidelines:
- Keep very small count.
- Ensure stable, deterministic environment.
- Fail with clear logs and artifacts.

---

## Determinism and flake prevention

### Prohibited in tests unless explicitly controlled
- Real network calls.
- Sleeping to wait for state.
- Using current date/time without freezing.
- Relying on filesystem ordering.
- Unseeded randomness.

### Required practices
- Freeze time when asserting on timestamps.
- Seed randomness and surface seed in failure output.
- Use temp directories and clean up.
- Use retry only for known eventual consistency scenarios, and keep retries bounded.

---

## Assertions and readability

### Preferred assertions
- Exact equality for computed results.
- Structured comparisons (dicts, objects) with helpful diffs.
- Explicit exception type and message checks for error paths.

### Avoid
- Overly broad snapshots for complex structures unless they are stable and intentional.
- Assertions that depend on formatting or unrelated ordering unless ordering is the behavior.

---

## Operational constraints and guardrails

### Read-only external systems by default
- Tests should not mutate shared dev environments.
- Avoid writing outside test temp directories.
- Avoid destructive database operations on developer machines.

### Performance
- Keep unit tests fast and parallelizable.
- Enforce `max_test_runtime_seconds` when possible.
- For expensive tests, mark them and exclude from default runs.

### Dependency policy
- Do not add new test dependencies unless allowed by configuration.
- Prefer built-in testing utilities and existing repo tooling.

---

## Error handling rules

### If tests cannot run
- Identify the minimal steps to make them runnable.
- Add a smoke test to confirm the harness works.
- Document required environment variables or services as part of the test setup.

### If an existing test is failing unexpectedly
- Determine whether it is a real regression or a pre-existing failure.
- If pre-existing, isolate your change by running a focused subset and record baseline failures.
- Do not silently update expected outputs without understanding the reason.

### If a test is flaky
- Treat flakiness as a bug.
- Identify nondeterminism source and remove it.
- If unavoidable (rare), quarantine with clear marking and a follow-up task note.

---

## Suggested default configuration
- `test_scope = "unit"`
- `allow_new_dependency = false`
- `max_test_runtime_seconds = 60`
- `seed_reproducibility = true`
- `flaky_test_policy = "fail_fast"`
- Prefer: Tiered testing (unit first, then integration for wiring, e2e for critical flows).

---

## Definition of done
- A new or updated test exists that would fail on the previous version and passes on the new version.
- The smallest necessary production change was made to pass tests.
- Refactors, if any, are behavior-preserving and covered by tests.
- Relevant test suites run locally (or in the defined execution method) with passing results.
- New tests are deterministic, readable, and aligned with public behavior.

---

## Notes for downstream processing
This skill pairs well with:
- Continuous Integration checks (run tests on every change).
- Code review gates that require tests for behavior changes.
- Mutation testing or coverage checks for critical modules.

Downstream automation should treat test output and logs as potentially sensitive and avoid storing secrets or environment variables.
