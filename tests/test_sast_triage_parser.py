"""AC6, AC7, AC9, AC10 — parser layer.

- AC6: changed-files-only filter at parse time (NOT triaged, NOT logged).
- AC7: severity normalization (Semgrep + SARIF + unknown).
- AC9: rationale rejection (empty/N-A/<8-token/stop-list).
- AC10: verdict outside {keep, drop, unsure} → unsure with system rationale.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from sast_triage import (
    parse_sarif,
    normalize_severity,
    validate_triage_output,
    _RATIONALE_STOP_LIST,
    _RATIONALE_MIN_TOKENS,
)


def _sarif_with_results(results):
    return {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "Semgrep"}}, "results": results}],
    }


def _result(rule_id, file_uri, line=1, level="error", message="msg"):
    return {
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


def test_findings_outside_changed_files_are_dropped():
    """AC6 — findings whose file is not in changed_files are filtered at parse time."""
    sarif = _sarif_with_results([
        _result("r.in-scope", "src/changed.py", line=10),
        _result("r.out-of-scope", "src/other.py", line=20),
    ])
    findings = parse_sarif(sarif, changed_files=["src/changed.py"])
    rule_ids = [f["rule_id"] for f in findings]
    assert "r.in-scope" in rule_ids
    assert "r.out-of-scope" not in rule_ids


def test_severity_normalization_table(capsys):
    """AC7 — Semgrep + SARIF severity mappings; unknown → INFO + stderr warning."""
    # Semgrep mappings
    assert normalize_severity("ERROR", tool="semgrep") == "CRITICAL"
    assert normalize_severity("WARNING", tool="semgrep") == "HIGH"
    assert normalize_severity("INFO", tool="semgrep") == "LOW"
    # SARIF mappings
    assert normalize_severity("error", tool="sarif") == "HIGH"
    assert normalize_severity("warning", tool="sarif") == "MEDIUM"
    assert normalize_severity("note", tool="sarif") == "LOW"
    assert normalize_severity("none", tool="sarif") == "INFO"
    # Unknown → INFO + stderr warning
    result = normalize_severity("blizzard", tool="sarif")
    assert result == "INFO"
    err = capsys.readouterr().err
    assert "blizzard" in err.lower() or "unknown" in err.lower()


def test_empty_or_na_rationale_force_rewrites_to_unsure():
    """AC9 — empty/whitespace/N-A/stop-list/<8-token rationale → unsure."""
    bad_rationales = [
        "",
        "   ",
        "N/A",
        "n/a",
        "NA",
        "none",
        "-",
        "null",
        "safe",
        "benign",
        "false positive",
        "Looks fine",
        "ok ok ok",  # < 8 tokens after collapse
        "all good here totally",  # 4 tokens
    ]
    for rationale in bad_rationales:
        result = validate_triage_output({"verdict": "drop", "rationale": rationale})
        assert result["verdict"] == "unsure", (
            f"expected unsure for rationale={rationale!r}"
        )
        assert "rejected" in result["rationale"].lower()
        assert "conservatism" in result["rationale"].lower()


def test_valid_long_rationale_preserved():
    """A real ≥8-token rationale outside the stop-list is preserved as-is."""
    rationale = (
        "This is in a test fixture file mocking the database driver, "
        "not production code path."
    )
    result = validate_triage_output({"verdict": "drop", "rationale": rationale})
    assert result["verdict"] == "drop"
    assert result["rationale"] == rationale


def test_invalid_verdict_force_rewrites_to_unsure():
    """AC10 — verdict outside {keep, drop, unsure} → unsure with system rationale."""
    long_rationale = (
        "This finding has been carefully analysed and confirmed to be a "
        "real issue worth tracking."
    )
    for bad_verdict in ["maybe", "yes", "REJECT", "", None, 42]:
        result = validate_triage_output(
            {"verdict": bad_verdict, "rationale": long_rationale}
        )
        assert result["verdict"] == "unsure", (
            f"expected unsure for verdict={bad_verdict!r}"
        )
        assert "rejected" in result["rationale"].lower()


def test_rationale_stop_list_constants_present():
    """Stop-list and threshold are module constants for one-line tuning."""
    assert "safe" in _RATIONALE_STOP_LIST
    assert "false positive" in _RATIONALE_STOP_LIST
    assert _RATIONALE_MIN_TOKENS == 8


def test_force_unsure_preserves_original_rationale_excerpt():
    """LLM-mutant L3 — the system rationale's `(rationale was: ...)` segment
    must contain a prefix of the ORIGINAL rationale, not the verdict string.

    Guards against a swapped-arg mutant `_force_unsure(reason, verdict)`:
    such a mutant would log the verdict string ("maybe-not-real") in the
    `(rationale was: ...)` slot instead of the operator-meaningful prefix
    of the original rationale, destroying audit-trail correctness.
    """
    bogus_verdict = "maybe-not-real"
    original_rationale = (
        "Operator-supplied long rationale text whose first sixty characters "
        "must survive into the system rationale audit trail."
    )
    result = validate_triage_output(
        {"verdict": bogus_verdict, "rationale": original_rationale}
    )
    assert result["verdict"] == "unsure"
    # The excerpt is the original rationale's first 60 chars (post-strip).
    expected_excerpt = original_rationale.strip()[:60]
    assert f"(rationale was: {expected_excerpt})" in result["rationale"]
    # And critically, the verdict string must NOT have been logged in its place.
    assert f"(rationale was: {bogus_verdict})" not in result["rationale"]
    assert bogus_verdict not in result["rationale"].split("(rationale was:")[1]
