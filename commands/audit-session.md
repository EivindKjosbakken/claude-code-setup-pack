---
description: Find your own most-violated CLAUDE.md rules by auditing recent session transcripts
---

# /audit-session

Find which of my instructions the agent is actually failing to follow, ranked by
frequency, so I mechanise the expensive ones instead of guessing.

## What to do

1. **Locate recent transcripts.** They live under
   `~/.claude/projects/<encoded-project-path>/*.jsonl`, one file per session.
   Take the last 7 days unless I gave you a different window.

2. **Read my rules.** Load `~/.claude/CLAUDE.md` and any repo-level `CLAUDE.md`
   in scope. Extract each discrete instruction as a checkable statement.

3. **Count violations, don't judge them.** Walk the transcripts and count
   concrete, countable breaches — a tool call that did the forbidden thing, not
   a vibe. For each rule report:
   - how many times it was violated
   - how many sessions it appeared in
   - two or three verbatim examples with the session id

   Be strict about what counts. A rule the model *interpreted* differently than
   I intended is a wording problem; a rule it plainly broke is a mechanism
   problem. Report them separately — they have different fixes.

4. **Rank by cost, not count.** A violation that burns a whole turn (a
   foreground poll loop, a blocked call that has to be re-issued) costs far more
   than a cosmetic one. Weight accordingly and say how you weighted.

5. **Report** as a table: rule, violations, sessions, estimated cost, and a
   verdict of `mechanise` / `reword` / `drop`.

   `drop` is a real answer and an underused one. If a rule has not been violated
   in a week and nothing bad happened, it may simply be dead weight taking up
   attention budget.

## Then

For anything marked `mechanise`, run `/mechanize <rule>`.

## Notes

- Transcripts are large. Grep for the specific patterns each rule implies rather
  than reading files end to end.
- Do not count the same violation twice when a session was resumed or compacted.
- If a rule is unfalsifiable from a transcript ("be thoughtful"), say so plainly
  rather than inventing a number. That is itself the finding: it cannot be
  enforced, so it should probably be cut.
