"""AC5.3 — QA Checklist PBT bullets are preserved verbatim.

Asserts both checklist bullets are present byte-for-byte in the
post-edit file, located by content match (NOT line number).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "qa-test-strategy" / "SKILL.md"

CHECKLIST_BULLET_1 = (
    "PBT run produced ≥ 1 property per public function on changed lines, "
    "OR a documented justification why a property is impossible")
CHECKLIST_BULLET_2 = (
    "Frozen counterexamples from PBT runs are captured as deterministic "
    "unit tests (`@example` / seeded `fc.assert`)")


def test_qa_checklist_pbt_items_preserved_verbatim():
    body = SKILL_PATH.read_text()
    assert CHECKLIST_BULLET_1 in body, (
        f"QA Checklist bullet 1 must be preserved byte-for-byte: "
        f"{CHECKLIST_BULLET_1!r}")
    assert CHECKLIST_BULLET_2 in body, (
        f"QA Checklist bullet 2 must be preserved byte-for-byte: "
        f"{CHECKLIST_BULLET_2!r}")
