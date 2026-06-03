"""AC-A6a: CLAUDE.md Runtime State Location section references HARNESS_ROOT/HARNESS_DATA."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def test_claude_md_runtime_state_references_harness_resolver():
    text = CLAUDE_MD.read_text()
    assert "HARNESS_ROOT" in text or "HARNESS_DATA" in text, (
        'CLAUDE.md missing resolver note: expected "HARNESS_ROOT" or "HARNESS_DATA"'
    )
    assert "hooks/_lib/harness-paths.sh" in text, (
        'CLAUDE.md missing reference to hooks/_lib/harness-paths.sh'
    )
