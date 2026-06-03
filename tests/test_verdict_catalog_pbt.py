"""AC3.1 — verdict-catalog has three PBT rows with reason codes.

Asserts the catalog table contains rows for PBT_AUTHORED (success),
PBT_SKIPPED (info), PBT_BLOCKED (failure); emitter is
`property-based-test`; phase is `build`; PBT_SKIPPED downstream-branch
column enumerates all three reason codes; PBT_BLOCKED downstream-branch
column enumerates both reason codes AND names CLAUDE_PBT=0 recovery.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"


def _row_for(verdict, body):
    """Return the matched row text for a given verdict, or None."""
    pattern = re.compile(
        r"^\|\s*`" + re.escape(verdict) + r"`\s*\|.*$",
        re.MULTILINE)
    m = pattern.search(body)
    return m.group(0) if m else None


def test_catalog_has_three_pbt_rows_with_reason_codes():
    body = CATALOG.read_text()
    authored = _row_for("PBT_AUTHORED", body)
    skipped = _row_for("PBT_SKIPPED", body)
    blocked = _row_for("PBT_BLOCKED", body)
    assert authored is not None, "PBT_AUTHORED row missing from verdict-catalog"
    assert skipped is not None, "PBT_SKIPPED row missing from verdict-catalog"
    assert blocked is not None, "PBT_BLOCKED row missing from verdict-catalog"

    # PBT_AUTHORED polarity = success, emitter property-based-test, phase build.
    assert "success" in authored, f"PBT_AUTHORED row wrong polarity: {authored}"
    assert "property-based-test" in authored, (
        f"PBT_AUTHORED emitter wrong: {authored}")
    assert "build" in authored, f"PBT_AUTHORED phase wrong: {authored}"

    # PBT_SKIPPED polarity = info; reason codes enumerated.
    assert "info" in skipped, f"PBT_SKIPPED row wrong polarity: {skipped}"
    for reason in ("env-hatch", "no-candidates", "no-framework-for-language"):
        assert reason in skipped, (
            f"PBT_SKIPPED downstream column missing reason {reason!r}: "
            f"{skipped}")

    # PBT_BLOCKED polarity = failure; reason codes enumerated;
    # CLAUDE_PBT=0 recovery named.
    assert "failure" in blocked, f"PBT_BLOCKED row wrong polarity: {blocked}"
    for reason in ("harness-crash", "unrecoverable-error"):
        assert reason in blocked, (
            f"PBT_BLOCKED downstream column missing reason {reason!r}: "
            f"{blocked}")
    assert "CLAUDE_PBT=0" in blocked, (
        f"PBT_BLOCKED downstream column must name CLAUDE_PBT=0 recovery: "
        f"{blocked}")
