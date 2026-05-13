"""Mine recurring SANDBOX_FAILED divergences as fragility instincts.

`/learn` Step 3 invokes `mine_sandbox_fragility` to scan
`observations.jsonl` for pipelines whose `phases.sandbox_verify` block
carries `verdict == "SANDBOX_FAILED"`. Each `diverging_tests` entry is
clustered by `sha1(test_name)[:8]`; clusters recurring across at least
3 distinct pipelines emit one fragility instinct per cluster.

Mirrors the design of `learn_anti_pattern_mining.mine_anti_patterns`:

- best-effort scan (malformed JSONL lines skipped, never raise — C5).
- filter via `sandbox_verify_observation.is_present` (NEVER coerce).
- 3-pipeline threshold matches the scratchpad → instinct promotion
  rule documented in `protocols/autonomous-intelligence.md`.
- confidence 0.5 (fragility seed — matches existing scratchpad rule).
- roles `[software-engineer, sandbox-verify-engineer]` so the instinct
  injects into both Build and sandbox-verify spawns.
- domain `testing`; category `fragility`.

Only SANDBOX_FAILED observations contribute. SANDBOX_VERIFIED and
SANDBOX_SKIPPED records are filtered out — VERIFIED has no divergence
to mine and SKIPPED is degraded-mode info, not signal.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from sandbox_verify_observation import is_present, read_sandbox_phase

_RECURRENCE_THRESHOLD = 3
_CONFIDENCE = 0.5
_DOMAIN = "testing"
_CATEGORY = "fragility"
_ROLES = ("software-engineer", "sandbox-verify-engineer")


def _test_name_hash(test_name: str) -> str:
    """Stable 8-hex-char hash for cluster keying."""
    return hashlib.sha1(test_name.encode("utf-8")).hexdigest()[:8]


def _read_observations(observations_path: Path) -> Iterable[dict]:
    """Yield one dict per JSONL line; skip blanks + malformed lines."""
    if not observations_path.exists():
        return
    with observations_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Best-effort scan — never crash on one malformed line.
                continue


def _collect_clusters(observations: Iterable[dict]) -> dict:
    """Build `{cluster_key: {test_name, pipeline_ids}}` from observations.

    Only SANDBOX_FAILED records contribute. Filter via `is_present`
    (NEVER coerce absence). Pipelines without a `pipeline_id` are
    skipped (cannot count toward distinct-pipeline threshold).
    """
    clusters: dict = {}
    for obs in observations:
        if not is_present(obs):
            continue
        block = read_sandbox_phase(obs)
        if not block or block.get("verdict") != "SANDBOX_FAILED":
            continue
        pipeline_id = obs.get("pipeline_id")
        if not pipeline_id:
            continue
        for test_name in block.get("diverging_tests") or []:
            if not isinstance(test_name, str) or not test_name:
                continue
            key = _test_name_hash(test_name)
            entry = clusters.setdefault(
                key, {"test_name": test_name, "pipeline_ids": set()})
            entry["pipeline_ids"].add(pipeline_id)
    return clusters


def _render_instinct(key: str, cluster: dict) -> str:
    """Render the fragility-instinct markdown for one cluster."""
    test_name = cluster["test_name"]
    distinct_pipelines = len(cluster["pipeline_ids"])
    roles_yaml = "[" + ", ".join(_ROLES) + "]"
    body = (
        f"Test `{test_name}` diverged between worktree and sandbox in "
        f"{distinct_pipelines} pipelines — likely timing-sensitive, "
        "environment-dependent, or carrying a hidden test-order coupling. "
        "Investigate the test's fixtures and isolation before re-running."
    )
    return (
        "---\n"
        f"id: fragility-sandbox-{key}\n"
        f"category: {_CATEGORY}\n"
        f"roles: {roles_yaml}\n"
        f"confidence: {_CONFIDENCE}\n"
        f"domain: {_DOMAIN}\n"
        "---\n"
        "\n"
        "## Pattern\n"
        f"{body}\n"
    )


def _write_cluster(instincts_dir: Path, key: str, cluster: dict) -> Path:
    instincts_dir.mkdir(parents=True, exist_ok=True)
    path = instincts_dir / f"fragility-sandbox-{key}.md"
    path.write_text(_render_instinct(key, cluster))
    return path


def mine_sandbox_fragility(observations_path: Path,
                           instincts_dir: Path) -> list[Path]:
    """Scan `observations_path`, emit fragility-instinct files.

    Returns the list of files written (empty when no cluster cleared
    the recurrence threshold).
    """
    clusters = _collect_clusters(_read_observations(Path(observations_path)))
    written: list[Path] = []
    for key, cluster in sorted(clusters.items()):
        if len(cluster["pipeline_ids"]) < _RECURRENCE_THRESHOLD:
            continue
        written.append(_write_cluster(Path(instincts_dir), key, cluster))
    return written
