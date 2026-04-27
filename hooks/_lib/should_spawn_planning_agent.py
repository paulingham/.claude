"""Gate function for the continuous planning agent spawn decision.

Returns True only when a planning-agent should be spawned alongside the Build team.
Called by the orchestrator at Build phase dispatch time.
"""


def should_spawn_planning_agent(
    slice_count: int,
    dispatch_mode: str,
    phase: str,
) -> bool:
    """Return True iff a planning-agent should be spawned for this Build dispatch.

    Args:
        slice_count: Number of engineer slices in this Build.
        dispatch_mode: "standard" | "best-of-n" | "fix" or similar.
        phase: Current pipeline phase, e.g. "build" | "fix" | "review".

    Returns False when any of:
        - slice_count < 2 (single-slice has no fan-out divergence risk)
        - dispatch_mode == "best-of-n" (candidates are racing, not collaborating)
        - phase == "fix" (fix-engineer scope is narrower than the plan)
    """
    if slice_count < 2 or dispatch_mode == "best-of-n" or phase == "fix":
        return False
    return True
