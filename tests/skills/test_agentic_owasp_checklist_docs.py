"""WS-B — SKILL.md and agent.md document the Agentic OWASP Top 10 checklist
and its gating contract.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "security-review" / "SKILL.md"
AGENT = REPO_ROOT / "agents" / "security-engineer.md"


@pytest.fixture(scope="module")
def skill_text():
    return SKILL.read_text()


@pytest.fixture(scope="module")
def agent_text():
    return AGENT.read_text()


FOUR_THREATS = ["memory poisoning", "instinct poisoning", "tool misuse", "goal hijacking"]


@pytest.mark.parametrize("threat", FOUR_THREATS)
def test_agent_names_each_agentic_threat(agent_text, threat):
    assert threat in agent_text.lower(), f"agent.md missing agentic threat: {threat}"


@pytest.mark.parametrize("threat", FOUR_THREATS)
def test_skill_names_each_agentic_threat(skill_text, threat):
    assert threat in skill_text.lower(), f"SKILL.md missing agentic threat: {threat}"


def test_agent_has_agentic_owasp_section(agent_text):
    assert "OWASP Top 10 for Agentic Applications" in agent_text
    for code in ["AA01", "AA02", "AA03", "AA04"]:
        assert code in agent_text


def test_agent_documents_three_gated_surfaces(agent_text):
    for surface in ["learning/", "agent-memory/", "hooks/"]:
        assert surface in agent_text


def test_skill_documents_agentic_surface_gate(skill_text):
    assert "Agentic Surface Gate" in skill_text
    for surface in ["learning/", "agent-memory/", "hooks/"]:
        assert surface in skill_text


def test_skill_documents_bypass_env_var(skill_text):
    assert "CLAUDE_DISABLE_AGENTIC_GATE" in skill_text


def test_agent_references_bypass_env_var(agent_text):
    assert "CLAUDE_DISABLE_AGENTIC_GATE" in agent_text
