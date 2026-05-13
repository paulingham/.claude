"""Spec-blind behavioural tests for Story 3 (E2B provisioning + secrets + cost cap).

Authored from AC plan + Tier 0 contracts ONLY. No implementation source read.
Verdict surface exercised:
  - hooks/_lib/sandbox_e2b_client.py        — provision_microvm / exec / destroy
  - hooks/_lib/sandbox_secrets_allowlist.py — forward_env(allowlist)
  - hooks/_lib/sandbox_cost_meter.py        — tick(elapsed_seconds, rate_key)
  - hooks/_lib/sandbox_verify_diff.py       — parse_test_outcomes(output, runner)
  - rules/verdict-catalog.md                — SANDBOX_SKIPPED / SANDBOX_FAILED rows

These tests exercise the published function-envelope contracts (C1, C2, C3 from
plan.md § Tier 0 Contract Assertions) and the AC literal — they do NOT
introspect source line shape.
"""

import os
import sys
import unittest
from pathlib import Path

# Project import convention (set by tests/conftest.py): `hooks/_lib` is on
# sys.path so its modules import as bare names (e.g. `import sandbox_cost_meter`).
# We mirror that here so this test file is robust to either unittest or pytest
# being the runner (unittest does not auto-load pytest conftest files).
_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_LIB = str(_WORKTREE_ROOT / "hooks" / "_lib")
if _HOOKS_LIB not in sys.path:
    sys.path.insert(0, _HOOKS_LIB)


def _import_module(name: str):
    """Import a module by name. We bind to the module's public symbols via
    Python's import mechanism — we do NOT read the source. The argument is
    the bare module name (the project's convention for `hooks/_lib/` helpers)."""
    import importlib

    return importlib.import_module(name)


class AC3_SecretsAllowlist_DefaultDeny(unittest.TestCase):
    """AC3: No declaration → zero secrets forwarded (C3: empty allowlist → {})."""

    def test_forward_env_empty_allowlist_returns_empty_dict(self):
        m = _import_module("sandbox_secrets_allowlist")
        # Even with a populated host environment, an empty allowlist must
        # return an empty dict. Default-deny is the AC literal.
        os.environ["__SPEC_BLIND_PROBE__"] = "should-not-leak"
        try:
            result = m.forward_env([])
        finally:
            os.environ.pop("__SPEC_BLIND_PROBE__", None)
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {})

    def test_forward_env_only_returns_allowlisted_keys(self):
        m = _import_module("sandbox_secrets_allowlist")
        os.environ["DB_URL"] = "postgres://example"
        os.environ["ANTHROPIC_API_KEY"] = "secret-must-not-leak"
        try:
            result = m.forward_env(["DB_URL"])
        finally:
            os.environ.pop("DB_URL", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)
        # AC3: ONLY allowlisted keys returned; secret env var stripped.
        self.assertEqual(result.get("DB_URL"), "postgres://example")
        self.assertNotIn("ANTHROPIC_API_KEY", result)
        # No other host vars leak in.
        self.assertEqual(set(result.keys()) & {"ANTHROPIC_API_KEY", "GITHUB_PERSONAL_ACCESS_TOKEN"}, set())


class AC5_CostMeter_SoftAndHardCaps(unittest.TestCase):
    """AC5: per-second cost meter — soft warn at $0.50, hard trip at $2.00.

    Contract C2: tick(elapsed_seconds) → {soft_warn, hard_trip, elapsed_usd}.
    Invariant: hard_trip implies soft_warn.
    """

    def test_small_elapsed_does_not_trip_either_cap(self):
        m = _import_module("sandbox_cost_meter")
        result = m.tick(0.5)
        self.assertIsInstance(result, dict)
        self.assertIn("soft_warn", result)
        self.assertIn("hard_trip", result)
        self.assertIn("elapsed_usd", result)
        self.assertFalse(result["soft_warn"], f"expected soft_warn=False at 0.5s, got {result}")
        self.assertFalse(result["hard_trip"], f"expected hard_trip=False at 0.5s, got {result}")
        # cost is non-negative and tiny
        self.assertGreaterEqual(result["elapsed_usd"], 0.0)

    def test_large_elapsed_trips_hard_cap(self):
        m = _import_module("sandbox_cost_meter")
        # 99999 seconds at any positive rate must exceed the $2.00 hard cap.
        result = m.tick(99999)
        self.assertTrue(result["hard_trip"], f"expected hard_trip=True at 99999s, got {result}")
        # AC: elapsed_usd is non-trivial when hard-tripping
        self.assertGreater(result["elapsed_usd"], 2.0)

    def test_hard_trip_implies_soft_warn_invariant(self):
        """C2 invariant: hard_trip implies soft_warn."""
        m = _import_module("sandbox_cost_meter")
        for elapsed in (10.0, 1000.0, 99999.0, 1e7):
            result = m.tick(elapsed)
            if result["hard_trip"]:
                self.assertTrue(
                    result["soft_warn"],
                    f"C2 invariant violated at elapsed={elapsed}: "
                    f"hard_trip=True but soft_warn=False (result={result})",
                )


