#!/usr/bin/env python3
"""
Semantic stuck-detector — ported from OpenHands openhands/controller/stuck.py @ v0.39.1.
Shipped ADVISORY (log-only): always exits 0, never blocks.

Claude Code transcript schema (Stop hook, stdin JSON):
  - transcript_path: path to JSONL transcript file
  - stop_hook_active: bool (if true, skip to avoid Stop recursion)

Transcript JSONL record types (one object per line):
  type:"assistant" -> .message.content[] list of blocks:
    text block:     {"type":"text","text":"..."}              agent thought
    tool_use block: {"type":"tool_use","id":"...","name":"...","input":{...},"caller":{}}  action
  type:"user" -> .message.content is:
    str  => genuine user prompt (BOUNDARY — resets history window)
    list => tool_result items (observations) OR genuine user text blocks
      tool_result: {"type":"tool_result","tool_use_id":"...","content":<str|list>,"is_error":<bool>}
      text block:  {"type":"text","text":"..."} => genuine user prompt (BOUNDARY)
  Other types (attachment, mode, last-prompt, file-history-snapshot, etc.) => ignore.

Output: "MATCH <pattern>\t<json-evidence>" or "NOMATCH"
"""

import json
import sys

from stuck_patterns import (
    check_alternating,
    check_context_window,
    check_monologue,
    check_repeating_action_error,
    check_repeating_action_observation,
    eq_no_pid,
    strip_volatile,
)

# Max lines to read from transcript (performance cap)
_TRANSCRIPT_LINE_CAP = 400

_PATTERNS = [
    ("repeating-action-observation", check_repeating_action_observation),
    ("repeating-action-error", check_repeating_action_error),
    ("monologue", check_monologue),
    ("alternating", check_alternating),
    ("context-window", check_context_window),
]


def _obs_content(block: dict) -> str:
    """Stringify tool_result content for equality comparison."""
    raw = block.get("content", "")
    if isinstance(raw, list):
        return json.dumps(raw, sort_keys=True)
    return str(raw) if raw is not None else ""


def _is_genuine_user(record: dict) -> bool:
    """True if this user record is a genuine user prompt, not a tool_result carrier."""
    content = record.get("message", {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get("type") == "text"
            for b in content
        )
    return False


def _parse_assistant(rec: dict) -> list:
    """Extract action and/or message events from an assistant record."""
    events = []
    content = rec.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return events
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            inp = block.get("input", {})
            if isinstance(inp, dict):
                inp = strip_volatile(inp)
            events.append({"kind": "action", "name": block.get("name", ""), "input": inp})
        elif block.get("type") == "text" and block.get("text"):
            events.append({"kind": "message", "text": block["text"]})
    return events


def _parse_user_obs(rec: dict) -> list:
    """Extract observation events from a user record (tool_result blocks only)."""
    content = rec.get("message", {}).get("content")
    if not isinstance(content, list):
        return []
    events = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            events.append({
                "kind": "observation",
                "content": _obs_content(block),
                "is_error": bool(block.get("is_error")),
            })
    return events


def _record_to_events(rec: dict) -> list:
    rtype = rec.get("type")
    if rtype == "assistant":
        return _parse_assistant(rec)
    if rtype == "user":
        return _parse_user_obs(rec)
    return []


def _find_last_user_boundary(records: list) -> int:
    """Return index of the last genuine user-prompt record, or -1."""
    last = -1
    for i, rec in enumerate(records):
        if rec.get("type") == "user" and _is_genuine_user(rec):
            last = i
    return last


def parse_transcript(path: str) -> list:
    """
    Read transcript JSONL, return filtered_history = events after the last
    genuine user message, excluding user boundaries and null events.
    Caps read to last _TRANSCRIPT_LINE_CAP lines.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw_lines = [ln.strip() for ln in fh if ln.strip()]
    raw_lines = raw_lines[-_TRANSCRIPT_LINE_CAP:]

    records = []
    for line in raw_lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    last_idx = _find_last_user_boundary(records)
    after = records[last_idx + 1:] if last_idx >= 0 else records

    events = []
    for rec in after:
        events.extend(_record_to_events(rec))
    return events


def detect(events: list) -> dict:
    """Run five patterns in order; return first match or NOMATCH."""
    for name, fn in _PATTERNS:
        evidence = fn(events)
        if evidence is not None:
            return {"matched": True, "pattern": name, "evidence": evidence}
    return {"matched": False, "pattern": None, "evidence": {}}


def main() -> None:
    """Read Stop hook stdin JSON, run detector, print verdict."""
    try:
        payload = json.loads(sys.stdin.read())
        path = payload.get("transcript_path", "")
        if not path:
            print("NOMATCH")
            return
        events = parse_transcript(path)
        if len(events) < 3:
            print("NOMATCH")
            return
        result = detect(events)
        if result["matched"]:
            print(f"MATCH {result['pattern']}\t{json.dumps(result['evidence'], default=str)}")
        else:
            print("NOMATCH")
    except Exception:  # noqa: BLE001 — malformed transcript must never wedge Stop
        print("NOMATCH")


if __name__ == "__main__":
    main()
