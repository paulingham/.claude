"""AC13, AC14, AC15 — telemetry JSONL writer.

- AC13: Every triage decision (incl. `drop`) appends one record with
  required fields.
- AC14: `rationale_excerpt` is single-line, ≤200 chars; full rationale hashed.
- AC15: When metrics dir unwritable, runner stderr-warns and continues.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from sast_triage import write_decision_jsonl


def _finding(rule_id="r1", file="src/a.py", line=10, tool="semgrep", sev="HIGH"):
    return {
        "rule_id": rule_id,
        "tool": tool,
        "file": file,
        "line": line,
        "sast_severity": sev,
        "message": "msg",
        "snippet": "snippet",
    }


def test_every_decision_writes_one_jsonl_record_with_required_fields(tmp_path, monkeypatch):
    """AC13 — N decisions → N records; every required field present."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-tele")
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path / "metrics"))

    decisions = [
        ("keep", "Real SQL injection sink reachable from request body parser."),
        ("drop", "Test fixture file mocking the database driver, not prod."),
        ("unsure", "Cannot determine without seeing calling site context."),
    ]
    for i, (verdict, rationale) in enumerate(decisions):
        write_decision_jsonl(
            task_id="task-y",
            finding=_finding(rule_id=f"rule.{i}"),
            verdict=verdict,
            rationale=rationale,
        )

    jsonl = tmp_path / "metrics" / "test-tele" / "sast-triage.jsonl"
    assert jsonl.exists()
    records = [json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
    assert len(records) == 3

    required = {
        "ts", "session_id", "task_id", "rule_id", "tool", "file", "line",
        "sast_severity", "verdict", "rationale_excerpt", "rationale_full_hash",
    }
    for record in records:
        missing = required - record.keys()
        assert not missing, f"missing fields {missing} in {record}"
        assert record["session_id"] == "test-tele"
        assert record["task_id"] == "task-y"


def test_rationale_excerpt_single_line_truncated_to_200(tmp_path, monkeypatch):
    """AC14 — multi-line rationale → single-line, ≤200 chars; hash matches full."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-trunc")
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path / "metrics"))

    long_rationale = (
        "First line of rationale text spanning multiple paragraphs.\n"
        "Second line — newlines should be coerced to spaces in excerpt.\n"
        "Third line padding to make this longer than two hundred characters total."
        + " filler" * 50
    )
    write_decision_jsonl(
        task_id="task-z",
        finding=_finding(),
        verdict="keep",
        rationale=long_rationale,
    )
    jsonl = tmp_path / "metrics" / "test-trunc" / "sast-triage.jsonl"
    record = json.loads(jsonl.read_text().splitlines()[0])

    excerpt = record["rationale_excerpt"]
    assert "\n" not in excerpt
    assert len(excerpt) <= 200
    # First line text should be present (single-line collapse)
    assert excerpt.startswith("First line")

    # Hash matches full original
    expected_hash = "sha1:" + hashlib.sha1(long_rationale.encode("utf-8")).hexdigest()
    assert record["rationale_full_hash"] == expected_hash


def test_unwritable_metrics_dir_warns_and_continues(tmp_path, monkeypatch, capsys):
    """AC15 — unwritable metrics dir → stderr warning, no exception raised."""
    bad_dir = tmp_path / "metrics_root"
    bad_dir.mkdir()
    bad_dir.chmod(0o500)  # read-only — cannot create subdirs/files inside
    try:
        monkeypatch.setenv("CLAUDE_SESSION_ID", "test-unw")
        monkeypatch.setenv("CLAUDE_METRICS_DIR", str(bad_dir))

        # Should NOT raise — telemetry failure does not block triage
        write_decision_jsonl(
            task_id="task-unw",
            finding=_finding(),
            verdict="keep",
            rationale="A real finding rationale long enough to pass the validator.",
        )
        err = capsys.readouterr().err
        assert "sast-triage" in err.lower() or "metrics" in err.lower()
    finally:
        # Restore permissions so tmp_path cleanup works
        bad_dir.chmod(0o700)
