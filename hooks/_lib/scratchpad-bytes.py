"""Compute scratchpad-injection bytes from an Agent spawn payload.

Reads JSON on stdin, extracts the rendered ## Pipeline Scratchpad section from
tool_input.prompt (post-filter, as actually injected by the orchestrator), and
emits one JSON object on stdout with byte counts. Returns silently if no
scratchpad section is present — empty injection logs as 0 bytes.
"""
import json
import re
import sys


_HEADER_PATTERN = re.compile(
    r"^##\s+Pipeline\s+Scratchpad\b.*?$",
    re.MULTILINE | re.IGNORECASE,
)
_NEXT_HEADER = re.compile(r"^##\s", re.MULTILINE)


def _section_bytes(prompt):
    if not prompt:
        return 0, 0
    match = _HEADER_PATTERN.search(prompt)
    if not match:
        return 0, 0
    body_start = match.end()
    next_header = _NEXT_HEADER.search(prompt, body_start)
    body_end = next_header.start() if next_header else len(prompt)
    section = prompt[match.start():body_end]
    body = prompt[body_start:body_end]
    return len(section.encode("utf-8")), len(body.strip().encode("utf-8"))


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = payload.get("tool_input", {}) or {}
    prompt = tool_input.get("prompt", "") or ""
    section_bytes, body_bytes = _section_bytes(prompt)
    out = {
        "subagent_type": tool_input.get("subagent_type", "")[:64],
        "task_id": tool_input.get("task_id", "")[:64],
        "section_bytes": section_bytes,
        "body_bytes": body_bytes,
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
