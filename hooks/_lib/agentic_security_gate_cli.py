"""Stdin->decision CLI for hooks/agentic-security-gate.sh.

Reads the PreToolUse Agent payload on stdin, resolves the branch changeset via
git, and prints two lines: the gate action and its reason.
"""
import json
import os
import subprocess
import sys

from agentic_security_gate import gate_decision


def _changed_files():
    files = set()
    for cmd in (
        ["git", "diff", "--name-only", "main...HEAD"],
        ["git", "diff", "--name-only", "HEAD"],
    ):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except Exception:
            continue
        if out.returncode == 0:
            files.update(line for line in out.stdout.splitlines() if line.strip())
    return sorted(files)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        data = {}
    tool_input = data.get("tool_input") or {}
    subagent_type = tool_input.get("subagent_type") or ""
    prompt = tool_input.get("prompt") or ""
    disabled = os.environ.get("CLAUDE_DISABLE_AGENTIC_GATE", "0") == "1"
    decision = gate_decision(
        _changed_files(), prompt, subagent_type=subagent_type, disabled=disabled
    )
    print(decision["action"])
    print(decision["reason"])


if __name__ == "__main__":
    main()
