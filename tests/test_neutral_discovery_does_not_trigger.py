"""Test: neutral discoveries do NOT trigger plan updates (per contradiction rubric)."""
import tempfile
from pathlib import Path
from scratchpad_diff import diff_new_findings

NEUTRAL_DISCOVERY = """---
category: discovery
---
This project uses barrel exports in src/index.ts — not mentioned in the plan but not contradictory.
"""


def test_neutral_discovery_surfaced_but_not_a_contradiction():
    """A neutral discovery is surfaced by diff_new_findings (surfacing != contradiction).

    The planning-agent decides whether to trigger a plan update via its rubric.
    This test confirms the finding IS returned (so the agent can evaluate it)
    but with category 'discovery' — which per the rubric triggers only on
    precondition invalidation, not on neutral observations.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        scratchpad = Path(tmpdir) / "scratchpad"
        scratchpad.mkdir()
        (scratchpad / "build-eng.md").write_text(NEUTRAL_DISCOVERY)
        cursor = Path(tmpdir) / "cursor.json"
        findings = diff_new_findings(scratchpad, cursor)
        assert len(findings) == 1
        assert findings[0]["category"] == "discovery"
        # The agent decides whether this triggers — the rubric says neutral discoveries do NOT.
        # We document that expectation here without mocking the LLM.
        assert findings[0]["category"] != "fragility"
        assert findings[0]["category"] != "warning"


def test_pattern_finding_never_triggers():
    """Pattern findings have category 'pattern' — never trigger per rubric."""
    with tempfile.TemporaryDirectory() as tmpdir:
        scratchpad = Path(tmpdir) / "scratchpad"
        scratchpad.mkdir()
        content = "---\ncategory: pattern\n---\nComposition X->Y->Z works well.\n"
        (scratchpad / "build-eng.md").write_text(content)
        findings = diff_new_findings(scratchpad, Path(tmpdir) / "cursor.json")
        assert findings[0]["category"] == "pattern"
