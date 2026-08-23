#!/usr/bin/env python3
"""PreToolUse hook (Bash): block FOREGROUND polling patterns.

The 2026-07-04 weekly audit found 689 poll/sleep-pattern Bash calls in 7 days:
hand-rolled `until grep -q "CODEX_EXIT=" …; do sleep 5; done` foreground loops,
`sleep N; tail <log>` peeks, and 33x `pgrep -f "codex exec review"` probes —
each one burns a turn and the CLAUDE.md rule against them wasn't sticking.

Blocked (ONLY when the call is NOT run_in_background):
  1. until/while loops whose body sleeps  -> poll loop burning turns
  2. `sleep N ; cat|tail|head|grep …`     -> peek-at-log-while-it-grows
  3. foreground pgrep probes for codex    -> "is the review done yet?"

Sanctioned alternatives (what the block message says):
  - Wrap the wait in ONE Bash call with run_in_background=true whose loop EXITS
    when done (e.g. `until grep -q "Ready in" /abs/log; do sleep 1; done`) —
    the completion notification wakes the agent once. Background calls are
    exempt from this hook for exactly that reason.
  - Codex reviews run in the FOREGROUND and block to completion:
    `script -q /tmp/codex-review-<branch>.log codex exec review --base <base>`.
  - Monitor tool for recurring events in a long-lived stream.

Bypass for a genuine exception: append `# polling-guard: allow`.
"""

import json
import re
import sys

BYPASS = "# polling-guard: allow"

# until/while … do … sleep … done  (foreground poll loop)
LOOP_SLEEP_RE = re.compile(
    r"\b(until|while)\b[^\n]{0,400}?(;|\n)\s*do\b[\s\S]{0,400}?\bsleep\b",
    re.IGNORECASE,
)
# sleep N ; / && / || cat|tail|head|grep  (peek pattern)
SLEEP_PEEK_RE = re.compile(
    r"\bsleep\s+\d+(?:\.\d+)?\s*(?:;|&&|\|\|)\s*(?:sudo\s+)?(?:cat|tail|head|grep)\b",
    re.IGNORECASE,
)
# pgrep probe aimed at codex
PGREP_CODEX_RE = re.compile(r"\bpgrep\b[^\n|;&]{0,120}codex", re.IGNORECASE)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") or ""
    if tool_input.get("run_in_background"):
        return 0  # background waiter loops are the sanctioned pattern
    if BYPASS in command:
        return 0

    reason = None
    if LOOP_SLEEP_RE.search(command):
        reason = (
            "Foreground until/while+sleep poll loop — this burns a turn per poll. "
            "Run this SAME loop in ONE Bash call with run_in_background=true so it "
            "exits when the condition is met and the completion notification wakes "
            "you once (use an ABSOLUTE log path)."
        )
    elif SLEEP_PEEK_RE.search(command):
        reason = (
            "sleep-then-peek at a growing file — don't watch progress. Launch the "
            "wait as ONE run_in_background Bash call whose until-loop exits when "
            "done, then read the capture file ONCE after the completion notification."
        )
    elif PGREP_CODEX_RE.search(command):
        reason = (
            "pgrep probe for a codex process — codex reviews should run in the "
            "FOREGROUND and block to completion: `script -q /tmp/codex-review-"
            "<branch>.log codex exec review --base <base>` (exit 2 = findings). "
            "No is-it-done-yet probes needed."
        )

    if reason:
        print(json.dumps({
            "decision": "block",
            "reason": reason + " Genuine exception? Append `# polling-guard: allow`.",
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
