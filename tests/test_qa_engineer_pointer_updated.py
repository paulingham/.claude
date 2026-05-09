"""AC5.5 — qa-engineer self-review pointer updated; instinct_categories unchanged.

Asserts:
- Self-review item 4 contains substring `skills/property-based-test/SKILL.md`
- Frontmatter `instinct_categories` snapshot still contains `property-testing`
  (qa-engineer still verifies PBT coverage at Final Gate).
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "qa-engineer.md"


def _parse_frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, f"{path} has no YAML frontmatter block"
    return yaml.safe_load(match.group(1))


def test_qa_engineer_self_review_pointer_and_instincts_unchanged():
    body = AGENT_PATH.read_text()
    assert "skills/property-based-test/SKILL.md" in body, (
        "qa-engineer self-review pointer must reference "
        "skills/property-based-test/SKILL.md (the new home of the procedure)")
    fm = _parse_frontmatter(AGENT_PATH)
    instinct_categories = fm.get("instinct_categories") or []
    assert "property-testing" in instinct_categories, (
        f"qa-engineer instinct_categories must still contain "
        f"'property-testing' (qa-engineer still verifies PBT coverage at "
        f"Final Gate); got {instinct_categories}")
