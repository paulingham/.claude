"""AC18 — review-output preservation contract (hybrid enforcement).

For every `keep` and `unsure` finding originally surfaced by triage:
  1. Line referencing the finding (containing both `rule_id` AND `file:line`)
     appears UNDER `## Findings` heading.
  2. Line MUST NOT appear under any heading whose text matches case-insensitive
     regex `(dismissed|skipped|not.applicable|not.a.finding|ignored|suppressed|out.of.scope)`.
  3. Line MUST NOT be wrapped in markdown strikethrough (`~~...~~`).
  4. Within ±5 lines of each finding line, an `agent_verdict:` token must
     equal `confirmed` or `downgraded`. `not-applicable` is FORBIDDEN.

Uses `tests/_helpers/markdown_section_walker.py` to walk heading stacks.
"""
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from _helpers.markdown_section_walker import (
    lines_under_heading,
    lines_under_any_heading_matching,
)
from sast_triage import audit_agent_output


FIXTURE_CLEAN = REPO_ROOT / "tests" / "fixtures" / "sast_triage" / "agent_output_clean.md"
FIXTURE_BYPASS = REPO_ROOT / "tests" / "fixtures" / "sast_triage" / "agent_output_bypass_attempt.md"

DISMISS_RE = re.compile(
    r"(dismissed|skipped|not.applicable|not.a.finding|ignored|suppressed|out.of.scope)",
    re.IGNORECASE,
)


def test_clean_fixture_passes_audit_for_two_findings():
    """Findings present under ## Findings, with valid agent_verdict tokens."""
    text = FIXTURE_CLEAN.read_text()
    triage_findings = [
        {"rule_id": "rules.py.security.sql-injection", "file": "src/queries.py", "line": 42},
        {"rule_id": "rules.py.security.weak-hash", "file": "src/auth.py", "line": 88},
    ]
    result = audit_agent_output(text, triage_findings)
    assert result["ok"] is True, f"audit failed: {result}"
    assert result["violations"] == []


def test_bypass_fixture_fails_audit():
    """Findings under suppressed/strikethrough headings → audit fails."""
    text = FIXTURE_BYPASS.read_text()
    triage_findings = [
        {"rule_id": "rules.py.security.weak-hash", "file": "src/auth.py", "line": 88},
        {"rule_id": "rules.py.security.lfi", "file": "src/files.py", "line": 11},
    ]
    result = audit_agent_output(text, triage_findings)
    assert result["ok"] is False
    # Both findings should be flagged
    assert len(result["violations"]) >= 1


def test_audit_detects_dismissed_heading():
    """Finding line living under a dismissal heading fails."""
    md = """# Review

## Findings

- nothing here

## Dismissed

- **rule.x** `src/y.py:10` — agent_verdict: confirmed
"""
    result = audit_agent_output(md, [{"rule_id": "rule.x", "file": "src/y.py", "line": 10}])
    assert result["ok"] is False


def test_audit_detects_strikethrough():
    """Finding wrapped in ~~...~~ containing rule_id fails."""
    md = """# Review

## Findings

- ~~**rule.y** `src/z.py:5` — agent_verdict: confirmed~~
"""
    result = audit_agent_output(md, [{"rule_id": "rule.y", "file": "src/z.py", "line": 5}])
    assert result["ok"] is False


def test_audit_requires_agent_verdict_within_five_lines():
    """No agent_verdict: token within ±5 lines → audit fails."""
    md = """# Review

## Findings

- **rule.z** `src/a.py:1` — described here
- some other line
- and another
- still no token
- final
- another line
- another line
- another line  <-- agent_verdict: confirmed (more than 5 below)
"""
    result = audit_agent_output(md, [{"rule_id": "rule.z", "file": "src/a.py", "line": 1}])
    assert result["ok"] is False


def test_audit_forbids_not_applicable_agent_verdict():
    """`agent_verdict: not-applicable` is FORBIDDEN for triage-originating findings."""
    md = """# Review

## Findings

- **rule.q** `src/a.py:1` — agent_verdict: not-applicable
"""
    result = audit_agent_output(md, [{"rule_id": "rule.q", "file": "src/a.py", "line": 1}])
    assert result["ok"] is False


def test_audit_accepts_downgraded_verdict():
    md = """# Review

## Findings

- **rule.p** `src/a.py:1` — agent_verdict: downgraded
  - rationale: this is only used for cache key, not auth
"""
    result = audit_agent_output(md, [{"rule_id": "rule.p", "file": "src/a.py", "line": 1}])
    assert result["ok"] is True


def test_walker_finds_lines_under_findings_heading():
    text = FIXTURE_CLEAN.read_text()
    matches = lines_under_heading(text, "Findings", level=2)
    assert any("rules.py.security.sql-injection" in line for _idx, line in matches)


def test_walker_detects_dismissal_headings():
    text = FIXTURE_BYPASS.read_text()
    matches = lines_under_any_heading_matching(text, DISMISS_RE)
    assert any("rules.py.security.weak-hash" in line for _idx, line in matches)
