#!/usr/bin/env python3
"""Emit one JSONL line to {metrics_dir}/tool-output-bytes.jsonl.

Reads the PostToolUse payload on stdin, extracts tool_response.output, and
appends a record. When estimated_tokens > THRESHOLD, prints a warning to
stderr (the hook never exits non-zero — informational only).

Schema:
  {ts, tool, char_count, estimated_tokens, agent_role?, task_id?, reason?}

Non-string output (binary, dict, list) records char_count: 0 with
reason: "non-string-output" rather than skipping (negative-case observability).
"""
import json
import os
import sys

THRESHOLD_TOKENS = 20_000


def _extract_output(payload):
    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return None, "missing-tool-response"
    if "output" not in response:
        return None, "missing-tool-response"
    output = response["output"]
    if not isinstance(output, str):
        return None, "non-string-output"
    return output, None


def _build_record(ts, tool, output, reason, agent_role, task_id):
    if reason == "non-string-output":
        char_count = 0
    else:
        char_count = len(output)
    rec = {
        "ts": ts,
        "tool": tool,
        "char_count": char_count,
        "estimated_tokens": char_count // 4,
    }
    if agent_role:
        rec["agent_role"] = agent_role
    if task_id:
        rec["task_id"] = task_id
    if reason == "non-string-output":
        rec["reason"] = reason
    return rec


def _append_line(metrics_dir, rec):
    os.makedirs(metrics_dir, exist_ok=True)
    out = os.path.join(metrics_dir, "tool-output-bytes.jsonl")
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def main(argv):
    if len(argv) != 4:
        return 0
    metrics_dir, ts, task_id = argv[1], argv[2], argv[3]
    try:
        payload = json.loads(sys.stdin.read())
    except (ValueError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    output, reason = _extract_output(payload)
    if reason == "missing-tool-response":
        return 0
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    agent_role = tool_input.get("subagent_type", "") if isinstance(tool_input, dict) else ""
    rec = _build_record(ts, tool, output, reason, agent_role, task_id)
    _append_line(metrics_dir, rec)
    if rec["estimated_tokens"] > THRESHOLD_TOKENS:
        sys.stderr.write(
            f"tool-output-bytes: large output detected — tool={tool} "
            f"char_count={rec['char_count']} "
            f"estimated_tokens={rec['estimated_tokens']} "
            f"(threshold={THRESHOLD_TOKENS})\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
