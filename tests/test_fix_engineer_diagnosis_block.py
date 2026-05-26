"""fix-engineer must declare a mandatory Diagnosis block and demand complete failing test stderr.

V1 contract:
- The agent body declares Step 1.5 (or equivalent) requiring a `## Diagnosis`
  block emitted BEFORE the first Edit/Write call.
- The Diagnosis block lists exactly three fields: root_cause, affected_files,
  approach.
- The Output spec includes the Diagnosis block as a mandatory section.
- "Inputs You Receive" requires the complete failing test stderr,
  unsummarized.
- The orchestrator spawn-prompt example in parallel-dispatch-details.md
  passes the complete stderr (not a summary) to fix-engineer.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "fix-engineer.md"
DISPATCH_PATH = REPO_ROOT / "orchestrator" / "parallel-dispatch-details.md"


def test_agent_declares_diagnosis_block_before_edit():
    body = AGENT_PATH.read_text()
    assert "## Diagnosis" in body, (
        "fix-engineer agent must declare a `## Diagnosis` section "
        "(mandatory block before any Edit/Write call)")
    for field in ("root_cause", "affected_files", "approach"):
        assert field in body, (
            f"Diagnosis block must name the `{field}` field")
    assert "Step 1.5" in body, (
        "Agent body must declare Step 1.5 (Diagnosis emission) between "
        "Step 1 (verify finding) and Step 2 (make targeted fix)")
    assert "before" in body.lower() and "edit" in body.lower(), (
        "Agent body must state that the Diagnosis block emits BEFORE "
        "any Edit/Write call")


def test_agent_output_spec_includes_diagnosis():
    body = AGENT_PATH.read_text()
    output_idx = body.find("## Output")
    assert output_idx >= 0, "Agent must have `## Output` section"
    output_section = body[output_idx:]
    assert "## Diagnosis" in output_section, (
        "Output spec must include `## Diagnosis` as a mandatory section")
    for field in ("root_cause", "affected_files", "approach"):
        assert field in output_section, (
            f"Output spec Diagnosis block must list `{field}`")


def test_agent_inputs_require_complete_stderr():
    body = AGENT_PATH.read_text()
    idx = body.find("## Inputs You Receive")
    assert idx >= 0, "Agent must have `## Inputs You Receive` section"
    end = body.find("\n## ", idx + 1)
    inputs_section = body[idx:end if end > 0 else len(body)]
    lowered = inputs_section.lower()
    assert "stderr" in lowered, (
        "Inputs section must require failing test stderr")
    assert "complete" in lowered or "unsummarized" in lowered or "verbatim" in lowered, (
        "Inputs section must specify the stderr is complete/unsummarized/"
        "verbatim — summaries discard the line numbers fix-engineer needs")
    assert "summar" in body.lower(), (
        "Agent must explicitly address the no-summary rule for stderr")


def test_dispatch_spawn_prompt_passes_complete_stderr():
    text = DISPATCH_PATH.read_text()
    idx = text.find('subagent_type: "fix-engineer"')
    assert idx >= 0, (
        "parallel-dispatch-details.md must show a fix-engineer spawn "
        "example")
    block = text[idx:idx + 3000]
    lowered = block.lower()
    assert "stderr" in lowered, (
        "fix-engineer spawn prompt must pass failing test stderr")
    assert "unsummarized" in lowered or "do not summarise" in lowered or "do not summarize" in lowered, (
        "spawn prompt must explicitly forbid summarising the stderr")
    assert "diagnosis" in lowered, (
        "spawn prompt must direct fix-engineer to emit the Diagnosis "
        "block before editing")
