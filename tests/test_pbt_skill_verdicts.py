"""AC1.4 — `/property-based-test` skill emits exactly three verdicts.

Asserts the `## Verdict` section names PBT_AUTHORED, PBT_SKIPPED,
PBT_BLOCKED with explicit conditions; PBT_SKIPPED enumerates three
reason codes; PBT_BLOCKED enumerates two reason codes.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"

VERDICTS = ("PBT_AUTHORED", "PBT_SKIPPED", "PBT_BLOCKED")
SKIPPED_REASONS = ("env-hatch", "no-candidates", "no-framework-for-language")
BLOCKED_REASONS = ("harness-crash", "unrecoverable-error")


def test_skill_emits_three_named_verdicts_with_reason_codes():
    body = SKILL_PATH.read_text()
    assert "## Verdict" in body, (
        "property-based-test SKILL.md missing `## Verdict` section")
    missing_verdicts = [v for v in VERDICTS if v not in body]
    assert not missing_verdicts, (
        f"property-based-test SKILL.md missing verdicts: {missing_verdicts!r}")
    missing_skipped = [r for r in SKIPPED_REASONS if r not in body]
    assert not missing_skipped, (
        f"property-based-test SKILL.md missing PBT_SKIPPED reason codes: "
        f"{missing_skipped!r}")
    missing_blocked = [r for r in BLOCKED_REASONS if r not in body]
    assert not missing_blocked, (
        f"property-based-test SKILL.md missing PBT_BLOCKED reason codes: "
        f"{missing_blocked!r}")
