# The Claude Code Setup Pack

The parts of my Claude Code setup that actually changed how the agent behaves —
extracted from the configuration I run every day, cleaned up, and ready to drop
into your own `~/.claude/`.

This is not a list of tips. Every file here is a **mechanism**: something that
runs automatically and makes the failure impossible, rather than a rule in a
prompt that the model agrees with and then ignores twenty turns later.

That distinction is the whole point of the pack.

> New mechanisms and the workflows behind them go out by email: [subscribe free on Substack](https://eivindkjosbakken.substack.com/subscribe?utm_source=github&utm_medium=readme_top&utm_campaign=setup_pack_oct2026).

---

## Why rules in `CLAUDE.md` stop working

I spent months writing instructions into `CLAUDE.md` and watching them decay.
The pattern was always the same: the model follows a new rule for a day, then
drifts back. Nightly reviews of my own sessions put numbers on it —

| Rule, written as prose | What actually happened |
|---|---|
| "Don't use long inline heredocs" | 150 violations in a single day |
| "Don't paste secrets into commands" | flagged in 23 of 28 nightly reviews |
| "Don't hand-roll polling loops" | 689 poll/sleep calls in one week |
| "Don't `cd` into the directory you're already in" | 68% of all leading `cd`s were no-ops |

None of these are comprehension failures. The model understands the rule
perfectly. It just has a lot of instructions competing for attention, and prose
has no enforcement.

**A hook has enforcement.** Each rule above became a ~70-line Python hook, and
each one went to roughly zero and stayed there. That is what is in this pack.

---

## What's inside

### `hooks/` — four PreToolUse guards

| Hook | What it does |
|---|---|
| `pretool-heredoc-guard.py` | Blocks inline heredocs with bodies over 15 lines. Long heredocs break on quoting (Python f-strings especially), hide syntax errors, and reinvent scratch files. The block message names the right pattern: write the script, run it in one line. |
| `pretool-cd-guard.py` | **Silently rewrites** `cd <cwd> && cmd` to `cmd` when the target is already the session directory. Worth studying as a design example — it started as a blocker, and blocking cost a full round trip per occurrence while teaching nothing. Auto-fixing is strictly better when the fix is provably safe. |
| `pretool-polling-guard.py` | Blocks foreground `until … sleep … done` loops, `sleep N; tail log` peeks, and is-it-done-yet process probes. Each one burns an entire turn. Background waiter loops are explicitly exempt — that is the pattern it steers you toward. |
| `pretool-secret-guard.py` | Blocks key-shaped literals (AWS, OpenAI, GitHub, Slack, Notion, Google, JWTs…) in commands *and* file writes, plus full `.env` dumps and inline `export TOKEN=…` assignments. Credentials that reach a transcript have to be rotated. |

### `CLAUDE.md.template`

The structure I converged on after rewriting mine perhaps a dozen times.
Annotated with the reasoning, including the sections that turned out to matter
most — the environment-truths table and the mechanisms-not-prose principle.

### `settings.json.example`

Clean wiring for all four hooks. Copy the `hooks` block into your existing
settings; don't overwrite the file.

### `commands/`

Two slash commands that are genuinely portable rather than tied to my repos:
`/audit-session` (find your own most-violated rules) and `/mechanize` (turn one
of them into a hook).

---

## Install

See `INSTALL.md`. It takes about five minutes, and you can install a single hook
without taking the rest.

---

## The one habit that matters more than any file here

**Run `/audit-session` on your own transcripts before copying my hooks.**

My four guards fix *my* four most expensive habits. Yours will be different —
different stack, different tools, different failure modes. The transferable
part is the loop, not my particular guards:

1. Review your sessions periodically and count what actually went wrong.
2. Take the single most frequent failure.
3. Write a hook that makes it impossible.
4. Delete the corresponding prose rule from `CLAUDE.md`, because it is now dead
   weight competing for the model's attention.

Every hook in this pack came out of that loop. None of them came from a blog
post — including this one.

---

## Keep improving your coding-agent setup

[Get free practical AI-engineering workflows by email](https://eivindkjosbakken.substack.com/subscribe?utm_source=github&utm_medium=readme&utm_campaign=setup_pack_sep2026).

For the full configuration library, [The paid Vault](https://eivindkjosbakken.substack.com/p/the-vault-my-complete-ai-engineering?utm_source=github&utm_medium=readme&utm_campaign=setup_pack_sep2026) includes global and project templates, commands, hooks, prompt patterns and the parallel-agent setup. Access and updates are included while subscribed.

The files in this repository remain free to use; subscribing is optional.
