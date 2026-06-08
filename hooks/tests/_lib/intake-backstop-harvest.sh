#!/usr/bin/env bash
# intake-backstop-harvest.sh — read-only harvester of real orchestrator Bash
# commands from local Claude Code transcripts, for seeding the
# intake-backstop corpus fixture (SLICE C).
#
# Reads TOP-LEVEL transcripts at $HOME/.claude/projects/<slug>/<uuid>.jsonl
# (NOT the <uuid>/subagents/ subdir — those are subagent calls, never the
# orchestrator). For each Bash tool_use it extracts .input.command (transcript
# shape: message.content[] entries of type "tool_use", name "Bash"). Commands
# are deduped and REDACTED (same shape as bash-write-guard.sh::_bwg_redact)
# before emit. Emits `{"command":"...","expected":"allow"}` rows to stdout.
#
# This reads real local transcripts. It is READ-ONLY over them and redacts
# user:password@ credentials in URLs before writing anything to stdout.
#
# Usage: bash intake-backstop-harvest.sh [PROJECTS_DIR]
#   PROJECTS_DIR defaults to $HOME/.claude/projects

set -uo pipefail

PROJECTS_DIR="${1:-$HOME/.claude/projects}"

[[ -d "$PROJECTS_DIR" ]] || exit 0

python3 - "$PROJECTS_DIR" <<'PY'
import json, os, sys, glob, re

projects_dir = sys.argv[1]

def redact(s):
    # Mirror bash-write-guard.sh::_bwg_redact — scrub user:pass@ in URLs.
    return re.sub(r'(://)[^/@\s]+:[^/@\s]+@', r'\1REDACTED@', s)

seen = set()
out = []

# TOP-LEVEL transcripts only: <slug>/<uuid>.jsonl. Exclude the subagents subdir.
pattern = os.path.join(projects_dir, '*', '*.jsonl')
for path in sorted(glob.glob(pattern)):
    # Skip anything under a subagents/ subdir (defensive — glob above is one level).
    if '/subagents/' in path:
        continue
    try:
        f = open(path, 'r', encoding='utf-8', errors='replace')
    except OSError:
        continue
    with f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = obj.get('message', {})
            content = msg.get('content') if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get('type') != 'tool_use' or c.get('name') != 'Bash':
                    continue
                cmd = (c.get('input') or {}).get('command')
                if not isinstance(cmd, str) or not cmd.strip():
                    continue
                cmd = redact(cmd.strip())
                if cmd in seen:
                    continue
                seen.add(cmd)
                out.append(cmd)

for cmd in out:
    sys.stdout.write(json.dumps({"command": cmd, "expected": "allow"}) + "\n")
PY
