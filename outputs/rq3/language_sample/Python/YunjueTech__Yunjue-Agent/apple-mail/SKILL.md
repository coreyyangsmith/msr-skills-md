---
name: apple-mail
description: Apple Mail.app integration for macOS. Read inbox, search emails, send emails, reply, and manage messages with fast direct access (no enumeration).
metadata: {"clawdbot":{"emoji":"📧","os":["darwin"],"requires":{"bins":["sqlite3"]}}}
---

# Apple Mail

Interact with Mail.app via AppleScript and SQLite.

## Commands

| Command | Usage |
|---------|-------|
| **Refresh** | `mail-refresh [account] [wait_seconds]` |
| List recent | `mail-list [mailbox] [account] [limit]` |
| Search | `mail-search "query" [mailbox] [limit]` |
| Fast search | `mail-fast-search "query" [limit]` |
| Read email | `mail-read <message-id> [message-id...]` |
| Delete | `mail-delete <message-id> [message-id...]` |
| Mark read | `mail-mark-read <message-id> [message-id...]` |
| Mark unread | `mail-mark-unread <message-id> [message-id...]` |
| Send | `mail-send "to@email.com" "Subject" "Body" [from-account] [attachment]` ¹ |
| Reply | `mail-reply <message-id> "body" [reply-all]` |
| List accounts | `mail-accounts` |
| List mailboxes | `mail-mailboxes [account]` |

## Refreshing Mail

Force Mail.app to check for new messages:

```bash
mail-refresh                    # All accounts, wait up to 10s
mail-refresh Google             # Specific account only
mail-refresh "" 5               # All accounts, max 5 seconds
mail-refresh Google 0           # Google account, no wait
```

**Smart sync detection:**
- Script monitors database message count
- Returns early when sync completes (no changes for 2s)
- Reports new message count: `Sync complete in 2s (+3 messages)`

**Notes:**
- Mail.app must be running (script will error if not)
- `mail-list` does NOT auto-refresh — call `mail-refresh` first if you need fresh data

## Output Format

List/search returns: `ID | ReadStatus | Date | Sender | Subject`
- `●` = unread, blank = read

## Gmail Mailboxes

⚠️ Gmail special folders need `[Gmail]/` prefix:

| Shows as | Use |
|----------|-----|
| `Spam` | `[Gmail]/Spam` |
| `Sent Mail` | `[Gmail]/Sent Mail` |
| `All Mail` | `[Gmail]/All Mail` |
| `Trash` | `[Gmail]/Trash` |

Custom labels work without prefix.

## Fast Search (SQLite)

✨ **Now safe even if Mail.app is running** — copies database to temp file first.

```bash
mail-fast-search "query" [limit]  # ~50ms vs minutes
```

Previously required Mail.app to be quit. Now works anytime by copying the database to a temp file before querying.

## Performance Notes

**Speed by operation:**
| Operation | Speed | Notes |
|-----------|-------|-------|
| `mail-fast-search` | ~50ms | SQLite query, fastest |
| `mail-accounts` | <1s | Simple AppleScript |
| `mail-list` | 1-3s | AppleScript, direct mailbox access |
| `mail-send` | 1-2s | Creates and sends message |
| `mail-read` | ~2s | Position-optimized lookup |
| `mail-delete` | ~0.5s | Position-optimized lookup |
| `mail-mark-*` | ~1.5s | Position-optimized lookup |

**Optimization technique:**
SQLite provides account UUID and approximate message position. AppleScript jumps directly to that position instead of iterating from the start.

**Batch operations supported:**
- `mail-read 123 456 789` - Read multiple (separator between each)
- `mail-delete 123 456 789` - Delete multiple
- `mail-mark-read 123 456` - Mark multiple as read
- `mail-mark-unread 123 456` - Mark multiple as unread

**⚠️ No auto-refresh:** Scripts read cached data. Call `mail-refresh` first if you need latest emails.

## Managing Emails

**Delete emails:**
```bash
mail-delete 12345                    # Delete one
mail-delete 12345 12346 12347        # Delete multiple
```

**Mark as read/unread:**
```bash
mail-mark-read 12345 12346           # Mark as read
mail-mark-unread 12345               # Mark as unread
```

**Bulk operations example:**
```bash
# Find spam emails
mail-fast-search "spam" 50 > spam.txt

# Extract IDs and delete them
grep "^[0-9]" spam.txt | cut -d'|' -f1 | xargs mail-delete
```

## Reading Email Bodies

```bash
mail-read 12345              # Single email
mail-read 12345 12346 12347  # Multiple emails (separated output)
```

Uses position-optimized lookup (~2s per message). Multiple emails are separated by `========` with a summary at the end.

## Errors

| Error | Cause |
|-------|-------|
| `Mail.app is not running` | Open Mail.app before running scripts |
| `Account not found` | Invalid account — check mail-accounts |
| `Message not found` | Invalid/deleted ID — get fresh from mail-list |
| `Can't get mailbox` | Invalid name — check mail-mailboxes |
| `Mail database not found` | SQLite DB missing — check ~/Library/Mail/V{9,10,11}/MailData/ |

## Technical Details

**Database:** `~/Library/Mail/V{9,10,11}/MailData/Envelope Index`

**Message lookup method (optimized):**
1. Query SQLite for account UUID, mailbox path, and approximate position
2. AppleScript accesses the specific account directly (no iteration)
3. Search starts at the approximate position (±5 messages buffer)
4. Falls back to full mailbox search only if position hint fails

**Safety:**
- Fast search copies database to temp file before querying
- Safe to use even if Mail.app is running
- Delete/read/mark operations query live database but access is minimal

## Notes

- Message IDs are internal, get fresh ones from list/search
- Confirm recipient before sending
- AppleScript search is slow but comprehensive; SQLite is fast for metadata
- Delete/mark operations support bulk actions (pass multiple IDs)
- Always refresh before listing if you need the absolute latest emails

¹ **Known limitation:** Mail.app adds a leading blank line to sent emails. This is an AppleScript/Mail.app behavior that cannot be bypassed.