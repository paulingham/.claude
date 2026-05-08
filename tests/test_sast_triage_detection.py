"""AC2-AC5, AC19 — detection ladder.

4-rung ladder, first hit wins:
  1. $CLAUDE_SAST_SARIF_PATH if readable
  2. pipeline-state/{task_id}/scratchpad/sast-*.sarif
  3. on-demand semgrep --sarif on changed files
  4. None — TRIAGE_NO_INPUT

AC4: direct subprocess invocation (NOT a Claude skill); shutil.which gates entry.
AC19: PARSE_FAILED ≠ NO_INPUT — corrupt artifacts produce a distinct verdict.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from sast_triage import detect_findings, detect_and_triage


def _minimal_sarif(rule_id="js.audit.sample", file_uri="src/a.js", line=10,
                  level="error", message="sample message"):
    """A minimal valid SARIF document — single run, single result."""
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "Semgrep"}},
                "results": [
                    {
                        "ruleId": rule_id,
                        "level": level,
                        "message": {"text": message},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": file_uri},
                                    "region": {"startLine": line},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _stub_no_semgrep(monkeypatch):
    """semgrep not installed — `shutil.which("semgrep")` returns None."""
    monkeypatch.setattr("shutil.which", lambda name: None)


def test_pre_staged_sarif_path_wins(tmp_path, monkeypatch):
    """AC2 — $CLAUDE_SAST_SARIF_PATH wins over scratchpad."""
    sarif_path = tmp_path / "from_ci.sarif"
    sarif_path.write_text(json.dumps(_minimal_sarif(rule_id="ci.rule")))

    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()
    (scratchpad / "sast-other.sarif").write_text(
        json.dumps(_minimal_sarif(rule_id="scratch.rule"))
    )

    monkeypatch.setenv("CLAUDE_SAST_SARIF_PATH", str(sarif_path))
    monkeypatch.delenv("CLAUDE_DISABLE_SAST_TRIAGE", raising=False)

    findings, source = detect_findings(
        scratchpad_dir=scratchpad,
        changed_files=["src/a.js"],
    )
    assert source["rung"] == 1
    assert source["path"] == str(sarif_path)
    rule_ids = {f["rule_id"] for f in findings}
    assert "ci.rule" in rule_ids
    assert "scratch.rule" not in rule_ids


def test_scratchpad_sarif_used_when_path_unset(tmp_path, monkeypatch):
    """AC3 — env unset → scratchpad SARIF is the source."""
    monkeypatch.delenv("CLAUDE_SAST_SARIF_PATH", raising=False)
    monkeypatch.delenv("CLAUDE_DISABLE_SAST_TRIAGE", raising=False)
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()
    sarif = scratchpad / "sast-codeql.sarif"
    sarif.write_text(json.dumps(_minimal_sarif(rule_id="cql.rule")))

    findings, source = detect_findings(
        scratchpad_dir=scratchpad,
        changed_files=["src/a.js"],
    )
    assert source["rung"] == 2
    assert source["path"] == str(sarif)
    assert any(f["rule_id"] == "cql.rule" for f in findings)


def test_semgrep_invoked_on_changed_files_only(tmp_path, monkeypatch):
    """AC4 — rungs 1-2 absent, semgrep invoked with `--sarif --json --quiet --` and changed files only."""
    monkeypatch.delenv("CLAUDE_SAST_SARIF_PATH", raising=False)
    monkeypatch.delenv("CLAUDE_DISABLE_SAST_TRIAGE", raising=False)
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()  # empty — rung 2 fails

    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/semgrep")

    sarif_doc = _minimal_sarif(rule_id="ondemand.rule", file_uri="src/changed.py")
    seen_calls = {}

    class _CompletedProcess:
        def __init__(self):
            self.returncode = 0
            self.stdout = json.dumps(sarif_doc)
            self.stderr = ""

    def _fake_run(cmd, **kwargs):
        seen_calls["cmd"] = cmd
        seen_calls["timeout"] = kwargs.get("timeout")
        return _CompletedProcess()

    monkeypatch.setattr("subprocess.run", _fake_run)

    findings, source = detect_findings(
        scratchpad_dir=scratchpad,
        changed_files=["src/changed.py", "src/other.py"],
    )

    assert source["rung"] == 3
    assert seen_calls["cmd"][0] == "semgrep"
    assert "--sarif" in seen_calls["cmd"]
    assert "--json" in seen_calls["cmd"]
    assert "--quiet" in seen_calls["cmd"]
    assert "--" in seen_calls["cmd"]
    # changed files appear after `--`
    sep = seen_calls["cmd"].index("--")
    assert seen_calls["cmd"][sep + 1:] == ["src/changed.py", "src/other.py"]
    assert seen_calls["timeout"] == 60
    assert any(f["rule_id"] == "ondemand.rule" for f in findings)


def test_no_findings_returns_no_input_verdict(tmp_path, monkeypatch, capsys):
    """AC5 — all rungs fail → TRIAGE_NO_INPUT, no exceptions."""
    monkeypatch.delenv("CLAUDE_SAST_SARIF_PATH", raising=False)
    monkeypatch.delenv("CLAUDE_DISABLE_SAST_TRIAGE", raising=False)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-no-input")
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path / "metrics"))
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()
    _stub_no_semgrep(monkeypatch)

    result = detect_and_triage(
        task_id="t-empty",
        changed_files=["src/x.py"],
        scratchpad_dir=scratchpad,
    )
    assert result["verdict"] == "TRIAGE_NO_INPUT"


def test_semgrep_not_installed_falls_through_silently(tmp_path, monkeypatch, capsys):
    """AC4a — semgrep absent → rung 3 skipped with stderr line; fall-through."""
    monkeypatch.delenv("CLAUDE_SAST_SARIF_PATH", raising=False)
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()
    _stub_no_semgrep(monkeypatch)

    findings, source = detect_findings(
        scratchpad_dir=scratchpad,
        changed_files=["src/x.py"],
    )
    assert source["rung"] == 4
    err = capsys.readouterr().err
    assert "rung=3" in err
    assert "not-installed" in err


def test_semgrep_timeout_falls_through(tmp_path, monkeypatch, capsys):
    """AC4b — semgrep times out → fall-through with stderr."""
    import subprocess

    monkeypatch.delenv("CLAUDE_SAST_SARIF_PATH", raising=False)
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/semgrep")

    def _timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=60)

    monkeypatch.setattr("subprocess.run", _timeout)

    findings, source = detect_findings(
        scratchpad_dir=scratchpad,
        changed_files=["src/x.py"],
    )
    assert source["rung"] == 4
    err = capsys.readouterr().err
    assert "rung=3" in err
    assert "timeout" in err


def test_malformed_sarif_falls_through_to_next_rung(tmp_path, monkeypatch, capsys):
    """AC19 — corrupt rung-1 → fall-through; if all rungs fail to parse, PARSE_FAILED."""
    sarif_path = tmp_path / "corrupt.sarif"
    sarif_path.write_text("{not valid json")
    monkeypatch.setenv("CLAUDE_SAST_SARIF_PATH", str(sarif_path))
    monkeypatch.delenv("CLAUDE_DISABLE_SAST_TRIAGE", raising=False)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-parse-fail")
    monkeypatch.setenv("CLAUDE_METRICS_DIR", str(tmp_path / "metrics"))
    scratchpad = tmp_path / "scratch"
    scratchpad.mkdir()
    _stub_no_semgrep(monkeypatch)

    result = detect_and_triage(
        task_id="t-parse-fail",
        changed_files=["src/x.py"],
        scratchpad_dir=scratchpad,
    )
    assert result["verdict"] == "TRIAGE_PARSE_FAILED"
    err = capsys.readouterr().err
    assert "json-decode-error" in err

    # Telemetry record present for the parse failure
    main_jsonl = tmp_path / "metrics" / "test-parse-fail" / "sast-triage.jsonl"
    assert main_jsonl.exists()
    records = [json.loads(l) for l in main_jsonl.read_text().splitlines() if l.strip()]
    assert any(r.get("verdict") == "PARSE_FAILED" for r in records)
