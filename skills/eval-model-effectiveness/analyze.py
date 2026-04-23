#!/usr/bin/env python3
"""CLI entry point for the model-effectiveness advisory analyser.

Reads pipeline observations + cost records, emits a markdown recommendation
report. Never modifies any agent config. See SKILL.md for semantics.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cells import build_subcells, group_cells  # noqa: E402
from cost_parse import read_costs  # noqa: E402
from decide import decide  # noqa: E402
from obs_parse import read_observations  # noqa: E402
from paths import costs_path, obs_path, out_path, resolve_phash  # noqa: E402
from report import overall_verdict, render_report  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Model effectiveness advisory analyser")
    p.add_argument("--project-hash", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--obs-path", default=None)
    p.add_argument("--costs-path", default=None)
    return p.parse_args()


def _run(args: argparse.Namespace) -> int:
    phash = resolve_phash(args.project_hash)
    obs = read_observations(obs_path(args.obs_path, phash))
    costs = read_costs(costs_path(args.costs_path))
    grouped = group_cells(build_subcells(costs, obs))
    decisions = [decide(r, c, scs) for (r, c), scs in sorted(grouped.items())]
    out = out_path(args.out, phash)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(decisions))
    print(f"VERDICT: {overall_verdict(decisions)}")
    return 0


if __name__ == "__main__":
    sys.exit(_run(_parse_args()))
