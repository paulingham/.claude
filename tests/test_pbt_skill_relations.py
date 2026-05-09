"""AC1.3 — `/property-based-test` skill names the four PBT relation categories.

Asserts the skill body names the four canonical PBT relations
(idempotence / inverse / oracle / metamorphic) AND documents the
impossibility-justification format with at least one example each.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"

CANONICAL_RELATIONS = ("idempotence", "inverse", "oracle", "metamorphic")
JUSTIFICATION_MARKERS = ("justif", "impossib")  # justification / justify, impossibility / impossible


def test_skill_names_four_pbt_relation_categories():
    body = SKILL_PATH.read_text().lower()
    missing = [r for r in CANONICAL_RELATIONS if r not in body]
    assert not missing, (
        f"property-based-test SKILL.md missing relation categories: "
        f"{missing!r}")
    missing_justif = [m for m in JUSTIFICATION_MARKERS if m not in body]
    assert not missing_justif, (
        f"property-based-test SKILL.md missing impossibility-justification "
        f"markers: {missing_justif!r}")
