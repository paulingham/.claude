"""AC22-quater: forensic budget gate consumed by CI.

Reads the most recent 30 lines from
`metrics/{session-id}/codebase-map-rebuild.jsonl` and asserts that the
mean `time_ms` across those samples stays under 2000ms.

PR #96 / commit 3a2fef4 bound SessionStart fixed cost from 3 minutes to
~2 seconds. This forensic gate prevents codebase-map from regressing
that work.

Skip semantics
==============

When fewer than 30 samples exist (fresh install, CI environment without
prior runs), the test is SKIPPED rather than failed. Without the skip,
every fresh CI run would fail the gate spuriously. The skip carries an
explicit reason so operators see why the test was non-blocking.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import unittest
from pathlib import Path

# The metrics dir is session-scoped at runtime; for the gate we look at all
# session dirs and aggregate the most recent 30 entries across them.
METRICS_BASE = Path(
    os.environ.get(
        "CLAUDE_HOOK_LOG_DIR",
        os.path.expanduser("~/.claude/metrics"),
    )
)
JSONL_FILENAME = "codebase-map-rebuild.jsonl"
SAMPLE_FLOOR = 30
MEAN_BUDGET_MS = 2000


def _collect_recent_lines(metrics_base: Path, floor: int) -> list[dict]:
    """Walk metrics dirs, gather the most-recently-modified JSONL files."""
    if not metrics_base.exists():
        return []
    candidates = list(metrics_base.glob(f"*/{JSONL_FILENAME}"))
    if not candidates:
        return []
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    lines = []
    for path in candidates:
        try:
            for raw in path.read_text().splitlines():
                if not raw.strip():
                    continue
                try:
                    lines.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
                if len(lines) >= floor:
                    return lines
        except OSError:
            continue
    return lines


class MeanRebuildTimeUnderTwoSeconds(unittest.TestCase):
    """CI-consumed forensic budget gate."""

    def test_mean_rebuild_time_under_2s(self):
        samples = _collect_recent_lines(METRICS_BASE, SAMPLE_FLOOR)
        if len(samples) < SAMPLE_FLOOR:
            self.skipTest(
                f"insufficient samples: {len(samples)} < {SAMPLE_FLOOR} "
                "(fresh install — gate not enforceable)"
            )
        time_values = [
            s.get("time_ms")
            for s in samples
            if isinstance(s.get("time_ms"), (int, float))
        ]
        self.assertGreaterEqual(
            len(time_values),
            SAMPLE_FLOOR,
            "samples lack time_ms field — JSONL schema regression",
        )
        mean = statistics.mean(time_values[:SAMPLE_FLOOR])
        self.assertLess(
            mean,
            MEAN_BUDGET_MS,
            f"mean rebuild time {mean:.1f}ms exceeds {MEAN_BUDGET_MS}ms budget",
        )


if __name__ == "__main__":
    unittest.main()
