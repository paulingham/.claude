"""Slice 1b — Verify advisory CI-watch line in Definition of Done.

AC9: protocols/pipeline-protocol.md Definition of Done carries an advisory
     CI-watch line that contains 'advisory' and a not-a-gate qualifier
     ('does not … block' / 'not yet block' / 'does not gate').

Goes RED before the line is added (DoD has no CI-watch item),
GREEN after the line lands.
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
    """AC9: DoD contains an advisory CI-watch line with 'advisory' + not-a-gate qualifier."""
    text = PROTOCOL.read_text()
    dod = _dod_section(text)
    assert dod is not None, (
        "protocols/pipeline-protocol.md must have a '## Definition of Done' section"
    )

    ci_watch_present = any(
        kw in dod
        for kw in ("gh pr checks", "CI-watch", "CI watch", "remote CI")
    )
    assert ci_watch_present, (
        "Definition of Done must contain an advisory CI-watch line naming "
        "'gh pr checks' or 'CI-watch' or 'remote CI'. "
        "None found in DoD section."
    )

    assert "advisory" in dod, (
        "The CI-watch DoD line must contain the word 'advisory' to signal "
        "this is not yet a blocking gate."
    )

    not_a_gate_present = any(
        kw in dod
        for kw in (
            "does not", "not yet block", "not block", "does not gate",
            "does not yet block", "not a block", "non-blocking",
        )
    )
    assert not_a_gate_present, (
        "The CI-watch DoD line must include a not-a-gate qualifier such as "
        "'does not … block' or 'not yet block Ship→Deploy'. "
        "CI-watch is ADVISORY in Slice 1."
    )
