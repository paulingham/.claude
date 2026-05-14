"""AC1, AC2 — Teammate Prompt Template invariants for instinct-injection-post-breakpoint slice-a.

AC1: `<!-- claude:persona-end -->` sits on its own line immediately after the
three persona-read instructions (skill / patterns / role) and BEFORE the
`**Tool-result fabrication is forbidden.**` line in
`protocols/parallel-dispatch-protocol.md` Teammate Prompt Template.

AC2: Regression lockdown — `## Learned Patterns (from system learning)` continues
to sit between `Subagent depth: {N}` and `## Session Context (engineering notes
for this project)`.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "protocols" / "parallel-dispatch-protocol.md"


def _lines():
    return TEMPLATE.read_text().splitlines()


def _index_of(lines, needle, *, start=0):
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    raise AssertionError(f"needle not found: {needle!r}")


def test_persona_end_marker_present_after_role_read_instruction():
    lines = _lines()
    skill_idx = _index_of(lines, "Read the skill file at ~/.claude/skills/[name]/SKILL.md")
    patterns_idx = _index_of(lines, "Also read ~/.claude/skills/[stack]-patterns/SKILL.md", start=skill_idx)
    role_idx = _index_of(lines, "Read ~/.claude/agents/[role].md", start=patterns_idx)
    tool_idx = _index_of(lines, "**Tool-result fabrication is forbidden.**", start=role_idx)

    marker = "<!-- claude:persona-end -->"
    occurrences = [i for i, line in enumerate(lines) if line.strip() == marker]
    assert len(occurrences) == 1, (
        f"expected exactly one persona-end marker line; found {len(occurrences)}: {occurrences}"
    )
    marker_idx = occurrences[0]
    assert role_idx < marker_idx < tool_idx, (
        f"persona-end marker must sit between role-read (line {role_idx}) "
        f"and Tool-result line (line {tool_idx}); got {marker_idx}"
    )


def test_learned_patterns_block_position_unchanged():
    lines = _lines()
    subagent_depth_idx = _index_of(lines, "Subagent depth: {N}")
    learned_idx = _index_of(lines, "## Learned Patterns (from system learning)", start=subagent_depth_idx)
    session_idx = _index_of(lines, "## Session Context (engineering notes for this project)", start=learned_idx)
    assert subagent_depth_idx < learned_idx < session_idx, (
        f"Learned Patterns block must sit between Subagent depth (line {subagent_depth_idx}) "
        f"and Session Context (line {session_idx}); got {learned_idx}"
    )
