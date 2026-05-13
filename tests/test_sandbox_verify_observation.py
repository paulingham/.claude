"""AC2 — `hooks/_lib/sandbox_verify_observation.py` reader helper.

Three pure functions per the plan's Slice Order step 2 + Tier-0 contracts
C1-C3:

- `read_sandbox_phase(observation: dict) -> Optional[dict]`
  C1: returns None when absent (or null); never returns `{}`. Pure — no I/O.

- `is_present(observation: dict) -> bool`
  C2: True iff `phases.sandbox_verify` is a dict carrying the `verdict` key
  whose value is in the 3-enum set
  {`SANDBOX_VERIFIED`, `SANDBOX_FAILED`, `SANDBOX_SKIPPED`}.

- `diverging_tests_from_build_md(build_md_text: str) -> list[str]`
  C3: parses the build.md `## Sandbox Verify` body table for rows where
  the `Diff` column is `diverge`; returns the test names. Idempotent;
  returns `[]` when the section is absent.

Anti-coercion invariant: legacy records missing the block return None
from `read_sandbox_phase`. Consumers (`/learn`, `/forensics`,
`/eval-model-effectiveness`) MUST filter, never coerce.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _load():
    import sandbox_verify_observation
    return sandbox_verify_observation


class ReadSandboxPhaseReturnsNoneWhenAbsent(unittest.TestCase):
    """C1: absence returns None (legacy record, never coerce)."""

    def test_absent_block_returns_none(self):
        mod = _load()
        self.assertIsNone(mod.read_sandbox_phase({}))
        self.assertIsNone(mod.read_sandbox_phase({"phases": {}}))
        self.assertIsNone(
            mod.read_sandbox_phase({"phases": {"build": {}}}))


class ReadSandboxPhaseReturnsDictWhenPresent(unittest.TestCase):
    """C1: present block returned as-is (caller treats as read-only)."""

    def test_present_dict_returned(self):
        mod = _load()
        obs = {"phases": {"sandbox_verify": {
            "verdict": "SANDBOX_VERIFIED",
            "rounds": 1,
            "cost_estimate_usd": 0.42,
        }}}
        result = mod.read_sandbox_phase(obs)
        self.assertIsNotNone(result)
        self.assertEqual(result["verdict"], "SANDBOX_VERIFIED")
        self.assertEqual(result["rounds"], 1)


class ReadSandboxPhaseNullValueTreatedAsAbsent(unittest.TestCase):
    """Explicit `null` is distinct from synthetic empty dict — still absent."""

    def test_explicit_null_is_absent(self):
        mod = _load()
        obs = {"phases": {"sandbox_verify": None}}
        self.assertIsNone(mod.read_sandbox_phase(obs))


class IsPresentTrueIffDictWithVerdictKey(unittest.TestCase):
    """C2: present iff dict + verdict key in 3-enum set."""

    def test_is_present_true_when_verdict_in_enum(self):
        mod = _load()
        for verdict in ("SANDBOX_VERIFIED",
                        "SANDBOX_FAILED", "SANDBOX_SKIPPED"):
            obs = {"phases": {"sandbox_verify": {"verdict": verdict}}}
            self.assertTrue(
                mod.is_present(obs),
                f"verdict={verdict!r} must register as present")

    def test_is_present_false_when_absent(self):
        mod = _load()
        self.assertFalse(mod.is_present({}))
        self.assertFalse(mod.is_present({"phases": {}}))

    def test_is_present_false_when_verdict_key_missing(self):
        mod = _load()
        # Dict present but verdict missing (malformed) → treat as absent.
        obs = {"phases": {"sandbox_verify": {"rounds": 1}}}
        self.assertFalse(mod.is_present(obs))

    def test_is_present_false_when_verdict_not_in_enum(self):
        mod = _load()
        # Unknown verdict → treat as absent (defensive: don't crash
        # downstream consumers on garbage data).
        obs = {"phases": {"sandbox_verify": {"verdict": "GARBAGE"}}}
        self.assertFalse(mod.is_present(obs))


class LearnReaderFiltersMissingRecordsNotCoerce(unittest.TestCase):
    """AC2 invariant: readers MUST filter, not coerce.

    `is_present` returns False for missing records; downstream callers
    iterating over `observations.jsonl` filter on that, never assume a
    default verdict.
    """

    def test_filter_pattern_skips_missing_records(self):
        mod = _load()
        # Mixed batch: present + absent + present.
        records = [
            {"pipeline_id": "p1", "phases": {"sandbox_verify": {
                "verdict": "SANDBOX_VERIFIED", "rounds": 1,
                "cost_estimate_usd": 0.1}}},
            {"pipeline_id": "p2"},  # legacy: no phases block
            {"pipeline_id": "p3", "phases": {"sandbox_verify": {
                "verdict": "SANDBOX_FAILED", "rounds": 2,
                "cost_estimate_usd": 0.2,
                "divergence_count": 3,
                "diverging_tests": ["tests/a.py::t", "tests/b.py::u",
                                    "tests/c.py::v"]}}},
        ]
        # Canonical filter idiom from the plan's M21 invariant:
        kept = [r for r in records if mod.is_present(r)]
        self.assertEqual(len(kept), 2,
                         "legacy record p2 must be filtered, not coerced")
        ids = [r["pipeline_id"] for r in kept]
        self.assertEqual(ids, ["p1", "p3"])


class DivergingTestsFromBuildMd(unittest.TestCase):
    """C3: parse `## Sandbox Verify` table for diverging rows."""

    def test_diverging_tests_extracted_from_diverge_rows(self):
        mod = _load()
        build_md = """## Decision Record
- Chose: simple.

## Context for Review
- Nothing.

## Sandbox Verify
- Worktree pass: 13/15
- Sandbox pass:   13/15
- Verdict: SANDBOX_FAILED

| Test | Worktree | Sandbox | Diff |
|---|---|---|---|
| tests/test_a.py::t_one | PASS | FAIL | diverge |
| tests/test_b.py::t_two | PASS | PASS | match |
| tests/test_c.py::t_three | FAIL | PASS | diverge |
"""
        tests = mod.diverging_tests_from_build_md(build_md)
        self.assertEqual(tests,
                         ["tests/test_a.py::t_one",
                          "tests/test_c.py::t_three"])

    def test_diverging_tests_empty_when_section_absent(self):
        mod = _load()
        build_md = "## Decision Record\n- nothing\n"
        self.assertEqual(mod.diverging_tests_from_build_md(build_md), [])

    def test_diverging_tests_empty_when_no_diverge_rows(self):
        mod = _load()
        build_md = """## Sandbox Verify
- Verdict: SANDBOX_VERIFIED

| Test | Worktree | Sandbox | Diff |
|---|---|---|---|
| tests/test_a.py::t | PASS | PASS | match |
"""
        self.assertEqual(mod.diverging_tests_from_build_md(build_md), [])

    def test_diverging_tests_idempotent(self):
        """C3: idempotent — parse twice gets the same list."""
        mod = _load()
        build_md = """## Sandbox Verify
| Test | Worktree | Sandbox | Diff |
|---|---|---|---|
| tests/x.py::t | PASS | FAIL | diverge |
"""
        a = mod.diverging_tests_from_build_md(build_md)
        b = mod.diverging_tests_from_build_md(build_md)
        self.assertEqual(a, b)
        self.assertEqual(a, ["tests/x.py::t"])


if __name__ == "__main__":
    unittest.main()
