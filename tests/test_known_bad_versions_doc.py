import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "knowledge" / "claude-code-known-bad-versions.md"

def test_known_bad_versions_doc_exists():
    assert DOC.exists(), f"Missing: {DOC}"

def test_known_bad_versions_has_proper_headings():
    body = DOC.read_text()
    assert "# Claude Code Known Bad Versions" in body
    assert "## Tracking Convention" in body
    assert "## Known Issues" in body
