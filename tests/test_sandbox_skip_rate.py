"""AC5 — `hooks/_lib/sandbox_skip_rate.py` aggregates skip-rate.

`aggregate_skip_rate(metrics_root: Path) -> dict` walks
`metrics/*/sandbox-verify-skips.jsonl` and returns:

    {
        "reasons": {<reason_enum>: <count>, ...},
        "total_invocations": int,
        "skip_rate": float,
        "dropped_lines": int,
    }

Identity invariant (Tier-0 C4):
    total_invocations == sum(reasons.values()) + dropped_lines

`skip_rate = sum(reasons.values()) / total_invocations` when
`total_invocations > 0`, else `0.0`.

Malformed JSONL lines are counted as `dropped_lines` (best-effort, never
raise). Empty metrics_root returns zeros + empty reasons.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _load():
    import sandbox_skip_rate
    return sandbox_skip_rate


def _write_skip_jsonl(metrics_root, session_id, reasons):
    """Write `metrics_root/<session>/sandbox-verify-skips.jsonl`."""
    path = (metrics_root / session_id / "sandbox-verify-skips.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for reason in reasons:
            f.write(json.dumps({
                "reason": reason,
                "timestamp": "2026-05-13T00:00:00Z",
                "session_id": session_id,
            }) + "\n")
    return path


class SkipRateAggregatesByReasonEnum(unittest.TestCase):
    """Reasons aggregate across sessions; identity invariant holds."""

    def test_aggregates_by_reason_enum(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            metrics_root = Path(tmp)
            _write_skip_jsonl(metrics_root, "s1",
                              ["no-e2b-token", "no-e2b-token",
                               "env-hatch"])
            _write_skip_jsonl(metrics_root, "s2",
                              ["e2b-unavailable", "no-testable-changes"])

            result = mod.aggregate_skip_rate(metrics_root)
            self.assertIsInstance(result, dict)
            self.assertIn("reasons", result)
            self.assertIn("total_invocations", result)
            self.assertIn("skip_rate", result)
            self.assertIn("dropped_lines", result)

            # Reason counts roll up across both sessions.
            reasons = result["reasons"]
            self.assertEqual(reasons["no-e2b-token"], 2)
            self.assertEqual(reasons["env-hatch"], 1)
            self.assertEqual(reasons["e2b-unavailable"], 1)
            self.assertEqual(reasons["no-testable-changes"], 1)

            self.assertEqual(result["dropped_lines"], 0)
            self.assertEqual(result["total_invocations"], 5)
            # Identity invariant C4:
            self.assertEqual(
                result["total_invocations"],
                sum(reasons.values()) + result["dropped_lines"])

    def test_skip_rate_value(self):
        """skip_rate = sum(reasons) / total_invocations."""
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            metrics_root = Path(tmp)
            _write_skip_jsonl(metrics_root, "s1",
                              ["no-e2b-token", "env-hatch", "env-hatch"])
            result = mod.aggregate_skip_rate(metrics_root)
            # 3 skips, 3 invocations → rate 1.0 (every invocation skipped).
            self.assertAlmostEqual(result["skip_rate"], 1.0)

    def test_skip_rate_denominator_is_total_invocations_not_sum_reasons(self):
        """Adversarial: kill mutation where skip_rate is sum(reasons)/sum(reasons).

        With dropped_lines > 0, the rate must use total_invocations
        (which includes dropped) as the denominator — otherwise the rate
        would always be 1.0 when only valid lines are seen, which masks
        JSONL corruption rates.
        """
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            metrics_root = Path(tmp)
            path = metrics_root / "s1" / "sandbox-verify-skips.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            # 2 valid + 1 malformed → sum(reasons)=2, total=3, dropped=1
            path.write_text(
                json.dumps({"reason": "no-e2b-token"}) + "\n"
                "{ malformed\n"
                + json.dumps({"reason": "env-hatch"}) + "\n"
            )
            result = mod.aggregate_skip_rate(metrics_root)
            # Real rate: 2/3 ≈ 0.6667. Mutation (sum/sum): 2/2 == 1.0.
            self.assertAlmostEqual(result["skip_rate"], 2.0 / 3.0, places=4)
            self.assertNotAlmostEqual(result["skip_rate"], 1.0)


class SkipRateHandlesEmptyMetricsDir(unittest.TestCase):
    """Empty metrics root returns zeros + empty reasons (never raises)."""

    def test_empty_metrics_dir(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            metrics_root = Path(tmp)
            result = mod.aggregate_skip_rate(metrics_root)
            self.assertEqual(result["reasons"], {})
            self.assertEqual(result["total_invocations"], 0)
            self.assertEqual(result["dropped_lines"], 0)
            self.assertEqual(result["skip_rate"], 0.0)

    def test_nonexistent_metrics_dir(self):
        mod = _load()
        # Path that does not exist — must not raise.
        result = mod.aggregate_skip_rate(
            Path("/tmp/definitely-does-not-exist-xyz-123"))
        self.assertEqual(result["reasons"], {})
        self.assertEqual(result["total_invocations"], 0)
        self.assertEqual(result["skip_rate"], 0.0)


class SkipRateMalformedLineCountedAsDroppedNotFatal(unittest.TestCase):
    """C5-shape: malformed JSONL counted as `dropped_lines`, never raise."""

    def test_malformed_line_dropped(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            metrics_root = Path(tmp)
            path = metrics_root / "s1" / "sandbox-verify-skips.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"reason": "no-e2b-token",
                            "timestamp": "x"}) + "\n"
                "{ not valid json\n"
                "\n"
                + json.dumps({"reason": "env-hatch",
                              "timestamp": "y"}) + "\n"
            )
            result = mod.aggregate_skip_rate(metrics_root)
            # 2 valid lines, 1 dropped (blank lines are not dropped, just skipped)
            self.assertEqual(result["reasons"].get("no-e2b-token"), 1)
            self.assertEqual(result["reasons"].get("env-hatch"), 1)
            self.assertEqual(result["dropped_lines"], 1)
            self.assertEqual(result["total_invocations"], 3)
            # Identity invariant preserved.
            self.assertEqual(
                result["total_invocations"],
                sum(result["reasons"].values()) + result["dropped_lines"])

    def test_record_missing_reason_field_counted_dropped(self):
        """Record present but lacking `reason` field → dropped."""
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            metrics_root = Path(tmp)
            path = metrics_root / "s1" / "sandbox-verify-skips.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"timestamp": "x"}) + "\n"
                + json.dumps({"reason": "no-e2b-token"}) + "\n"
            )
            result = mod.aggregate_skip_rate(metrics_root)
            self.assertEqual(result["dropped_lines"], 1)
            self.assertEqual(result["reasons"]["no-e2b-token"], 1)
            self.assertEqual(result["total_invocations"], 2)


if __name__ == "__main__":
    unittest.main()
