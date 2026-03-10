---
name: kubit-eliciting-spec
description: Use when discussing, expanding, or designing any subsystem in SPEC.md. Use when user asks about goals, API shape, edge cases, or configuration for HTTP, Router, ORM, Queue, Mail, Views, or other framework subsystems.
---

# Eliciting Spec for Kubit Subsystems

## Overview

Extract detailed requirements through structured questions, then capture decisions in SPEC.md with the standard template.

## When to Use

- User mentions expanding a subsystem (Router, ORM, Queue, Mail, etc.)
- Discussing goals, non-goals, or API shape for any feature
- Need to resolve open questions in SPEC.md
- Designing new framework capability

## General Prompts (Ask Per Subsystem)

| Area | Questions to Ask |
|------|------------------|
| Scope | Goals vs non-goals? What's MVP vs later? |
| Data | Inputs/outputs? Data shapes? |
| Flow | Step-by-step lifecycle? Extension points? |
| Config | Knobs, defaults, override mechanisms? |
| Errors | Failure modes? Error types? How surfaced? |
| Edge Cases | Tricky scenarios to support or reject? |
| Security | AuthN/Z, CSRF, CORS, secrets, privacy? |
| Performance | Latency, streaming, caching, batching? |
| Extensibility | Hooks, interfaces, adapters, plugins? |
| Testing | What tests prove it? Fixtures needed? |
| Open Questions | Undecided items → add to SPEC |

## Subsystem Deep-Dive Prompts

**HTTP Kernel:** Request/response abstraction (Node vs Web)? Streaming? Middleware pipeline order? Error handling policy? Static vs app route precedence? 404/405/500 behavior?

**Router:** Path syntax, params, constraints? Trailing slash, case sensitivity? Named routes, reverse routing? Route groups, per-route middleware? Controller action resolution?

**Controllers & DI:** Construction via DI or factories? Access to request/config? Return types (text, JSON, redirects, view(), streams)? Validation strategy?

**Views & Inertia:** Envelope shape `{ component, props, url, version }`? Layouts? Hydration and bundle splitting? Asset manifest? Client runtime duties? Forms/links enhancement?

**ORM/DB:** Table builder DSL surface? Migration runner (tracking table, up/down, transactions)? Seeding?

**Queue/Jobs:** Dispatch API? Queue names, retries/backoff? Idempotency, scheduling? Worker lifecycle, graceful shutdown?

**Mail:** Rendering API? Transport abstraction? Attachments? Preview/dev mailbox? Test fakes?

**CLI:** Commands, flags? Config discovery? Watch mode? Error UX?

## Subsystem Spec Template

When documenting in SPEC.md, use this structure:

```markdown
## [Subsystem Name]

### Goals
### Non-Goals
### Concepts & Vocabulary
### API Surface (TypeScript)
### Configuration
### Lifecycle & Control Flow
### Edge Cases & Errors
### Security & Privacy
### Performance & Scaling
### Extensibility & Integration Points
### Testing Strategy & Fixtures
### Open Questions
### Alternatives Considered
```

## Capturing Decisions

When a decision is made, add to SPEC.md Decision Log:

```markdown
## Decision Log

### YYYY-MM-DD: [Decision Title]
**Context:** [What prompted this]
**Decision:** [What was decided]
**Rationale:** [Why]
**Alternatives rejected:** [What else was considered]
```
