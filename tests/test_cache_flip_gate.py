"""Slice C AC-C4 (gate) — cache_flip_gate.py evaluates 30-day P50 read_ratio.

Three behaviour tests with synthetic JSONL fixtures (no real metrics files):
  (a) P50 >= 0.70 AND n >= 100 → `CACHE_FLIP_GATE_PASS`
  (b) P50 < 0.70 → `CACHE_FLIP_GATE_HOLD`
  (c) n < 30 → `CACHE_FLIP_GATE_INSUFFICIENT_DATA` (regardless of P50)
"""
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
import cache_flip_gate  # noqa: E402


def _write_jsonl(dir_path: Path, ratios: list[float]) -> None:
    """Write one cache.jsonl with N records, one read_ratio per record."""
    session_dir = dir_path / "session-x"
    session_dir.mkdir(parents=True, exist_ok=True)
    with (session_dir / "cache.jsonl").open("w") as fh:
        for r in ratios:
            fh.write(json.dumps({"read_ratio": r, "agent_role": "x"}) + "\n")


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


if __name__ == "__main__":
    unittest.main()
