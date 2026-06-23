"""Slice 1b → Slice 2 update — CI-watch + enforcing gate in Definition of Done.

Slice 1 (AC9): DoD gained an advisory CI-watch line.
Slice 2: the advisory qualifier is FLIPPED to enforcing — 'CI-green gate passed'
replaces 'does not yet block'. This test is updated to reflect the enforcing state.

The test still verifies the DoD mentions CI-watch/CI-green gate and that no
advisory-only qualifier remains. Goes RED if the enforcing wording is reverted
to the Slice 1 advisory form.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = REPO_ROOT / "protocols" / "pipeline-protocol.md"


def _dod_section(text):
    """Extract the Definition of Done section text."""
    m = re.search(
        r"(## Definition of Done\b.+?)(?=\n## |\Z)",
        text,
        re.DOTALL,
    )
    return m.group(1) if m else None


def test_dod_has_advisory_ci_watch_line():
    """Slice 2: DoD has enforcing CI-green gate line (not advisory-only from Slice 1).

    Verifies:
    - DoD mentions CI-green gate (enforcing gate passed before Deploy).
    - DoD does NOT say 'does not yet block' or 'enforcing gate is tracked separately'
      (advisory-only qualifiers from Slice 1 must be gone).
    """
    text = PROTOCOL.read_text()
    dod = _dod_section(text)
    assert dod is not None, (
        "protocols/pipeline-protocol.md must have a '## Definition of Done' section"
    )

    ci_gate_present = any(
        kw in dod
        for kw in ("CI-green gate", "ci-green gate", "CI_GREEN", "gh pr checks")
    )
    assert ci_gate_present, (
        "Definition of Done must contain a CI-green gate line (enforcing, Slice 2). "
        "None found in DoD section."
    )

    # Enforcing state: advisory-only qualifiers must be gone
    assert "does not yet block" not in dod, (
        "DoD still says 'does not yet block' — Slice 2 must flip this to enforcing."
    )
    assert "enforcing gate is tracked separately" not in dod, (
        "DoD still says 'enforcing gate is tracked separately' — Slice 2 must flip this."
    )
