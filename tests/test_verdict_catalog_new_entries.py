"""Slice C AC-C4 — three new CACHE_FLIP_GATE_* verdicts declared in catalog.

`rules/verdict-catalog.md` is the single source of truth for verdict names.
Slice C adds:
  - `CACHE_FLIP_GATE_PASS` (success polarity)
  - `CACHE_FLIP_GATE_HOLD` (info polarity)
  - `CACHE_FLIP_GATE_INSUFFICIENT_DATA` (info polarity)

All three must be emitted by skill `cache-flip-gate`.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "rules" / "verdict-catalog.md"


class CacheFlipGateVerdictsRegistered(unittest.TestCase):
    def test_cache_flip_gate_verdicts_in_catalog(self):
        text = CATALOG.read_text()
        for verdict in ("CACHE_FLIP_GATE_PASS",
                        "CACHE_FLIP_GATE_HOLD",
                        "CACHE_FLIP_GATE_INSUFFICIENT_DATA"):
            self.assertIn(
                f"`{verdict}`", text,
                f"verdict `{verdict}` must be declared in rules/verdict-catalog.md")
            # also assert it is associated with the cache-flip-gate emitter
        # All three rows must reference the cache-flip-gate skill emitter.
        for line in text.splitlines():
            if "CACHE_FLIP_GATE_" in line:
                self.assertIn(
                    "cache-flip-gate", line,
                    f"row `{line}` should attribute emitter `cache-flip-gate`")


if __name__ == "__main__":
    unittest.main()
