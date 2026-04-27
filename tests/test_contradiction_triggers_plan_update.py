"""Test: contradiction detection via scratchpad findings triggers plan update format."""
import tempfile
from pathlib import Path
from scratchpad_diff import diff_new_findings

FRAGILITY_FINDING = """---
category: fragility
---
auth.ts mutates global state via a singleton — the plan calls it 'safe to modify in isolation'.
"""


def test_fragility_finding_is_surfaced():
    """A fragility finding in scratchpad is returned by diff_new_findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        scratchpad = Path(tmpdir) / "scratchpad"
        scratchpad.mkdir()
        (scratchpad / "build-eng-slice1.md").write_text(FRAGILITY_FINDING)
        cursor = Path(tmpdir) / "cursor.json"
        findings = diff_new_findings(scratchpad, cursor)
        assert len(findings) == 1
        assert findings[0]["category"] == "fragility"


def test_plan_update_format_is_valid():
    """The Plan Update format (as defined in SKILL.md) is a valid markdown section."""
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    update = (
        f"\n## Plan Update — {ts}\n"
        f"**Source:** build-eng-slice1.md\n"
        f"**Category:** fragility\n"
        f"**Invalidated assumption:** auth.ts is safe to modify\n"
        f"**Updated guidance:** auth.ts uses a singleton; coordinate with Slice 2 before modifying.\n"
        f"**Affected slices:** slice-2\n"
    )
    assert update.startswith("\n## Plan Update —"), "Plan Update must start with the required heading"
    assert "**Source:**" in update
    assert "**Category:**" in update
    assert "**Invalidated assumption:**" in update
    assert "**Updated guidance:**" in update


def test_warning_finding_is_surfaced():
    """A warning category finding is surfaced (warnings trigger plan updates per rubric)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        scratchpad = Path(tmpdir) / "scratchpad"
        scratchpad.mkdir()
        content = "---\ncategory: warning\n---\nPayment handler has a race on concurrent writes.\n"
        (scratchpad / "build-eng-slice2.md").write_text(content)
        cursor = Path(tmpdir) / "cursor.json"
        findings = diff_new_findings(scratchpad, cursor)
        assert findings[0]["category"] == "warning"
