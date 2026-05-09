"""AC1.5 — `/property-based-test` skill documents the CLAUDE_PBT=0 env hatch.

Asserts the skill contains literal `CLAUDE_PBT=0` text within an escape-hatch
subsection styled like `build-implementation:77` (`**Escape hatch.**` heading
form, ≤5-line body).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"


def _extract_escape_hatch_block(body):
    """Return the lines following `**Escape hatch.**` up to the next blank line."""
    lines = body.splitlines()
    block = []
    in_block = False
    for line in lines:
        if "**Escape hatch.**" in line:
            in_block = True
        if in_block:
            if not line.strip() and block:
                break
            block.append(line)
    return block


def test_skill_documents_claude_pbt_env_hatch():
    body = SKILL_PATH.read_text()
    assert "CLAUDE_PBT=0" in body, (
        "property-based-test SKILL.md missing literal `CLAUDE_PBT=0`")
    assert "**Escape hatch.**" in body, (
        "property-based-test SKILL.md missing `**Escape hatch.**` marker "
        "(style mirroring build-implementation:77)")
    block = _extract_escape_hatch_block(body)
    assert block, "Could not locate escape-hatch block"
    assert len(block) <= 5, (
        f"escape-hatch block must be ≤5 lines (mirroring build-implementation:77 "
        f"style), got {len(block)} lines: {block!r}")
    block_text = "\n".join(block)
    assert "CLAUDE_PBT=0" in block_text, (
        "the escape-hatch block must reference CLAUDE_PBT=0")
