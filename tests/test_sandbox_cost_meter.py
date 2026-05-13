"""AC5 — per-second cost meter for sandbox-verify with soft+hard caps.

`hooks/_lib/sandbox_cost_meter.py`:

- `RATES_USD_PER_SECOND` dict (module-top, single source of truth).
- `tick(elapsed_seconds: float) -> {"soft_warn": bool, "hard_trip": bool,
   "elapsed_usd": float}` — C2 contract.
- Invariant: `hard_trip implies soft_warn` (anything past hard cap is also
  past soft cap by construction).
- Env-var overrides: `CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD` and `_HARD_USD`
  (defaults 0.50 / 2.00 per intake).
- `write_starting_tick(jsonl_path)` — appends `{"event": "starting", ...}`
  to the cost JSONL BEFORE provisioning, per state-before-expensive-op
  instinct.

Env-var test hygiene per `learning/instincts/instinct-env-var-test-hygiene.md`:
use `patch.dict(os.environ, {}, clear=False)` + inner pop.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _load():
    from sandbox_cost_meter import (RATES_USD_PER_SECOND, tick,
                                    write_starting_tick)
    return RATES_USD_PER_SECOND, tick, write_starting_tick


class TickContractShape(unittest.TestCase):
    """C2 contract: `tick` returns dict with three required keys + types."""

    def test_tick_returns_required_keys(self):
        _, tick, _ = _load()
        result = tick(0.5)
        self.assertIn("soft_warn", result)
        self.assertIn("hard_trip", result)
        self.assertIn("elapsed_usd", result)
        self.assertIsInstance(result["soft_warn"], bool)
        self.assertIsInstance(result["hard_trip"], bool)
        self.assertIsInstance(result["elapsed_usd"], float)


class TickUnderSoftCapNoWarnings(unittest.TestCase):
    """Below soft cap → soft_warn=False, hard_trip=False."""

    def test_tick_under_soft_cap_returns_no_warnings(self):
        _, tick, _ = _load()
        # 1 second × $0.0001/s = $0.0001 (well under $0.50 soft).
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD", None)
            os.environ.pop("CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD", None)
            result = tick(1.0)
        self.assertFalse(result["soft_warn"])
        self.assertFalse(result["hard_trip"])
        self.assertGreater(result["elapsed_usd"], 0.0)


class TickSoftWarnsHardTrips(unittest.TestCase):
    """AC5: past soft → soft_warn=True; past hard → hard_trip=True."""

    def test_cost_meter_soft_warns_hard_trips(self):
        _, tick, _ = _load()
        # Force tiny caps so a small elapsed_seconds crosses thresholds.
        with patch.dict(os.environ, {
                "CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD": "0.0001",
                "CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD": "0.001",
        }, clear=False):
            # 100 seconds at default rate → ~$0.01, past hard.
            past_hard = tick(100.0)
            # 5 seconds → ~$0.0005, past soft but under hard.
            past_soft_only = tick(5.0)

        self.assertTrue(past_hard["hard_trip"])
        self.assertTrue(past_hard["soft_warn"],
                        "C2 invariant: hard_trip implies soft_warn")
        self.assertTrue(past_soft_only["soft_warn"])
        self.assertFalse(past_soft_only["hard_trip"])

    def test_hard_trip_implies_soft_warn_invariant(self):
        """C2 contract invariant — exhaustive: any hard_trip MUST soft_warn."""
        _, tick, _ = _load()
        with patch.dict(os.environ, {
                "CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD": "0.0001",
                "CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD": "0.0005",
        }, clear=False):
            for elapsed in [1.0, 10.0, 100.0, 1000.0]:
                result = tick(elapsed)
                if result["hard_trip"]:
                    self.assertTrue(result["soft_warn"],
                                    f"hard_trip without soft_warn at "
                                    f"elapsed={elapsed}")

    def test_hard_trip_forces_soft_warn_even_when_soft_cap_higher(self):
        """Adversarial: kills the `drop hard_trip from soft_warn` mutation.

        With SOFT cap > HARD cap (degenerate but legal config), elapsed_usd
        can sit ABOVE hard_cap and BELOW soft_cap. The C2 invariant says
        `hard_trip implies soft_warn`, so soft_warn MUST still be True via
        the `or hard_trip` clause. Without that clause, soft_warn would be
        False for this configuration and the mutation survives.
        """
        _, tick, _ = _load()
        with patch.dict(os.environ, {
                # Soft cap deliberately HIGHER than hard cap (inverted).
                "CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD": "100.0",
                "CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD": "0.0001",
        }, clear=False):
            # 10 seconds at $0.0001/s = $0.001 — past hard (0.0001),
            # under soft (100.0). soft_warn would be False without
            # the `or hard_trip` clause.
            result = tick(10.0)
        self.assertTrue(result["hard_trip"])
        self.assertTrue(
            result["soft_warn"],
            "C2 invariant: hard_trip implies soft_warn, regardless of cap order")

    def test_soft_warn_at_exact_boundary(self):
        """Adversarial: kills the `>=` -> `>` boundary mutation on soft cap.

        When elapsed_usd EXACTLY equals soft_cap, the C2 contract uses
        `>=` so soft_warn must be True. Mutation to `>` would yield False.
        """
        _, tick, _ = _load()
        # 5000 seconds at $0.0001/s = $0.5 exactly == default soft cap.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD", None)
            os.environ.pop("CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD", None)
            result = tick(5000.0)
        # elapsed_usd should be 0.5 exactly.
        self.assertAlmostEqual(result["elapsed_usd"], 0.5, places=6)
        self.assertTrue(result["soft_warn"],
                        ">= boundary: soft_warn at exact soft cap")

    def test_hard_trip_at_exact_boundary(self):
        """Adversarial: kills the `>=` -> `>` boundary mutation on hard cap."""
        _, tick, _ = _load()
        # 20000 seconds at $0.0001/s = $2.0 exactly == default hard cap.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD", None)
            os.environ.pop("CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD", None)
            result = tick(20000.0)
        self.assertAlmostEqual(result["elapsed_usd"], 2.0, places=6)
        self.assertTrue(result["hard_trip"],
                        ">= boundary: hard_trip at exact hard cap")


class StartingTickWrittenBeforeExpensiveOp(unittest.TestCase):
    """AC5 + state-before-expensive-op: starting tick is persisted BEFORE
    the first E2B HTTP call. Verifies a real JSONL line is written and
    that the file mode is 0o600."""

    def test_cost_meter_writes_starting_tick_before_provision(self):
        _, _, write_starting_tick = _load()

        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "sub" / "sandbox-verify-cost.jsonl"
            write_starting_tick(str(jsonl_path),
                                session_id="test-session-cost")

            self.assertTrue(jsonl_path.exists(),
                            "starting tick must create the JSONL file")
            lines = jsonl_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["event"], "starting")
            self.assertEqual(record["session_id"], "test-session-cost")
            self.assertIn("timestamp", record)

    def test_starting_tick_jsonl_file_mode_0o600(self):
        """LOW-B: cost JSONL written with restrictive mode 0o600."""
        _, _, write_starting_tick = _load()
        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "sandbox-verify-cost.jsonl"
            write_starting_tick(str(jsonl_path), session_id="test-mode")
            mode = stat.S_IMODE(os.stat(jsonl_path).st_mode)
            self.assertEqual(mode, 0o600,
                             f"cost JSONL must be 0o600; got {oct(mode)}")


class WriteCostEventEmitsJsonlForSoftWarnAndHardTrip(unittest.TestCase):
    """M21 carryforward — `write_cost_event` emits JSONL for soft-warn
    AND hard-trip events. The function is the shared writer for both
    boundary crossings; without coverage of the named events, mutations
    that drop one branch from the writer survive (e.g. mutation that
    skips the soft-warn write and only writes hard-trip lines).

    Mode is 0o600 (LOW-B carryforward — same hardening as starting tick).
    """

    def test_write_cost_event_soft_cap_warn_emits_jsonl(self):
        from sandbox_cost_meter import write_cost_event
        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "sub" / "sandbox-verify-cost.jsonl"
            write_cost_event(str(jsonl_path), session_id="s-warn",
                             event="soft-cap-warn",
                             payload={"elapsed_usd": 0.55,
                                      "soft_cap_usd": 0.50})
            self.assertTrue(jsonl_path.exists())
            lines = jsonl_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["event"], "soft-cap-warn")
            self.assertEqual(record["session_id"], "s-warn")
            self.assertEqual(record["elapsed_usd"], 0.55)
            self.assertEqual(record["soft_cap_usd"], 0.50)
            self.assertIn("timestamp", record)
            # LOW-B carryforward: mode 0o600.
            mode = stat.S_IMODE(os.stat(jsonl_path).st_mode)
            self.assertEqual(mode, 0o600)

    def test_write_cost_event_hard_trip_emits_jsonl(self):
        from sandbox_cost_meter import write_cost_event
        with tempfile.TemporaryDirectory() as tmp:
            jsonl_path = Path(tmp) / "sandbox-verify-cost.jsonl"
            write_cost_event(str(jsonl_path), session_id="s-trip",
                             event="hard-cap-trip",
                             payload={"elapsed_usd": 2.10,
                                      "hard_cap_usd": 2.00})
            self.assertTrue(jsonl_path.exists())
            lines = jsonl_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["event"], "hard-cap-trip")
            self.assertEqual(record["session_id"], "s-trip")
            self.assertEqual(record["elapsed_usd"], 2.10)
            self.assertEqual(record["hard_cap_usd"], 2.00)


if __name__ == "__main__":
    unittest.main()
