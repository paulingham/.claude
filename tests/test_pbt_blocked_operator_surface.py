"""AC1.4b — `PBT_BLOCKED` operator-visible payload contract.

Asserts the skill body documents the four required operator surfaces:
function name, 5-line error excerpt, `CLAUDE_PBT=0` recovery action,
and the explicit non-counting clause referencing
`rules/_detail/operational-protocol.md` retry-twice-then-escalate.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"

REQUIRED_MARKERS = (
    "function name",  # candidate function name surface
    "5 line",         # 5-line error excerpt (allow "5 line" or "5-line")
    "CLAUDE_PBT=0",   # recommended recovery
    "retry-twice",    # explicit reference to retry-twice budget exemption
    "rules/_detail/operational-protocol.md",  # cite the rule file
)


def test_pbt_blocked_payload_documents_operator_surface_and_retry_exemption():
    body = SKILL_PATH.read_text()
    # tolerate "5-line" or "5 line"
    body_normalised = body.replace("5-line", "5 line")
    missing = [m for m in REQUIRED_MARKERS if m not in body_normalised]
    assert not missing, (
        f"property-based-test SKILL.md PBT_BLOCKED operator surface "
        f"missing markers: {missing!r}")
