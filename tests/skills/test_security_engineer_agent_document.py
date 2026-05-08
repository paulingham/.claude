"""AC17 — agent markdown declares A00 checklist hook.

`agents/security-engineer.md` MUST:
  - declare an A00 checklist hook
  - reference the merge block ('SAST Triage Findings' or '## Findings')
  - instruct the agent to consume `keep` + `unsure` findings
  - allow downgrade-with-rationale BUT FORBID deletion (literal 'MUST NOT delete')
  - reference the bypass switch (`CLAUDE_DISABLE_SAST_TRIAGE`)
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_PATH = REPO_ROOT / "agents" / "security-engineer.md"


@pytest.fixture(scope="module")
def agent_text():
    return AGENT_PATH.read_text()


def test_agent_declares_a00_hook(agent_text):
    assert "A00" in agent_text


def test_agent_references_sast_triage_findings_block(agent_text):
    assert "SAST Triage Findings" in agent_text


def test_agent_instructs_consumption_of_keep_and_unsure(agent_text):
    """Both `keep` and `unsure` must be addressed."""
    assert "keep" in agent_text and "unsure" in agent_text


def test_agent_forbids_deletion_with_literal_must_not_delete(agent_text):
    """AC17 — 'MUST NOT delete' is the literal phrase required."""
    assert "MUST NOT delete" in agent_text


def test_agent_allows_downgrade_with_rationale(agent_text):
    assert "downgrade" in agent_text.lower() and "rationale" in agent_text.lower()


def test_agent_references_bypass_switch(agent_text):
    assert "CLAUDE_DISABLE_SAST_TRIAGE" in agent_text


def test_agent_documents_agent_verdict_token(agent_text):
    """AC18 hybrid — agent_verdict: confirmed | downgraded."""
    assert "agent_verdict" in agent_text
    assert "confirmed" in agent_text.lower()
    assert "downgraded" in agent_text.lower()


def test_agent_forbids_not_applicable_for_triage_findings(agent_text):
    """AC18 — `not-applicable` FORBIDDEN as agent_verdict for triage-originating findings."""
    assert "not-applicable" in agent_text.lower() or "not applicable" in agent_text.lower()
    # FORBID is literal in plan section 6.2 / 6.3
    assert "forbidden" in agent_text.lower() or "must not" in agent_text.lower() or "MUST NOT" in agent_text
