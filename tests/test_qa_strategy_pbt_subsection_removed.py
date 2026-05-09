"""AC5.2 — Procedural `### Property-Based Coverage` subsection is removed.

Asserts the procedural subsection (anchored by the body sentence
"Inserted between gap analysis (Step 2 in the qa-engineer prompt)...")
is absent from `skills/qa-test-strategy/SKILL.md`. The Tier-mapping
sentence "PBT tests run as Tier 1.5" is also absent (relocated to
the new /property-based-test skill in Slice 1).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "qa-test-strategy" / "SKILL.md"


def test_procedural_property_based_coverage_subsection_absent():
    body = SKILL_PATH.read_text()
    procedural_anchor = (
        "Inserted between gap analysis (Step 2 in the qa-engineer prompt)")
    assert procedural_anchor not in body, (
        f"Procedural subsection anchor still present in qa-test-strategy "
        f"SKILL.md: {procedural_anchor!r}")
    tier_mapping_anchor = "PBT tests run as **Tier 1.5**"
    assert tier_mapping_anchor not in body, (
        f"Tier-mapping sentence still present in qa-test-strategy "
        f"SKILL.md (it should have been relocated to "
        f"/property-based-test skill): {tier_mapping_anchor!r}")
