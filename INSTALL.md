# Install

About five minutes. Every hook is independent — take one, take all four.

## 1. Copy the hooks

```bash
mkdir -p ~/.claude/hooks
cp hooks/*.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.py
```

They need Python 3 and nothing else. No pip installs, no dependencies.

## 2. Wire them up

Open `~/.claude/settings.json` and merge the `hooks` block from
`settings.json.example` into it. If you already have a `PreToolUse` array, add
these entries to it rather than replacing it.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 ~/.claude/hooks/pretool-heredoc-guard.py" },
          { "type": "command", "command": "python3 ~/.claude/hooks/pretool-cd-guard.py" },
          { "type": "command", "command": "python3 ~/.claude/hooks/pretool-polling-guard.py" }
        ]
      },
      {
        "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit",
        "hooks": [
          { "type": "command", "command": "python3 ~/.claude/hooks/pretool-secret-guard.py" }
        ]
      }
    ]
  }
}
```

Note the second matcher. The secret guard covers **file writes as well as
commands** — a key written into a file is exactly as leaked as one echoed to a
terminal, and that was the gap in my first version of it.

## 3. Restart

Hooks load at session start. Restart Claude Code; an already-running session
will not pick them up.

## 4. Check it works

```
Run this: cat <<'EOF' > /tmp/x.txt
line 1
… (paste 20 more lines)
EOF
```

The heredoc guard should block it and tell the agent to write a script instead.
If nothing happens, the wiring didn't take — check `settings.json` parses as
valid JSON.

---

## Bypasses

Two hooks have deliberate escape hatches, because a guard with no exit turns
into a guard people delete:

| Hook | Bypass |
|---|---|
| `pretool-polling-guard.py` | append `# polling-guard: allow` to the command |
| `pretool-secret-guard.py` | append `# secret-guard: allow` (Bash only — file writes have no bypass, on purpose) |

The heredoc and cd guards have none. Neither has ever needed one.

---

## Tuning

- **Heredoc limit.** `MAX_BODY_LINES = 15` near the top. 15 is where I landed;
  it is strict enough to force scratch files without blocking a small `cat >`.
- **Secret patterns.** `KEY_PATTERNS` is a plain list of `(name, regex)` tuples.
  Add your own vendor prefixes — that is the file you will most want to edit.
- **Polling.** If you use a different long-running CLI, the third pattern
  (`PGREP_CODEX_RE`) is worth renaming to match it.

## Uninstall

Delete the `hooks` entries from `settings.json`. The `.py` files are inert on
their own.
