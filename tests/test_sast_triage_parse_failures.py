"""AC19 — parse failure variants and TRIAGE_PARSE_FAILED.

Distinct from TRIAGE_NO_INPUT: NO_INPUT means no SAST artifact existed;
PARSE_FAILED means artifacts existed but unusable.

Error classes asserted:
  - json-decode-error  : truncated/malformed JSON
  - sarif-shape-error  : SARIF document but missing required path
  - semgrep-shape-error: semgrep output not a parseable SARIF on stdout
  - subprocess-failed  : non-zero exit from semgrep
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from sast_triage import detect_findings, detect_and_triage


def _stub_no_semgrep(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)


def test_sarif_shape_error_falls_through(tmp_path, monkeypatch, capsys):
    """SARIF JSON parses but missing required `runs` → sarif-shape-error fall-through."""
    # rung 1 — valid JSON but invalid SARIF shape (no runs[])
    sarif_path = tmp_path / "shape-error.sarif"
    sarif_path.write_text(json.dumps({"version": "2.1.0", "results_in_wrong_place": []}))
    monkeypatch.setenv("CLAUDE_SAST_SARIF_PATH", str(sarif_path))
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-shape")
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path / "metrics"))
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()
    _stub_no_semgrep(monkeypatch)

    result = detect_and_triage(
        task_id="t-shape",
        changed_files=["src/x.py"],
        scratchpad_dir=scratchpad,
    )
    assert result["verdict"] == "TRIAGE_PARSE_FAILED"
    err = capsys.readouterr().err
    assert "sarif-shape-error" in err


def test_semgrep_subprocess_non_zero_falls_through(tmp_path, monkeypatch, capsys):
    """AC4b — semgrep returns non-zero → subprocess-failed fall-through."""
    monkeypatch.delenv("CLAUDE_SAST_SARIF_PATH", raising=False)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-rc")
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path / "metrics"))
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/semgrep")

    class _Proc:
        returncode = 2
        stdout = ""
        stderr = "fatal: cannot run rules"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _Proc())

    findings, source = detect_findings(scratchpad_dir=scratchpad, changed_files=["src/x.py"])
    assert source["rung"] == 4
    err = capsys.readouterr().err
    assert "rung=3" in err
    assert "exit-code-2" in err


def test_parse_failed_writes_telemetry_record(tmp_path, monkeypatch):
    """AC19 — PARSE_FAILED writes a record with `verdict: "PARSE_FAILED"` and `failed_rungs`."""
    sarif_path = tmp_path / "bad.sarif"
    sarif_path.write_text("{not valid")
    monkeypatch.setenv("CLAUDE_SAST_SARIF_PATH", str(sarif_path))
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-parse-rec")
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path / "metrics"))
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()
    _stub_no_semgrep(monkeypatch)

    result = detect_and_triage(
        task_id="t-rec", changed_files=["src/x.py"], scratchpad_dir=scratchpad,
    )
    assert result["verdict"] == "TRIAGE_PARSE_FAILED"
    jsonl = tmp_path / "metrics" / "test-parse-rec" / "sast-triage.jsonl"
    assert jsonl.exists()
    records = [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]
    parse_records = [r for r in records if r.get("verdict") == "PARSE_FAILED"]
    assert len(parse_records) == 1
    record = parse_records[0]
    assert "failed_rungs" in record
    failed = record["failed_rungs"]
    assert any("json-decode-error" in str(entry) for entry in failed)


def test_no_input_distinct_from_parse_failed(tmp_path, monkeypatch):
    """NO_INPUT: nothing existed; PARSE_FAILED: stuff existed but was unusable.
    Distinct verdicts."""
    monkeypatch.delenv("CLAUDE_SAST_SARIF_PATH", raising=False)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-no-vs")
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path / "metrics"))
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()  # empty
    _stub_no_semgrep(monkeypatch)

    result = detect_and_triage(
        task_id="t-no-vs", changed_files=["src/x.py"], scratchpad_dir=scratchpad,
    )
    assert result["verdict"] == "TRIAGE_NO_INPUT"
    assert result["verdict"] != "TRIAGE_PARSE_FAILED"
