"""Pure-function diff algorithm for sandbox-verify.

Two public functions:

- `parse_test_outcomes(output, runner='pytest') -> dict[str, "pass"|"fail"]`
  Story-1 stub: returns an empty dict; Story 2 fills in the per-language
  parsers (pytest, jest, rspec, ...). The contract is a string->str map
  where each value is exactly `"pass"` or `"fail"`.

- `compare_pass_sets(worktree, sandbox) -> dict`
  Compares two `{test_name: "pass"|"fail"}` dicts by symmetric difference
  on the pass sets. Returns `{"verdict": ..., "diverging_tests": [...]}`.
  Empty diff → SANDBOX_VERIFIED; non-empty → SANDBOX_FAILED with names
  sorted for determinism.

Lives in `hooks/_lib/` per the extracted-Python-helper pattern (see
`session-memory/.../patterns.md` § Python helper module pattern).
"""
from __future__ import annotations


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


def parse_test_outcomes(output, runner="pytest"):
    """Parse test-runner output into `{test_name: "pass"|"fail"}`.

    Story-1 stub: returns `{}`. The contract is a `dict[str, str]` where
    each value is exactly `"pass"` or `"fail"`. Story 2 extends this with
    per-language parsers; the runner argument selects the parser.
    """
    # Story 2 fills this in per language. The empty-dict stub composes
    # correctly with compare_pass_sets — two empty parses produce
    # SANDBOX_VERIFIED, which is the right behaviour when neither side
    # has parseable test output (degenerate but not a regression).
    del output, runner  # unused at Story 1
    return {}
