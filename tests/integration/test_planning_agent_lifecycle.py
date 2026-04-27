"""Integration test: planning-agent lifecycle (library-level, no live agents)."""
import tempfile
from pathlib import Path
from scratchpad_diff import diff_new_findings, _save_cursor, _load_cursor

# Simulate the full poll-update-broadcast-terminate cycle at the library level

PLAN_CONTENT = """# Wave 3-I Plan

## Slice 1
Modify auth.ts. Assume it has no global state.

## Slice 2
Modify api.ts. Assume it calls auth.ts safely.
"""

FRAGILITY_FINDING = """---
category: fragility
---
auth.ts uses a module-level cache singleton — modifying it affects Slice 2.
"""


def _append_plan_update(plan_path: Path, source: str, category: str,
                        assumption: str, guidance: str, slices: str) -> str:
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    update = (
        f"\n## Plan Update — {ts}\n"
        f"**Source:** {source}\n"
        f"**Category:** {category}\n"
        f"**Invalidated assumption:** {assumption}\n"
        f"**Updated guidance:** {guidance}\n"
        f"**Affected slices:** {slices}\n"
    )
    with plan_path.open("a") as f:
        f.write(update)
    return ts


def test_full_poll_update_broadcast_cycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup
        scratchpad = Path(tmpdir) / "scratchpad"
        scratchpad.mkdir()
        plan_path = Path(tmpdir) / "task-plan.md"
        plan_path.write_text(PLAN_CONTENT)
        cursor_path = Path(tmpdir) / "cursor.json"
        original_bytes = plan_path.read_bytes()

        # Poll 1: no findings yet
        findings = diff_new_findings(scratchpad, cursor_path)
        assert findings == []

        # Slice 1 engineer writes a fragility finding
        (scratchpad / "build-eng-slice1.md").write_text(FRAGILITY_FINDING)

        # Poll 2: fragility found
        findings = diff_new_findings(scratchpad, cursor_path)
        assert len(findings) == 1
        assert findings[0]["category"] == "fragility"

        # planning-agent processes it: append Plan Update
        ts = _append_plan_update(
            plan_path,
            source="build-eng-slice1.md",
            category="fragility",
            assumption="auth.ts has no global state",
            guidance="auth.ts uses a singleton cache; Slice 2 must read auth.ts state before modifying.",
            slices="slice-2",
        )

        # Verify append-only invariant
        after_bytes = plan_path.read_bytes()
        assert after_bytes[:len(original_bytes)] == original_bytes

        # Verify broadcast payload shape
        payload = {
            "type": "plan_update",
            "task_id": "wave3-I",
            "plan_path": str(plan_path),
            "update_section_anchor": f"Plan Update — {ts}",
            "ts": ts,
        }
        assert payload["type"] == "plan_update"
        assert f"Plan Update — {ts}" in plan_path.read_text()

        # Update cursor (simulate agent persisting state)
        seen = _load_cursor(cursor_path)
        for f in findings:
            seen.add((f["filename"], f["content_hash"]))
        _save_cursor(cursor_path, seen)

        # Poll 3: idempotency — same finding not returned again
        findings_again = diff_new_findings(scratchpad, cursor_path)
        assert findings_again == [], "Idempotency: processed finding must not be returned again"


def test_shutdown_verdict_logic():
    """PLAN_REFINED when updates were made; PLAN_UNCHANGED when none."""
    updates_made = 0
    verdict = "PLAN_REFINED" if updates_made > 0 else "PLAN_UNCHANGED"
    assert verdict == "PLAN_UNCHANGED"

    updates_made = 1
    verdict = "PLAN_REFINED" if updates_made > 0 else "PLAN_UNCHANGED"
    assert verdict == "PLAN_REFINED"
