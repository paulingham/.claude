"""Regression: pipeline-protocol.md must include 'plan' in the phase enum."""
import re
from pathlib import Path


def test_plan_in_pipeline_protocol_phase_enum():
    content = (Path(__file__).parent.parent / "rules" / "pipeline-protocol.md").read_text()
    # The phase enum line should contain 'plan'
    assert re.search(r'phase.*plan.*build', content), (
        "rules/pipeline-protocol.md phase enum must include 'plan' before 'build'"
    )


def test_planning_agent_subsection_in_parallel_dispatch():
    content = (Path(__file__).parent.parent / "rules" / "parallel-dispatch-protocol.md").read_text()
    assert "Planning Agent" in content, (
        "rules/parallel-dispatch-protocol.md must have a Planning Agent subsection"
    )


def test_planning_agent_in_claude_md_agent_table():
    content = (Path(__file__).parent.parent / "CLAUDE.md").read_text()
    assert "planning-agent" in content, (
        "CLAUDE.md Agent Team table must include planning-agent row"
    )
