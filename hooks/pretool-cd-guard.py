#!/usr/bin/env python3
"""PreToolUse hook (Bash): strip a leading `cd <abspath>` that targets the
directory the shell is ALREADY in.

The Bash tool's cwd resets to the SESSION working directory before every call,
so `cd /abs/path/that/is/the/session/cwd && ...` is pure boilerplate. Audit
(7 days): 68% of all leading-cd commands cd into the session's own cwd, +9%
into a subdir of it -> ~77% of cd boilerplate is avoidable. Native Read/Grep/
Glob and `git -C <path>` need no cd at all.

Behaviour (changed 2026-07-16 from block -> auto-strip): when the command begins
with `cd <abspath>` and <abspath> equals the session cwd (case-insensitive, for
APFS) — a guaranteed no-op — the hook REWRITES the command with that prefix
removed and lets it run, instead of rejecting the call and making the model
re-issue it. Blocking cost a full round-trip per occurrence and taught nothing
durable: it fired 71 times in the week to 2026-07-16 and the habit did not
decay. Stripping is semantics-preserving precisely because the cd is a no-op:
`cd <cwd> && cmd` cannot fail at the cd, so dropping it cannot strand `cmd`.

Subdir cd's (`cd <cwd>/apps/frontend`) and genuine navigation (`cd /tmp`,
`cd <other-repo>`) are left untouched, so it can never break a real command.

Deliberately emits `updatedInput` with NO `permissionDecision`: the rewritten
command must still go through the normal permission flow (allowlist / prompt)
and the sibling Bash guards. Returning "allow" here would auto-approve anything
that happened to carry a redundant cd prefix — e.g. `cd <cwd> && rm -rf ...` —
which would turn a formatting nit into a permission bypass.
"""

import json
import os
import re
import sys

LEADING_CD_RE = re.compile(r"^\s*cd\s+(/[^\s;&|]+)\s*(?:;|&&|\n|$)")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") or ""
    m = LEADING_CD_RE.match(command)
    if not m:
        return 0
    target = m.group(1).rstrip("/")
    cwd = (payload.get("cwd") or os.getcwd()).rstrip("/")
    # Case-insensitive (macOS APFS) exact match only — never a descendant.
    if target.lower() != cwd.lower():
        return 0

    remainder = command[m.end():].strip()
    if not remainder:
        # Bare `cd <cwd>` with nothing after it: there is no command left to
        # rewrite into, so there is nothing to run. Keep rejecting this one.
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"`cd {target}` is a no-op — the Bash tool already starts every call "
                f"in this directory ({cwd}), and there is no other command here to run."
            ),
        }))
        return 0

    updated_input = dict(tool_input)
    updated_input["command"] = remainder
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": updated_input,
            "additionalContext": (
                f"cd-guard stripped a redundant leading `cd {target}` (already the "
                "session cwd) and ran the rest. Skip that prefix next time; for paths "
                "elsewhere use absolute paths, Read/Grep/Glob, or `git -C <path> ...`."
            ),
        },
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