class AC1_AC4_ProvisionEnvelope(unittest.TestCase):
    """AC1 + AC4: provision_microvm returns the {ok, reason, microvm_id, ...} envelope.

    Without E2B_API_KEY → ok=False with a discoverable reason.
    """

    def test_provision_without_token_returns_not_ok_envelope(self):
        m = _import_module("sandbox_e2b_client")
        # Ensure no token in env for this test (default-deny token path).
        saved = os.environ.pop("E2B_API_KEY", None)
        try:
            result = m.provision_microvm()
        finally:
            if saved is not None:
                os.environ["E2B_API_KEY"] = saved
        # C1: envelope shape with ok:bool. Reason should be discoverable.
        self.assertIsInstance(result, dict)
        self.assertIn("ok", result)
        self.assertFalse(
            result["ok"],
            f"AC4 / AC1: provision without token must report ok=False, got {result}",
        )
        # Reason should be a non-empty string indicating the failure class.
        self.assertIn("reason", result, f"envelope missing 'reason' key: {result}")
        self.assertIsInstance(result["reason"], str)
        self.assertTrue(result["reason"], "reason must be a non-empty string")

    def test_provision_module_exposes_lifecycle_functions(self):
        """The module's public surface includes provision/exec/destroy per intake & plan."""
        m = _import_module("sandbox_e2b_client")
        for name in ("provision_microvm", "exec_in_microvm", "destroy_microvm"):
            self.assertTrue(
                hasattr(m, name),
                f"sandbox_e2b_client.{name} not exposed — required by AC1/AC6 surface",
            )


class AC2_ParseTestOutcomes_Pytest(unittest.TestCase):
    """AC2: per-test outcomes captured in parseable format.

    parse_test_outcomes(output, runner='pytest') returns {test_name: 'pass'|'fail'}.
    """

    def test_parse_pytest_mixed_pass_and_fail(self):
        m = _import_module("sandbox_verify_diff")
        sample = "test_foo PASSED\ntest_bar FAILED\n"
        result = m.parse_test_outcomes(sample, "pytest")
        self.assertIsInstance(result, dict)
        # AC2 literal: test name → pass/fail
        self.assertEqual(
            result.get("test_foo"),
            "pass",
            f"AC2: PASSED line must map to 'pass'; got {result}",
        )
        self.assertEqual(
            result.get("test_bar"),
            "fail",
            f"AC2: FAILED line must map to 'fail'; got {result}",
        )


class AC4_AC5_VerdictCatalog_EnumDrift(unittest.TestCase):
    """AC4 + AC5: catalog reflects new reasons after Story 3.

    SANDBOX_SKIPPED enum must include `e2b-unavailable` (AC4).
    SANDBOX_FAILED row must mention `cost-exceeded` reason (AC5).
    cost-exceeded must NOT appear in SANDBOX_SKIPPED (separation of concerns).
    """

    @classmethod
    def setUpClass(cls):
        catalog = _WORKTREE_ROOT / "rules" / "verdict-catalog.md"
        cls.catalog_text = catalog.read_text()
        # Extract the three SANDBOX rows for targeted assertion.
        cls.skipped_row = next(
            (ln for ln in cls.catalog_text.splitlines() if "`SANDBOX_SKIPPED`" in ln),
            "",
        )
        cls.failed_row = next(
            (ln for ln in cls.catalog_text.splitlines() if "`SANDBOX_FAILED`" in ln),
            "",
        )

    def test_skipped_enum_contains_e2b_unavailable(self):
        self.assertIn(
            "e2b-unavailable",
            self.skipped_row,
            "AC4: SANDBOX_SKIPPED enum must include `e2b-unavailable` after Story 3. "
            f"Row: {self.skipped_row!r}",
        )

    def test_failed_row_mentions_cost_exceeded(self):
        self.assertIn(
            "cost-exceeded",
            self.failed_row,
            "AC5: SANDBOX_FAILED row must reference `cost-exceeded` reason after Story 3. "
            f"Row: {self.failed_row!r}",
        )

    def test_cost_exceeded_not_in_skipped_enum(self):
        # cost-exceeded is a HARD-TRIP failure, not a skip — surface separation.
        self.assertNotIn(
            "cost-exceeded",
            self.skipped_row,
            "AC5: `cost-exceeded` is a SANDBOX_FAILED reason, not a SANDBOX_SKIPPED reason. "
            f"Row: {self.skipped_row!r}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
