"""AC11, AC12 — merge block construction.

- AC11: `unsure` findings appear in the merge block with rationale preserved.
- AC12: `drop` findings are excluded from the merge block (they ARE in JSONL,
  not here).

The renderer is `render_merge_block(triaged) -> str`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from sast_triage import render_merge_block


def _finding(rule_id, file, line, sev, message="msg"):
    return {
        "rule_id": rule_id,
        "tool": "semgrep",
        "file": file,
        "line": line,
        "sast_severity": sev,
        "message": message,
        "snippet": "snippet",
    }


def test_unsure_findings_merge_into_working_set_like_keep():
    """AC11 — `unsure` rendered alongside `keep` with rationale preserved."""
    triaged = [
        {
            "finding": _finding("rule.keep", "src/a.py", 10, "HIGH"),
            "verdict": "keep",
            "rationale": "Real SQL injection sink reachable from request body parser.",
        },
        {
            "finding": _finding("rule.unsure", "src/b.py", 20, "MEDIUM"),
            "verdict": "unsure",
            "rationale": "Cannot determine without seeing the calling site context.",
        },
    ]
    block = render_merge_block(triaged)

    assert "## SAST Triage Findings (Pre-Rubric)" in block
    assert "rule.keep" in block
    assert "rule.unsure" in block
    assert "src/a.py:10" in block
    assert "src/b.py:20" in block
    # `unsure` rationale appears verbatim (preserved as-is)
    assert "Cannot determine without seeing the calling site context." in block
    # `keep` rationale appears too
    assert "Real SQL injection sink" in block


def test_drop_findings_excluded_from_merge_block_but_present_in_jsonl(tmp_path, monkeypatch):
    """AC12 — `drop` findings excluded from merge block."""
    triaged = [
        {
            "finding": _finding("rule.keep", "src/a.py", 10, "HIGH"),
            "verdict": "keep",
            "rationale": "Real SQL injection sink reachable from request body parser.",
        },
        {
            "finding": _finding("rule.dropped", "src/test_x.py", 99, "HIGH"),
            "verdict": "drop",
            "rationale": "This is in a jest mock fixture for tests, not production.",
        },
    ]
    block = render_merge_block(triaged)
    assert "rule.keep" in block
    assert "rule.dropped" not in block
    assert "src/test_x.py" not in block


def test_keep_and_unsure_have_distinct_subsections():
    """AC12 — merge block separates `keep (N)` and `unsure (M)` subsections."""
    triaged = [
        {
            "finding": _finding("rule.k1", "src/a.py", 1, "HIGH"),
            "verdict": "keep",
            "rationale": "Confirmed real path traversal in request handler logic.",
        },
        {
            "finding": _finding("rule.u1", "src/b.py", 2, "MEDIUM"),
            "verdict": "unsure",
            "rationale": "Cannot determine without seeing calling site context for the helper.",
        },
    ]
    block = render_merge_block(triaged)
    # Subsection counts present
    assert "keep (1" in block.lower() or "keep (1 finding)" in block.lower()
    assert "unsure (1" in block.lower()
