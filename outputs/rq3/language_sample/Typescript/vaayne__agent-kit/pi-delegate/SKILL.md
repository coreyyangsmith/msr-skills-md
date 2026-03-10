---
name: pi-delegate
description: Use Pi as a non-interactive subagent for delegated tasks. Best when fresh context, model specialization, or isolated task execution is useful.
---

# Pi Delegate

Use Pi as a separate non-interactive subagent when you want fresh context, a different model, or isolated task execution.

## Use this skill when

- you want to delegate a bounded task to Pi
- you want a different model for the task
- you want an independent second pass or critique
- you want to isolate noisy work from the current conversation

## Command rules

- Change to the target working directory first.
- Always add: `--offline --no-prompt-templates --no-themes`
- Choose a model with: `--model {model}` when model choice matters.
- Use `-c` or `--continue` when repeating the same delegated task.
- Use `pi --help` if exact flags are unclear.

Pattern:

```bash
cd /path/to/project && pi --offline --no-prompt-templates --no-themes [--model {model}] [-c] -p "Your task"
```

## Models

Most capable:

- `cx/gpt-5.4`
- `cc/gemini-3-pro-preview`
- `cc/claude-opus-4-6`

Balanced:

- `cc/claude-sonnet-4-6`

Cheap and fast:

- `cc/claude-haiku-4-5`
- `cc/gemini-3-flash-preview`
- `cx/gpt-5.3-codex-spark`

## Examples

```bash
cd /path/to/project && pi --offline --no-prompt-templates --no-themes -p "Review this proposal and give me the top risks and recommended changes"

cd /path/to/project && pi --offline --no-prompt-templates --no-themes --model cc/claude-sonnet-4-6 -p "Think through this decision and recommend the best option"

cd /path/to/project && pi --offline --no-prompt-templates --no-themes --model cc/claude-opus-4-6 -p "Give me a second opinion on this plan"

cd /path/to/project && pi --offline --no-prompt-templates --no-themes -c -p "Continue the previous task and refine the recommendation"
```

## Prompt guidance

Keep prompts direct. Ask Pi for the output you want back, such as:

- findings
- risks
- options
- recommendation
- next actions
