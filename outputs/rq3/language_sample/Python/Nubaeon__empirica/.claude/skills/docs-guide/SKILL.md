---
name: docs-guide
description: Interactive documentation guide - helps users explore and understand project documentation. Use when user asks about features, APIs, configuration, or wants to learn how something works. Retrieves focused docs and guides through them interactively.
allowed-tools: Bash(empirica docs-explain:*),Bash(python -m docpistemic.cli explain:*),Read,Glob,Grep
---

# Interactive Documentation Guide

## Overview

This skill helps users explore project documentation interactively. It retrieves relevant documentation sections and guides users through understanding them, with follow-up suggestions.

## When to Use

- User asks "how do I...?" or "what is...?"
- User wants to understand a feature, API, or concept
- User is exploring the codebase and needs guidance
- User asks about configuration, installation, or usage

## Workflow

### 1. Understand the Query

First, identify:
- **Topic**: General subject area (auth, api, config, install, etc.)
- **Question**: Specific question if provided
- **Audience**: developer, user, or ai-agent context

### 2. Retrieve Documentation

For Empirica project:
```bash
empirica docs-explain --topic "<topic>" --output json
# or
empirica docs-explain --question "<question>" --output json
```

For external projects (using docpistemic):
```bash
python -m docpistemic.cli explain /path/to/project --topic "<topic>" --output json
```

### 3. Present Results Interactively

After retrieving docs, guide the user:

1. **Summarize** - Brief overview of what was found
2. **Key Points** - Extract the most relevant 2-3 points
3. **Code Examples** - Show relevant code snippets if available
4. **Related Topics** - Suggest follow-up areas to explore
5. **Ask** - Check if they want more detail on any aspect

### 4. Follow-up Guidance

Based on the retrieved `related_topics`, offer to:
- Dive deeper into a specific section
- Show related commands or APIs
- Explain concepts mentioned in the docs
- Find code examples in the actual codebase

## Example Interaction

User: "How do sessions work in Empirica?"

Response pattern:
1. Run: `empirica docs-explain --topic "sessions" --output json`
2. Present: "Sessions in Empirica track AI agent work context..."
3. Key points from docs
4. Relevant CLI commands mentioned
5. "Would you like me to explain session-create, or show how sessions relate to goals?"

## Topic Aliases

Common topics map to multiple keywords:
- **auth** → authentication, login, oauth, jwt, token
- **api** → endpoints, routes, rest, graphql
- **config** → configuration, settings, environment
- **install** → installation, setup, quickstart
- **test** → testing, pytest, coverage
- **session** → sessions, context, bootstrap

## Interactive Patterns

### For "How do I...?" questions
1. Search for the action/verb in question
2. Find relevant command or API
3. Show usage example
4. Offer to show more examples or related commands

### For "What is...?" questions
1. Search for concept definition
2. Explain in context of the project
3. Show where it's used
4. Suggest related concepts

### For troubleshooting
1. Search for error or symptom
2. Find relevant documentation
3. Suggest diagnostic commands
4. Offer to search codebase if docs don't help

## Output Format

When presenting results, use clear structure:

```
## [Topic/Question]

**Summary:** Brief overview of what was found

**Key Points:**
- Point 1 with source reference
- Point 2 with source reference

**Relevant Commands:**
- `command` - description

**See Also:** [related topics]

**Want to explore:** [specific follow-ups]?
```

## Notes

- Always cite source files from the docs
- If docs are sparse, offer to search codebase directly
- Suggest running commands with `--help` for detailed usage
- For complex topics, break into multiple exchanges
