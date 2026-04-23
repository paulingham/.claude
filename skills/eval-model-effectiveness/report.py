"""Top-level report renderer (combines summary + evidence + apply)."""
from __future__ import annotations

from evidence import evidence_block
from models import CellDecision
from summary import summary_line

HOW_TO_APPLY = """== How to apply ==
To adopt a recommendation:
1. Open ~/.claude/agents/{role}.md
2. Update the frontmatter `model:` field (e.g. `model: sonnet`)
3. Commit as a harness-config change.
The orchestrator does NOT auto-apply recommendations. Review evidence, then decide.
"""


def _evidence_section(decisions: list[CellDecision]) -> list[str]:
    non_locked = [d for d in decisions if d.verdict not in ("LOCKED", "INSUFFICIENT_DATA")]
    if not non_locked:
        return ["(no evidence — all cells insufficient or locked)"]
    out: list[str] = []
    for d in non_locked:
        out.extend(evidence_block(d))
    return out


def render_report(decisions: list[CellDecision]) -> str:
    lines = ["== Summary =="]
    lines.extend(summary_line(d) for d in decisions)
    lines.append("")
    lines.append("== Evidence ==")
    lines.extend(_evidence_section(decisions))
    lines.append("")
    lines.append(HOW_TO_APPLY.rstrip())
    return "\n".join(lines) + "\n"


def overall_verdict(decisions: list[CellDecision]) -> str:
    actionable = [d for d in decisions if d.verdict != "LOCKED"]
    if any(d.verdict in ("DOWNGRADE", "UPGRADE") for d in actionable):
        return "RECOMMENDATIONS_READY"
    if any(d.verdict == "NO CHANGE" for d in actionable):
        return "NO_CHANGE"
    return "INSUFFICIENT_DATA"
