#!/usr/bin/env python3
"""PreToolUse hook: keep credentials out of transcripts.

Blocks, for Bash commands AND file-writing tools (Write/Edit/MultiEdit/NotebookEdit):
  1. Key-shaped literals (AKIA…, sk-…, lin_api_…, ghp_…, xox?-…, phx_/phc_…, GOCSPX-…,
     ntn_…, tpuf_…, xaat-…, AIza…, and 3-segment JWTs `eyJ….….…`) appearing inline.
  2. Full dumps of .env files (cat/head/tail/less/more/bat on .env*), except
     .env.example/.env.sample/.env.template. Use `grep '^VAR=' .env` for one var instead.
  3. `export NAME_TOKEN=<literal>` / `NAME_SECRET=<literal> cmd` style inline secret
     assignments (literal values only — $VAR, $(…) and short values pass).
  4. The original dotenvx-vs-service-account-JSON leak and `vercel env pull` warning.

Escape hatch for true false positives, after telling the user:
append `# secret-guard: allow` to the Bash command (file tools have no bypass).

History: replaced the narrow dotenvx-only guard on 2026-06-10 (process review:
inline secrets were flagged in 23 of 28 nightly reviews; prose rules didn't stick).
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

BYPASS_MARKER = "# secret-guard: allow"

KEY_PATTERNS = (
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("API key (sk-…)", re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b")),
    ("Linear key", re.compile(r"\blin_api_[A-Za-z0-9]{24,}\b")),
    ("GitHub token", re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{20,}\b")),
    ("PostHog key", re.compile(r"\bph[cx]_[A-Za-z0-9]{24,}\b")),
    ("Google OAuth secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{16,}\b")),
    ("Notion token", re.compile(r"\bntn_[A-Za-z0-9]{24,}\b")),
    ("Turbopuffer key", re.compile(r"\btpuf_[A-Za-z0-9]{16,}\b")),
    ("Axiom token", re.compile(r"\bxaat-[A-Za-z0-9-]{16,}\b")),
    ("Google API key", re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b")),
    # A full 3-segment JWT (header starts `eyJ` = base64 of `{"`). Catches runtime-scraped
    # auth tokens (e.g. a scraped session JWT) landing in the transcript
    # or a repo-tree file. Added 2026-07-01 (process review: token-in-repo recurred 3 cycles).
    ("JWT (eyJ…)", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}")),
)

ENV_DUMP_RE = re.compile(
    r"\b(cat|head|tail|less|more|bat|strings)\b[^|;&\n]*?(^|[\s'\"/])(\.env(?:\.[\w-]+)*)(['\"]?)(\s|$|;)",
    re.MULTILINE,
)
ENV_SAFE_SUFFIXES = (".example", ".sample", ".template")

INLINE_ASSIGN_RE = re.compile(
    r"(?:^|\s|;|&&|\|\|)(?:export\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|APIKEY|ACCESS_KEY|PRIVATE_KEY)[A-Za-z0-9_]*)"
    r"=([\"']?)(?!\$)(?!`)([^\s\"'`$]{8,})\2",
    re.IGNORECASE,
)
ASSIGN_PLACEHOLDER_RE = re.compile(
    r"^(\.{3}|x+|X+|\*+|<[^>]*>|your[-_].*|placeholder.*|dummy.*|redacted.*|example.*|changeme.*)$",
    re.IGNORECASE,
)

DOTENVX_DANGER_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r'"private_key_id"\s*:'),
    re.compile(r'"type"\s*:\s*"service_account"'),
)
ENV_PATH_RE = re.compile(r"(--env-file[=\s]+(\S+))|(\.env(?:\.[\w.-]+)?)")

FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def block(reason: str) -> int:
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def find_key_literal(text: str):
    for label, pattern in KEY_PATTERNS:
        if pattern.search(text):
            return label
    return None


def env_dump_target(command: str):
    for match in ENV_DUMP_RE.finditer(command):
        env_name = match.group(3)
        if not env_name.endswith(ENV_SAFE_SUFFIXES):
            return env_name
    return None


def inline_secret_assignment(command: str):
    for match in INLINE_ASSIGN_RE.finditer(command):
        variable_name, _, value = match.groups()
        if ASSIGN_PLACEHOLDER_RE.match(value):
            continue
        return variable_name
    return None


def env_file_is_dangerous(path: Path) -> bool:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return False
    return any(pattern.search(text) for pattern in DOTENVX_DANGER_PATTERNS)


def candidate_env_files(command: str, cwd: Path) -> list[Path]:
    candidates: list[Path] = []
    for _, named, default in ENV_PATH_RE.findall(command):
        chosen = named or default
        if not chosen:
            continue
        candidates.append(cwd / chosen if not os.path.isabs(chosen) else Path(chosen))
    if not candidates:
        for default in (".env.local", ".env"):
            candidates.append(cwd / default)
    return candidates


def check_bash(command: str, cwd: Path) -> int:
    if BYPASS_MARKER in command:
        return 0

    key_label = find_key_literal(command)
    if key_label:
        return block(
            f"Blocked: command contains an inline credential ({key_label}). Secrets must "
            "never appear in commands — they persist in the transcript. Read it from "
            "~/.config/<service>/credentials, an env var, or a secrets manager instead. "
            "If this is genuinely a false positive, tell the user, then re-run with "
            f"'{BYPASS_MARKER}' appended."
        )

    env_target = env_dump_target(command)
    if env_target:
        return block(
            f"Blocked: dumping {env_target} would copy every secret in it into the "
            "transcript. Fetch only what you need: grep '^VAR_NAME=' <file>, or list "
            "names without values: grep -o '^[A-Z_]*' <file>. "
            f"False positive? Tell the user and append '{BYPASS_MARKER}'."
        )

    assigned_variable = inline_secret_assignment(command)
    if assigned_variable:
        return block(
            f"Blocked: inline literal assignment to {assigned_variable} puts the secret in "
            "the transcript. Load it indirectly, e.g. "
            'VAR="$(grep ^NAME= ~/.config/<service>/credentials | cut -d= -f2-)" or use '
            f"a secrets-manager lookup. False positive? Tell the user and append '{BYPASS_MARKER}'."
        )

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if any("dotenvx" in token for token in tokens):
        for env_file in candidate_env_files(command, cwd):
            if env_file.exists() and env_file_is_dangerous(env_file):
                return block(
                    f"Blocked: dotenvx command would read {env_file}, which contains a "
                    "service-account JSON or PEM private key. dotenvx dumps the raw "
                    "source line on parse errors and the secret lands in the transcript. "
                    "Convert the value to a single-line base64 env var first."
                )

    if "vercel env pull" in command:
        sys.stderr.write(
            "WARNING: `vercel env pull` may print service-account JSON to stdout. "
            "Use `--environment <env>` and redirect to a file, then read with jq.\n"
        )
    return 0


def check_file_tool(tool_input: dict) -> int:
    content_fields = [
        tool_input.get("content") or "",
        tool_input.get("new_string") or "",
        tool_input.get("new_source") or "",
    ]
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict):
            content_fields.append(edit.get("new_string") or "")
    text = "\n".join(field for field in content_fields if field)
    if not text:
        return 0
    key_label = find_key_literal(text)
    if key_label:
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or "the file"
        return block(
            f"Blocked: the content being written to {file_path} contains an inline "
            f"credential ({key_label}). Secrets belong in ~/.config/<service>/credentials, "
            "env vars, or a secrets manager — never in written files except dedicated "
            "credential files under ~/.config or */scripts/credentials/."
        )
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    if tool_name == "Bash":
        command = tool_input.get("command") or ""
        cwd = Path(payload.get("cwd") or os.getcwd())
        return check_bash(command, cwd)

    if tool_name in FILE_TOOLS:
        file_path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        # Dedicated credential stores are the sanctioned destination — let them through.
        if "/.config/" in file_path or "/scripts/credentials/" in file_path or "/.ssh/" in file_path:
            return 0
        return check_file_tool(tool_input)

    return 0


if __name__ == "__main__":
    sys.exit(main())
