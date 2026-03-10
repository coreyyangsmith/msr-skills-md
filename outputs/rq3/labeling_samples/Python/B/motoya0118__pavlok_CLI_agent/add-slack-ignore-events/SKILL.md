---
name: add-slack-ignore-events
description: Insert a Slack ignore event and update daily punishments using scripts/add_slack_ignore_events.py. Use when a Slack message was ignored and you need to record it.
---

# Slack Ignore Events

Use `scripts/add_slack_ignore_events.py` to insert a Slack ignore event and update `daily_punishments`.

## Run

```bash
uv run scripts/add_slack_ignore_events.py 1700000000.000000
```

```bash
uv run scripts/add_slack_ignore_events.py 1700000000.000000 --detected-at "2026-01-26 08:15"
```

## Inputs

- `slack_message_ts` is required and must be unique.
- `--detected-at` is optional; accepted formats are `YYYY-MM-DD HH:MM`, `YYYY-MM-DDTHH:MM`, or `YYYYMMDDHHMM`.

## Outputs

Prints a single line of JSON:

```
{"remaining_total": 3}
```

## Notes

- Database URL comes from `DATABASE_URL` (default: `sqlite:///./app.db`).
- If a pending/failed `daily_punishments` row exists, its `ignore_count` and `punishment_count` are incremented; otherwise a new pending row is created.
