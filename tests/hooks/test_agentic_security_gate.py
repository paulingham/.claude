"""WS-B — gating trigger for the Agentic OWASP Top 10 security checklist.

The gate fires when a `security-engineer` agent is spawned over a diff that
touches an agentic-control surface (`learning/`, `agent-memory/`, `hooks/`).
When it fires, the spawn prompt MUST direct the reviewer to apply the Agentic
OWASP Top 10 checklist (memory poisoning, instinct poisoning, tool misuse,
goal hijacking); otherwise the spawn is blocked.

These tests exercise the pure gating logic in
`hooks/_lib/agentic_security_gate.py` directly — no subprocess required.
The conftest at tests/conftest.py prepends hooks/_lib to sys.path.
"""
import pytest

from agentic_security_gate import (
    AGENTIC_SURFACE_PREFIXES,
    gate_decision,
    prompt_satisfies_gate,
    touches_agentic_surface,
)


@pytest.mark.parametrize(
    "changed_file,expected",
    [
        ("learning/instincts/security-engineer.md", "learning"),
        ("agent-memory/code-reviewer/MEMORY.md", "agent-memory"),
        ("hooks/agentic-security-gate.sh", "hooks"),
        ("hooks/_lib/agentic_security_gate.py", "hooks"),
    ],
)
def test_single_agentic_surface_file_triggers(changed_file, expected):
    assert touches_agentic_surface([changed_file]) == [expected]


def test_no_agentic_surface_files_does_not_trigger():
    files = ["src/app.py", "README.md", "skills/security-review/SKILL.md"]
    assert touches_agentic_surface(files) == []


def test_empty_changeset_does_not_trigger():
    assert touches_agentic_surface([]) == []


def test_multiple_surfaces_dedup_and_sorted():
    files = [
        "hooks/foo.sh",
        "learning/instincts/x.md",
        "agent-memory/y/MEMORY.md",
        "hooks/bar.sh",
        "src/unrelated.py",
    ]
    assert touches_agentic_surface(files) == ["agent-memory", "hooks", "learning"]


def test_leading_dot_slash_is_normalized():
    assert touches_agentic_surface(["./hooks/foo.sh"]) == ["hooks"]


def test_substring_lookalike_does_not_falsely_trigger():
    files = [
        "src/learning_helpers.py",
        "docs/hooks-guide.md",
        "lib/agent-memory-notes.txt",
    ]
    assert touches_agentic_surface(files) == []


def test_whitespace_lines_are_ignored():
    assert touches_agentic_surface(["", "  ", "hooks/x.sh"]) == ["hooks"]


def test_surface_prefixes_constant_is_the_three_documented_roots():
    assert set(AGENTIC_SURFACE_PREFIXES) == {"learning/", "agent-memory/", "hooks/"}


@pytest.mark.parametrize(
    "prompt",
    [
        "Apply the Agentic OWASP Top 10 checklist.",
        "Run the AGENTIC OWASP review including memory poisoning.",
        "Goal hijacking + tool misuse — see Agentic OWASP § agent control plane.",
    ],
)
def test_prompt_with_agentic_directive_satisfies(prompt):
    assert prompt_satisfies_gate(prompt) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "Standard OWASP Top 10 review of the diff.",
        "",
        "Look for SQL injection and XSS.",
        # Key regression: mentions the filename but NOT the phrase "agentic owasp"
        "Review hooks/agentic-security-gate.sh for issues.",
    ],
)
def test_prompt_without_agentic_directive_fails(prompt):
    assert prompt_satisfies_gate(prompt) is False


def test_decision_allows_when_no_agentic_surface_touched():
    d = gate_decision(["src/app.py"], "any prompt", subagent_type="security-engineer")
    assert d["action"] == "allow"
    assert d["surfaces"] == []


def test_decision_blocks_when_surface_touched_and_prompt_lacks_directive():
    d = gate_decision(
        ["hooks/x.sh"], "Standard OWASP review", subagent_type="security-engineer"
    )
    assert d["action"] == "block"
    assert d["surfaces"] == ["hooks"]
    assert "agentic" in d["reason"].lower()


def test_decision_allows_when_surface_touched_and_prompt_has_directive():
    d = gate_decision(
        ["hooks/x.sh"],
        "Apply the Agentic OWASP Top 10 checklist for this diff.",
        subagent_type="security-engineer",
    )
    assert d["action"] == "allow"
    assert d["surfaces"] == ["hooks"]


def test_decision_blocks_when_prompt_has_filename_but_not_phrase():
    d = gate_decision(
        ["hooks/x.sh"],
        "Review hooks/agentic-security-gate.sh for issues.",
        subagent_type="security-engineer",
    )
    assert d["action"] == "block"


def test_decision_ignores_non_security_engineer_agents():
    d = gate_decision(
        ["hooks/x.sh"], "Standard review", subagent_type="software-engineer"
    )
    assert d["action"] == "allow"


def test_decision_bypass_flag_forces_allow_even_when_would_block():
    d = gate_decision(
        ["hooks/x.sh"],
        "Standard OWASP review",
        subagent_type="security-engineer",
        disabled=True,
    )
    assert d["action"] == "bypass"
    assert d["surfaces"] == ["hooks"]


# Finding 7 — _normalize path traversal tests
def test_normalize_collapses_dotdot_traversal():
    assert touches_agentic_surface(["src/../hooks/x.sh"]) == ["hooks"]


def test_normalize_external_dotdot_does_not_trigger():
    assert touches_agentic_surface(["../hooks/x.sh"]) == []


def test_normalize_leading_dot_slash_still_works():
    assert touches_agentic_surface(["./hooks/x.sh"]) == ["hooks"]
