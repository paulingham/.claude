"""Slice C AC-C4 (gate) — cache_flip_gate.py evaluates 30-day P50 read_ratio.

Behaviour tests with synthetic JSONL fixtures (no real metrics files):
  (a) P50 >= 0.70 AND n >= 100 → `CACHE_FLIP_GATE_PASS`
  (b) P50 < 0.70 → `CACHE_FLIP_GATE_HOLD`
  (c) n < 30 → `CACHE_FLIP_GATE_INSUFFICIENT_DATA` (regardless of P50)

Boundary tests (added in fix-cycle for code-reviewer MEDIUM):
  (d) n == 30 → NOT insufficient (implementation uses `n < 30`)
  (e) n == 100, P50 == 0.70 → PASS (implementation uses `>=`)
  (f) P50 exactly 0.70, n >= 100 → PASS

Time-window test (added in fix-cycle for code-reviewer HIGH):
  (g) In-window record counted, out-of-window record excluded.
"""
import datetime
import json
import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
import cache_flip_gate  # noqa: E402


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt: datetime.datetime) -> str:
    return dt.isoformat()


def _write_jsonl(dir_path: Path, ratios: list[float],
                 timestamp: datetime.datetime | None = None) -> None:
    """Write one cache.jsonl with N records, one read_ratio per record.

    If timestamp is given, each record carries that ISO timestamp; otherwise
    records get `now` so default tests stay inside the 30-day window.
    """
    session_dir = dir_path / "session-x"
    session_dir.mkdir(parents=True, exist_ok=True)
    ts = _iso(timestamp or _now_utc())
    with (session_dir / "cache.jsonl").open("w") as fh:
        for r in ratios:
            fh.write(json.dumps(
                {"read_ratio": r, "agent_role": "x", "timestamp": ts}) + "\n")


class CacheFlipGateBehaviour(unittest.TestCase):
    def test_gate_emits_pass_when_p50_above_threshold(self):
        # 150 records, P50=0.72 (majority at 0.72 with some spread)
        ratios = [0.72] * 80 + [0.68] * 35 + [0.76] * 35  # n=150, P50=0.72
        with tempfile.TemporaryDirectory() as td:
            _write_jsonl(Path(td), ratios)
            verdict = cache_flip_gate.evaluate(Path(td))
        self.assertEqual(verdict["verdict"], "CACHE_FLIP_GATE_PASS")
        self.assertGreaterEqual(verdict["n_observations"], 100)
        self.assertGreaterEqual(verdict["p50"], 0.70)

    def test_gate_emits_hold_when_below_threshold(self):
        # 150 records, P50=0.62
        ratios = [0.62] * 80 + [0.58] * 35 + [0.66] * 35
        with tempfile.TemporaryDirectory() as td:
            _write_jsonl(Path(td), ratios)
            verdict = cache_flip_gate.evaluate(Path(td))
        self.assertEqual(verdict["verdict"], "CACHE_FLIP_GATE_HOLD")
        self.assertLess(verdict["p50"], 0.70)

    def test_gate_emits_insufficient_when_n_below_30(self):
        ratios = [0.85] * 20  # n=20, P50 high but n short
        with tempfile.TemporaryDirectory() as td:
            _write_jsonl(Path(td), ratios)
            verdict = cache_flip_gate.evaluate(Path(td))
        self.assertEqual(verdict["verdict"], "CACHE_FLIP_GATE_INSUFFICIENT_DATA")
        self.assertLess(verdict["n_observations"], 30)

    def test_boundary_n_eq_30_returns_not_insufficient(self):
        # Boundary: implementation uses `n < 30` for INSUFFICIENT,
        # so n==30 is on the grading side (HOLD here because P50<0.70).
        ratios = [0.60] * 30
        with tempfile.TemporaryDirectory() as td:
            _write_jsonl(Path(td), ratios)
            verdict = cache_flip_gate.evaluate(Path(td))
        self.assertNotEqual(verdict["verdict"], "CACHE_FLIP_GATE_INSUFFICIENT_DATA")
        self.assertEqual(verdict["verdict"], "CACHE_FLIP_GATE_HOLD")
        self.assertEqual(verdict["n_observations"], 30)

    def test_boundary_n_eq_100_with_p50_above_threshold_returns_pass(self):
        # Boundary: n==100 is at the PASS edge (`n >= 100`).
        ratios = [0.72] * 100
        with tempfile.TemporaryDirectory() as td:
            _write_jsonl(Path(td), ratios)
            verdict = cache_flip_gate.evaluate(Path(td))
        self.assertEqual(verdict["verdict"], "CACHE_FLIP_GATE_PASS")
        self.assertEqual(verdict["n_observations"], 100)

    def test_boundary_p50_eq_0_70_returns_pass(self):
        # Boundary: P50 exactly 0.70 with n>=100 satisfies `P50 >= 0.70`.
        ratios = [0.70] * 100
        with tempfile.TemporaryDirectory() as td:
            _write_jsonl(Path(td), ratios)
            verdict = cache_flip_gate.evaluate(Path(td))
        self.assertEqual(verdict["verdict"], "CACHE_FLIP_GATE_PASS")
        self.assertEqual(verdict["p50"], 0.70)


class CacheFlipGateTimeWindow(unittest.TestCase):
    def test_only_in_window_records_counted(self):
        """One in-window record (now-15d) + one out-of-window (now-60d)
        with vastly different P50s; out-of-window must be excluded.

        Use n<30 thin counts to verify by observation count: if both files
        were combined, n would be 50; if only in-window kept, n=25.
        """
        now = _now_utc()
        in_window = now - datetime.timedelta(days=15)
        out_window = now - datetime.timedelta(days=60)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # In-window file
            in_dir = root / "session-in"
            in_dir.mkdir()
            with (in_dir / "cache.jsonl").open("w") as fh:
                for _ in range(25):
                    fh.write(json.dumps(
                        {"read_ratio": 0.80,
                         "timestamp": _iso(in_window)}) + "\n")
            # Out-of-window file
            out_dir = root / "session-out"
            out_dir.mkdir()
            with (out_dir / "cache.jsonl").open("w") as fh:
                for _ in range(25):
                    fh.write(json.dumps(
                        {"read_ratio": 0.10,
                         "timestamp": _iso(out_window)}) + "\n")
            # Set mtime on out-of-window file to 60 days ago for mtime pre-filter.
            old_ts = (out_window).timestamp()
            os.utime(out_dir / "cache.jsonl", (old_ts, old_ts))
            verdict = cache_flip_gate.evaluate(root)
        # Only the 25 in-window records should be counted.
        self.assertEqual(verdict["n_observations"], 25)


if __name__ == "__main__":
    unittest.main()
