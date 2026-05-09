"""AC4-bis — planning-agent guard predicate at
`orchestrator/parallel-dispatch-details.md` line ~232 must exclude
`pdr-rtv` (in addition to `best-of-n`).

The predicate is documentation-encoded today (per the architect's reuse-
discovery in pdr-rtv-skill scratchpad). The test greps the doc source-of-
truth. If the predicate is later promoted to executable code, this test
trivially extends to invoke it directly.
"""
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
DISPATCH_DOC = REPO_ROOT / "orchestrator" / "parallel-dispatch-details.md"


def _planning_agent_guard_block() -> str:
    """Return the canonical 'When spawned' bullet list under the
    Planning Agent Dispatch section."""
    text = DISPATCH_DOC.read_text()
    # Find "### Planning Agent Dispatch" then the "**When spawned**" line
    # and read the bullet list that follows (lines starting with "- ").
    m = re.search(
        r"###\s+Planning Agent Dispatch.*?\*\*When spawned\*\*[^\n]*\n(?P<bullets>(?:- [^\n]*\n)+)",
        text,
        re.DOTALL,
    )
    assert m, (
        "Could not locate 'Planning Agent Dispatch' / 'When spawned' bullet "
        "list in orchestrator/parallel-dispatch-details.md"
    )
    return m.group("bullets")


def test_planning_agent_not_spawned_when_pdr_rtv_active():
    """The dispatch_mode predicate excludes both 'best-of-n' AND 'pdr-rtv'."""
    bullets = _planning_agent_guard_block()
    # The line must mention `pdr-rtv` and `best-of-n` together in the
    # dispatch_mode exclusion clause.
    assert "pdr-rtv" in bullets, (
        "Planning-agent guard does not exclude pdr-rtv. "
        "Expected an exclusion list containing both 'best-of-n' AND 'pdr-rtv'. "
        f"Current 'When spawned' block:\n{bullets}"
    )
    assert "best-of-n" in bullets, (
        "Planning-agent guard no longer excludes best-of-n — regression. "
        f"Current 'When spawned' block:\n{bullets}"
    )

    # Both must appear on the dispatch_mode line, not split across bullets.
    dispatch_line = next(
        (line for line in bullets.splitlines() if "dispatch_mode" in line),
        "",
    )
    assert dispatch_line, (
        "No `dispatch_mode` bullet in the 'When spawned' block. "
        f"Block was:\n{bullets}"
    )
    assert "best-of-n" in dispatch_line and "pdr-rtv" in dispatch_line, (
        "dispatch_mode bullet does not list BOTH best-of-n AND pdr-rtv "
        f"in the same exclusion clause. Got: {dispatch_line}"
    )
