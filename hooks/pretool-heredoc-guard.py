#!/usr/bin/env python3
"""PreToolUse hook (Bash): block inline heredocs with bodies longer than 15 lines.

Long heredocs are brittle (quoting), hide syntax errors, and re-invent scratch
scripts. The sanctioned pattern: Write the script to /tmp/<task>.<ext> (or
scripts/<task>.<ext>) with the Write tool and invoke it with a one-line command.

Mechanized 2026-06-10 — the prose ban (the prose rule in CLAUDE.md) was the
most-violated rule in a month of nightly reviews (150 violations in one day).
"""

import json
import re
import sys

MAX_BODY_LINES = 15

HEREDOC_START_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def heredoc_body_lines(command: str):
    """Yield (delimiter, body_line_count) for each heredoc in the command."""
    lines = command.split("\n")
    line_index = 0
    while line_index < len(lines):
        match = HEREDOC_START_RE.search(lines[line_index])
        # Skip here-strings (<<<) which the regex could partially match.
        if match and "<<<" not in lines[line_index][max(0, match.start() - 1): match.end() + 1]:
            delimiter = match.group(2)
            body_count = 0
            scan_index = line_index + 1
            while scan_index < len(lines):
                if lines[scan_index].strip() == delimiter or lines[scan_index].lstrip("\t") == delimiter:
                    break
                body_count += 1
                scan_index += 1
            yield delimiter, body_count
            line_index = scan_index + 1
        else:
            line_index += 1


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    if "<<" not in command:
        return 0

    for delimiter, body_count in heredoc_body_lines(command):
        if body_count > MAX_BODY_LINES:
            print(json.dumps({
                "decision": "block",
                "reason": (
                    f"Blocked: inline heredoc (<<{delimiter}) has {body_count} body lines "
                    f"(max {MAX_BODY_LINES}). Write the script to /tmp/<task>.<ext> with the "
                    "Write tool and run it with a one-line command instead — long heredocs "
                    "break on quoting (especially Python f-strings) and hide syntax errors."
                ),
            }))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
