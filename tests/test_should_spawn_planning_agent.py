"""Tests for the planning-agent spawn gate.

The gate decides whether to spawn a continuous-planning agent alongside the
Build team. It returns False on single-slice, Best-of-N, or fix dispatches.
"""

from should_spawn_planning_agent import should_spawn_planning_agent


def test_spawns_on_two_slices():
    assert should_spawn_planning_agent(2, "standard", "build") is True


def test_spawns_on_five_slices():
    assert should_spawn_planning_agent(5, "standard", "build") is True


def test_skips_on_single_slice():
    assert should_spawn_planning_agent(1, "standard", "build") is False


def test_skips_on_best_of_n():
    assert should_spawn_planning_agent(2, "best-of-n", "build") is False


def test_skips_on_fix_phase():
    assert should_spawn_planning_agent(2, "standard", "fix") is False


def test_skips_on_zero_slices():
    assert should_spawn_planning_agent(0, "standard", "build") is False


def test_standard_mode_exactly_two():
    assert should_spawn_planning_agent(2, "standard", "build") is True
