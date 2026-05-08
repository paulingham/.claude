"""AC16 — skill markdown documents the operator-surface contract.

`skills/security-review/SKILL.md` MUST contain a § 0 (or equivalent
numbered section) with:
  - `CLAUDE_DISABLE_SAST_TRIAGE` bypass switch
  - `CLAUDE_SAST_SARIF_PATH` operator override
  - 4-rung detection ladder (rungs 1, 2, 3, 4 each named)
  - Severity normalization table (Semgrep ERROR → CRITICAL etc.)
  - JSONL schema fields (rule_id, tool, file, line, verdict, rationale_excerpt,
    rationale_full_hash)
  - Per-finding triage prompt template (the agent's iteration loop is here)
  - Strict-JSON output contract (verdict ∈ {keep, drop, unsure})
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "security-review" / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text():
    return SKILL_PATH.read_text()


def test_skill_documents_bypass_switch(skill_text):
    assert "CLAUDE_DISABLE_SAST_TRIAGE" in skill_text


def test_skill_documents_pre_staged_sarif_path(skill_text):
    assert "CLAUDE_SAST_SARIF_PATH" in skill_text


def test_skill_documents_four_rung_ladder(skill_text):
    """Four rungs each named explicitly."""
    assert "rung 1" in skill_text.lower() or "rung-1" in skill_text.lower()
    assert "rung 2" in skill_text.lower() or "rung-2" in skill_text.lower()
    assert "rung 3" in skill_text.lower() or "rung-3" in skill_text.lower()
    assert "rung 4" in skill_text.lower() or "rung-4" in skill_text.lower()


def test_skill_documents_severity_normalization_table(skill_text):
    """Severity normalization for Semgrep + SARIF inputs."""
    assert "ERROR" in skill_text and "CRITICAL" in skill_text
    assert "WARNING" in skill_text and "HIGH" in skill_text
    assert "warning" in skill_text and "MEDIUM" in skill_text  # SARIF
    assert "note" in skill_text and "LOW" in skill_text  # SARIF


def test_skill_documents_jsonl_schema(skill_text):
    """JSONL field names referenced in skill body."""
    for field in ["rule_id", "tool", "file", "line", "verdict",
                  "rationale_excerpt", "rationale_full_hash"]:
        assert field in skill_text, f"JSONL field {field!r} missing"


def test_skill_documents_iteration_template_with_strict_json(skill_text):
    """AC8 — § 0.3 contains 'for each finding' iteration text + strict-JSON output."""
    assert "for each finding" in skill_text.lower() or "per finding" in skill_text.lower()
    # Strict-JSON output contract: verdict enum
    assert "keep" in skill_text and "drop" in skill_text and "unsure" in skill_text


def test_skill_documents_triage_section_zero_pre_rubric(skill_text):
    """§ 0 named explicitly; runs BEFORE OWASP rubric."""
    # Section header — accept either '## §' or '## 0' or 'Section 0' style
    assert "§ 0" in skill_text or "## 0" in skill_text or "Section 0" in skill_text
    # Pre-rubric ordering documented
    assert "pre-rubric" in skill_text.lower() or "before" in skill_text.lower()


def test_skill_documents_triage_parse_failed_distinct_from_no_input(skill_text):
    """AC19 — TRIAGE_PARSE_FAILED distinct from TRIAGE_NO_INPUT."""
    assert "TRIAGE_PARSE_FAILED" in skill_text
    assert "TRIAGE_NO_INPUT" in skill_text


def test_skill_documents_bypass_jsonl_ledger(skill_text):
    """AC20 — distinct bypass ledger path."""
    assert "sast-triage-bypass.jsonl" in skill_text
