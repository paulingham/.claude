"""Slice slice-c-consumer — markdown-grep contract for the new dispatch subsection.

These tests pin the structure and content of the new
`### Multi-Slice DAG Mode (schema_version: 2)` subsection that slice-c-consumer
adds to `orchestrator/parallel-dispatch-details.md`. Assertions are
heading-anchored (NOT line-numbered) per E1 fix.
"""
from pathlib import Path

import pytest

DISPATCH_FILE = (
    Path(__file__).resolve().parent.parent
    / "orchestrator"
    / "parallel-dispatch-details.md"
)

DAG_HEADING = "### Multi-Slice DAG Mode (schema_version: 2)"
MULTISLICE_HEADING = "### Multi-Slice (team -- parallel engineers)"
PLANNING_HEADING = "### Planning Agent Dispatch (advisory, multi-slice Build only)"


@pytest.fixture(scope="module")
def dispatch_text() -> str:
    return DISPATCH_FILE.read_text()


@pytest.fixture(scope="module")
def dag_subsection(dispatch_text: str) -> str:
    """Body of the new subsection (between its heading and the next `### `)."""
    start = dispatch_text.find(DAG_HEADING)
    if start == -1:
        return ""
    after = dispatch_text[start + len(DAG_HEADING):]
    next_h3 = after.find("\n### ")
    return after if next_h3 == -1 else after[:next_h3]


def test_dag_mode_subsection_exists(dispatch_text: str) -> None:
    assert DAG_HEADING in dispatch_text


def test_dag_mode_inserts_after_multislice_before_planning(dispatch_text: str) -> None:
    """Structural anchor — heading order, not line numbers (E1 fix)."""
    multi = dispatch_text.find(MULTISLICE_HEADING)
    dag = dispatch_text.find(DAG_HEADING)
    planning = dispatch_text.find(PLANNING_HEADING)
    assert multi != -1, "Multi-Slice heading missing"
    assert dag != -1, "DAG mode heading missing"
    assert planning != -1, "Planning Agent Dispatch heading missing"
    assert multi < dag < planning, (
        f"DAG heading must sit between Multi-Slice and Planning headings; "
        f"got multi={multi} dag={dag} planning={planning}"
    )


def test_dag_mode_documents_pack_wave_function(dag_subsection: str) -> None:
    """B2 fix — single canonical knapsack `pack_wave` referenced by name."""
    assert "def pack_wave(" in dag_subsection
    assert "CLAUDE_BUILD_WAVE_MAX_PARALLEL" in dag_subsection
    assert "CLAUDE_BESTOFN_MAX_WORKTREES" in dag_subsection


def test_dag_mode_documents_knapsack_not_divisor(dag_subsection: str) -> None:
    """Subsection talks knapsack/first-fit; the old divisor formulation is gone."""
    lowered = dag_subsection.lower()
    assert ("first-fit" in lowered) or ("knapsack" in lowered)
    assert "floor(claude_bestofn_max_worktrees /" not in lowered


def test_dag_mode_documents_phases_build_wave_count(dag_subsection: str) -> None:
    """B1 fix — both forensic fields named in subsection prose."""
    assert "phases.build.wave_count" in dag_subsection
    assert "phases.build.wave_widths" in dag_subsection


def test_dag_mode_uses_worktree_delegated_cherry_pick(dag_subsection: str) -> None:
    """IL4 — every cherry-pick is worktree-delegated; no bare form."""
    assert 'git -C "$WORKTREE" cherry-pick' in dag_subsection
    # Bare `git cherry-pick` (no preceding `-C "$WORKTREE"`) must not appear.
    # Scan tokens; allow occurrences only when preceded by `-C "$WORKTREE"`.
    needle = "git cherry-pick"
    idx = 0
    while True:
        hit = dag_subsection.find(needle, idx)
        if hit == -1:
            break
        prefix = dag_subsection[max(0, hit - 25):hit]
        assert '-C "$WORKTREE"' in prefix, (
            f"Bare `git cherry-pick` found at offset {hit}; "
            f"preceding 25 chars: {prefix!r}"
        )
        idx = hit + len(needle)


def test_dag_mode_documents_transitive_cancel(dag_subsection: str) -> None:
    """M3 — failure handling cancels descendants and reconciles with retry-twice rule."""
    assert "transitive descendants" in dag_subsection
    assert "retry-twice-then-escalate" in dag_subsection


def test_dag_mode_escalation_message_lists_cancelled_dependents(dag_subsection: str) -> None:
    """M3 — verbatim escalation copy with cancelled-dependent IDs and recovery options."""
    assert "Pipeline halted:" in dag_subsection
    assert "Cancelled" in dag_subsection
    assert "dependent slice(s):" in dag_subsection
    assert "§ Re-routes" in dag_subsection
    assert "Recovery options" in dag_subsection
    # Three numbered options.
    for marker in ("1.", "2.", "3."):
        assert marker in dag_subsection, f"missing recovery option {marker}"


def test_dag_mode_specifies_branch_head_sha_capture(dag_subsection: str) -> None:
    """M5 — agent's structured return carries `branch_head_sha`; orchestrator does NOT `git merge`."""
    assert "branch_head_sha" in dag_subsection
    # Negative: no orchestrator-side `git merge` claim. Soft regex — it's fine to
    # mention `git merge` in a NEGATIVE context ("never runs `git merge` ...").
    # The literal we forbid is the imperative "orchestrator runs git merge".
    forbidden = "orchestrator runs `git merge`"
    assert forbidden not in dag_subsection.lower()


def test_dag_mode_state_persists_to_pipeline_md_only(dag_subsection: str) -> None:
    """M6 — state persistence target is pipeline.md via Edit; .json/.yaml/.sh writes forbidden."""
    assert "pipeline.md" in dag_subsection
    assert "bash-write-guard" in dag_subsection
    # Must mention forbidden extensions explicitly.
    for ext in (".json", ".yaml", ".sh"):
        assert ext in dag_subsection, f"forbidden-write extension {ext} not called out"
