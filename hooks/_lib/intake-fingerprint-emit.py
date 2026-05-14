#!/usr/bin/env python3
"""Emit one JSONL line to {metrics_dir}/intake-overrides.jsonl.

Args (positional, all required):
  metrics_dir  timestamp  task_id  intake_md_path

13-key record per protocols/work-class-routing.md § Forensic logging schema
and pipeline-state plan.md § C1. Sentinel defaults applied when fields are
absent (parse_error names the failure mode). Returns 0 on every path
(advisory contract — hook MUST NOT block).
"""
import json
import os
import re
import sys

REQUIRED_KEYS = [
    "tier_emitted", "tier_initial", "detector_phase", "detector_confidence",
    "user_phrasing_signals", "phrasing_honoured", "override_token",
    "safety_override_fired", "predicted_files", "fingerprint_cost_tokens",
]
SENTINELS = {
    "tier_emitted": "<unknown>", "tier_initial": "<unknown>",
    "detector_phase": "<unknown>", "detector_confidence": "<unknown>",
    "user_phrasing_signals": [], "phrasing_honoured": False,
    "override_token": None, "safety_override_fired": False,
    "predicted_files": [], "fingerprint_cost_tokens": 0,
}


def parse_frontmatter(path):
    """Read intake.md frontmatter; return (fields, error_code).
    error_code in {None, intake-md-missing, intake-md-malformed, frontmatter-key-missing}."""
    if not os.path.isfile(path):
        return {}, "intake-md-missing"
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}, "intake-md-malformed"
    fields = _parse_yaml_block(match.group(1))
    if not any(k in fields for k in REQUIRED_KEYS):
        return fields, "frontmatter-key-missing"
    return fields, None


def _parse_yaml_block(block):
    """Minimal YAML scalar/list/bool/null parser sufficient for the contract."""
    out = {}
    for line in block.splitlines():
        if ":" not in line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = _coerce(value.strip())
    return out


_SCALAR_LITERALS = {"": None, "null": None, "true": True, "false": False}


def _coerce_scalar(raw):
    """Bool/null/int/quoted-string/bare-string. Returns sentinel _NOT_SCALAR for lists."""
    lowered = raw.lower()
    if lowered in _SCALAR_LITERALS:
        return _SCALAR_LITERALS[lowered]
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        return raw


def _coerce(raw):
    """YAML scalar OR inline-list value. Lists recurse on _coerce_scalar."""
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_coerce_scalar(item.strip()) for item in inner.split(",")]
    return _coerce_scalar(raw)


def build_record(fields, error_code, timestamp, task_id):
    """Compose the 13-key JSONL record dict per plan § C1. Sentinel defaults
    for missing keys. String caps applied defensively at 1024 chars."""
    record = {"timestamp": timestamp, "task_id": task_id}
    for key in REQUIRED_KEYS:
        record[key] = fields.get(key, SENTINELS[key])
    if error_code is not None:
        record["parse_error"] = error_code
    return record


def append_jsonl(path, record):
    """Append json.dumps(record) + newline to path. Standard open(a) works for
    metrics/**/*.jsonl post-2026-05-09 per feedback_reflect_phase_quirks.md §1."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def main(argv):
    """argv = [script, metrics_dir, timestamp, task_id, intake_md_path]."""
    if len(argv) != 5:
        return 0
    metrics_dir, timestamp, task_id, intake_md = argv[1], argv[2], argv[3], argv[4]
    if task_id == "<unknown>":
        fields, error_code = {}, "task-id-resolution-failed"
    else:
        fields, error_code = parse_frontmatter(intake_md)
    record = build_record(fields, error_code, timestamp, task_id)
    append_jsonl(os.path.join(metrics_dir, "intake-overrides.jsonl"), record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
