---
description: Turn a repeatedly-violated CLAUDE.md rule into a PreToolUse hook that enforces it
argument-hint: <the rule to mechanise>
---

# /mechanize

Convert `$ARGUMENTS` from a prose rule into a hook that makes the failure
impossible, then delete the prose.

## Before writing anything, decide the shape

Not every rule should block. Pick one:

| Shape | Use when | Example |
|---|---|---|
| **Auto-fix** | The correct rewrite is provable and safe | strip a `cd` into the directory you are already in |
| **Block** | There is a right way and the model must choose it | long heredoc → write a script instead |
| **Warn** | You want the signal without stopping work | flag a slow pattern |

**Prefer auto-fix.** Blocking costs a full round trip every time it fires and
teaches nothing durable — a habit that gets blocked 70 times in a week is still
there in week two. Only block when you cannot compute the fix safely.

## Write the hook

1. Create `~/.claude/hooks/pretool-<name>.py`, executable, Python 3, no
   dependencies.
2. Read the JSON payload from stdin. Return early — `exit 0`, no output — on
   anything you do not handle. **A hook that crashes on unexpected input breaks
   the tool it guards**, so wrap the JSON parse and bail silently on failure.
3. Gate on `payload["tool_name"]` first, then on the pattern.
4. Emit the right JSON:

```python
# block
print(json.dumps({"decision": "block", "reason": "..."}))

# auto-fix (note: no permissionDecision — the rewritten call must still go
# through the normal permission flow, or you have built a permission bypass)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "updatedInput": updated_input,
    "additionalContext": "what was changed and what to do next time",
}}))
```

5. **Write the reason message for the reader, not the logs.** It is the only
   thing the model sees. State what was blocked, why in one clause, and the
   exact sanctioned alternative. A reason that just says "not allowed" produces
   a retry of the same shape.

6. Add a bypass (`# <name>: allow`) if false positives are plausible. A guard
   with no exit gets deleted the first time it is wrong.

## Test it

Before wiring it up:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"<the bad pattern>"}}' \
  | python3 ~/.claude/hooks/pretool-<name>.py
```

Then the same with a *good* command and confirm it stays silent. **Test the
false-positive case as carefully as the true-positive one** — a guard that fires
on legitimate work is worse than no guard, because it trains everyone to reach
for the bypass reflexively.

## Wire it up

Add to `PreToolUse` in `~/.claude/settings.json` under the right matcher.
Restart Claude Code; hooks load at session start.

## Finish the job

**Delete the prose rule from `CLAUDE.md`.** This is the step people skip. The
rule is now enforced by code, so leaving the sentence in place costs attention
budget and buys nothing. Note in the hook's docstring what it replaced and what
the violation rate was before — future-you will want to know whether it worked.

Re-run `/audit-session` in a week and confirm the count actually went to zero.
If it did not, the hook has a gap — fix the hook, do not re-add the paragraph.
