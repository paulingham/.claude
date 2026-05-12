"""Pure-function diff algorithm for sandbox-verify.

Two public functions:

- `parse_test_outcomes(output, runner='pytest') -> dict[str, "pass"|"fail"]`
  Story 3 implements the pytest `-v` parser. Story 4 carryforward extends
  to jest, rspec, cargo, go test. ERROR markers map to `"fail"` because
  the gate's contract is the pass set; ERROR is observably non-passing.

- `compare_pass_sets(worktree, sandbox) -> dict`
  Compares two `{test_name: "pass"|"fail"}` dicts by symmetric difference
  on the pass sets. Returns `{"verdict": ..., "diverging_tests": [...]}`.
  Empty diff → SANDBOX_VERIFIED; non-empty → SANDBOX_FAILED with names
  sorted for determinism.

Lives in `hooks/_lib/` per the extracted-Python-helper pattern (see
`session-memory/.../patterns.md` § Python helper module pattern).
"""
from __future__ import annotations

import re

# Pytest `-v` output marker:
#   tests/test_a.py::test_one PASSED                          [ 25%]
#   tests/test_b.py::test_three FAILED                        [ 75%]
#   tests/test_b.py::test_four ERROR                          [100%]
# Anchored at line start; test_name is everything before the marker.
_PYTEST_LINE = re.compile(
    r"^(?P<name>\S+)\s+(?P<marker>PASSED|FAILED|ERROR)\b")

# ERROR maps to "fail" per plan.md stub #3 assertion intent: the pass set is
# the contract; ERROR is observably non-passing for the diff algorithm.
_PYTEST_MARKER_TO_VERDICT = {
    "PASSED": "pass",
    "FAILED": "fail",
    "ERROR": "fail",
}


def _pass_set(outcomes):
    """Set of test names that passed in this outcome dict."""
    return {name for name, verdict in outcomes.items() if verdict == "pass"}


def compare_pass_sets(worktree, sandbox):
    """Return verdict + diverging test names for two outcome dicts.

    Symmetric difference of pass sets: names in exactly one of (worktree
    passes, sandbox passes) are the divergence signal. Empty difference
    → SANDBOX_VERIFIED; non-empty → SANDBOX_FAILED with sorted names.
    """
    diverging = sorted(_pass_set(worktree) ^ _pass_set(sandbox))
    verdict = "SANDBOX_VERIFIED" if not diverging else "SANDBOX_FAILED"
    return {"verdict": verdict, "diverging_tests": diverging}


def _parse_pytest_verbose(output):
    """Scan pytest `-v` output, return `{test_name: "pass"|"fail"}`."""
    outcomes = {}
    for line in output.splitlines():
        m = _PYTEST_LINE.match(line)
        if m:
            outcomes[m.group("name")] = _PYTEST_MARKER_TO_VERDICT[
                m.group("marker")]
    return outcomes


# Runner → parser dispatch table. Story 4 adds jest/rspec/cargo/go entries.
_RUNNER_PARSERS = {
    "pytest": _parse_pytest_verbose,
}


def parse_test_outcomes(output, runner="pytest"):
    """Parse test-runner output into `{test_name: "pass"|"fail"}`.

    Story 3 implements the `pytest` parser; unknown runners return `{}`
    (defensive — composes correctly with compare_pass_sets, yielding
    SANDBOX_VERIFIED when both sides are empty).
    """
    parser = _RUNNER_PARSERS.get(runner)
    if parser is None:
        return {}
    return parser(output)
