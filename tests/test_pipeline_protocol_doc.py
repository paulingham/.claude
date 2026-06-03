"""Slice A — canonical-spec doc tests.

These lock the doc invariants: pipeline-protocol.md MUST document the
new layout + 90-day DUAL_PATH soak, and autonomous-intelligence.md
MUST reference the new scratchpad path.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path):
    return (REPO_ROOT / rel_path).read_text()


def test_pipeline_protocol_documents_new_layout():
    content = _read("protocols/pipeline-protocol.md")
    assert "{task-id}/{phase}.md" in content
    assert "90-day" in content
    assert "DUAL_PATH" in content


def test_autonomous_intelligence_scratchpad_path_updated():
    content = _read("protocols/autonomous-intelligence.md")
    assert "pipeline-state/{task-id}/scratchpad/" in content
