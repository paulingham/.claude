"""AC5.7 — qa-engineer self-review accepts BOTH pointer forms during deprecation window.

Asserts:
- A `Deprecation Window` subsection exists in qa-engineer.md.
- BOTH pointer substrings are present:
  - new: `skills/property-based-test/SKILL.md`
  - legacy: `skills/qa-test-strategy/SKILL.md § Property-Based Coverage`
- The soak-deadline string `30-day soak` is present.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "qa-engineer.md"


def test_qa_engineer_self_review_accepts_both_pointer_forms():
    body = AGENT_PATH.read_text()
    has_deprecation_section = bool(
        re.search(r"^#+\s+Deprecation Window", body,
                  re.MULTILINE | re.IGNORECASE))
    assert has_deprecation_section, (
        "qa-engineer must have a `Deprecation Window` subsection")
    assert "skills/property-based-test/SKILL.md" in body, (
        "qa-engineer must include the new pointer "
        "`skills/property-based-test/SKILL.md`")
    legacy = "skills/qa-test-strategy/SKILL.md § Property-Based Coverage"
    assert legacy in body, (
        f"qa-engineer must retain the legacy pointer during deprecation "
        f"window: {legacy!r}")
    assert "30-day soak" in body, (
        "qa-engineer Deprecation Window must name the 30-day soak deadline")
