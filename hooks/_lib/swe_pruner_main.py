"""SWE-Pruner hook entry point — called by pre-agent-swe-pruner.sh.

Reads JSON from stdin, scores the spawn prompt, writes a JSONL record.
All output goes to JSONL only — stdout is kept silent (INVARIANT 1).
Never raises to caller: all exceptions are swallowed so the hook exits 0.
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    # Prepend _lib dir passed as argv[1] to sys.path so sibling modules resolve
    if len(sys.argv) > 1:
        lib_dir = sys.argv[1]
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return  # Malformed input — exit 0 silently

    try:
        from swe_pruner import (
            segment_content_blocks,
            extract_goal_keywords,
            propose_drops,
            get_jsonl_path,
            build_record,
        )
        from secure_jsonl import append_secure_jsonl
    except Exception:
        return  # Import failure — exit 0 silently

    try:
        tool_input = (payload or {}).get("tool_input") or {}
        prompt = str(tool_input.get("prompt") or "")
        subagent_type = str(tool_input.get("subagent_type") or "unknown")[:64]

        blocks = segment_content_blocks(prompt)
        keywords = extract_goal_keywords(subagent_type, prompt)
        proposals = [(b, propose_drops(b, keywords)) for b in blocks]
        record = build_record(payload, proposals)
        jsonl_path = get_jsonl_path()
        append_secure_jsonl(jsonl_path, record)
    except Exception:
        return  # Any scoring/write failure — exit 0 silently


if __name__ == "__main__":
    main()
