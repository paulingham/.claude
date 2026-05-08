"""AC1 — bypass switch short-circuits § 0 BEFORE any rung.

`CLAUDE_DISABLE_SAST_TRIAGE=1` causes the runner to:
- emit `TRIAGE_BYPASSED` verdict
- NOT touch the main `metrics/$SESSION/sast-triage.jsonl` (no file created)
- emit a stderr line `SAST triage bypassed via CLAUDE_DISABLE_SAST_TRIAGE`
- write exactly one record to `metrics/$SESSION/sast-triage-bypass.jsonl` (AC20)

Bypass MUST come before detection — env-set means no semgrep invocation, no
scratchpad scan, no SARIF parse.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from sast_triage import detect_and_triage


def _stub_subprocess_blowup(monkeypatch):
    """If detection runs at all, this raises — proves bypass short-circuits."""
    def _explode(*a, **k):
        raise AssertionError("detection ran despite bypass switch")
    monkeypatch.setattr("subprocess.run", _explode)


def test_bypass_env_var_short_circuits_section_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_DISABLE_SAST_TRIAGE", "1")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-bypass")
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path / "metrics"))
    monkeypatch.delenv("CLAUDE_SAST_SARIF_PATH", raising=False)
    _stub_subprocess_blowup(monkeypatch)

    result = detect_and_triage(task_id="task-x", changed_files=["src/a.py"])

    assert result["verdict"] == "TRIAGE_BYPASSED"
    main_jsonl = tmp_path / "metrics" / "test-bypass" / "sast-triage.jsonl"
    assert not main_jsonl.exists(), "main JSONL must NOT be created on bypass"

    bypass_jsonl = tmp_path / "metrics" / "test-bypass" / "sast-triage-bypass.jsonl"
    assert bypass_jsonl.exists(), "bypass JSONL must contain exactly one record"
    records = [
        json.loads(line)
        for line in bypass_jsonl.read_text().splitlines()
        if line.strip()
    ]
    assert len(records) == 1
    record = records[0]
    assert record["verdict"] == "BYPASSED"
    assert record["reason"] == "CLAUDE_DISABLE_SAST_TRIAGE=1"
    assert record["session_id"] == "test-bypass"
    assert record["task_id"] == "task-x"
    assert "ts" in record

    captured = capsys.readouterr()
    assert "SAST triage bypassed via CLAUDE_DISABLE_SAST_TRIAGE" in captured.err
