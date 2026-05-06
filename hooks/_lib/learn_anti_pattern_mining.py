"""C8 S4 — anti-pattern mining for `/learn` Step 3d.

Reads pipeline observations, gates on `phases.review.rounds >= 2`
(legacy/missing field is skipped, NOT coerced to 0), parses each
flat-string scratchpad finding into `(category, summary)`, clusters
by `sha1(category + ":" + summary_normalised)[:8]`, and emits one
anti-pattern instinct file per cluster recurring across at least
THREE distinct pipelines.

Cluster key normalisation strips digits and whitespace from the first
80 chars of the lowercased summary — coarsens noisy free-text into a
stable cluster identifier without depending on producer-side
file-glob metadata that does not yet exist.

Confidence formula: `min(0.85, floor + 0.05 * (N - 3))` where N is
the number of distinct pipelines exhibiting the cluster and `floor`
is resolved from the domain-weighted `_DOMAIN_FLOOR` map (workflow=0.5,
testing=0.6, code-style=0.6, architecture=0.7, security=0.7;
unknown→`_DEFAULT_FLOOR=0.5`). Three pipelines at the workflow floor →
0.5 (lowest confidence anti-patterns ship at); architecture/security
domains start at 0.7 because failures there are higher-stakes. The cap
(0.85) is uniform across domains — higher-floor domains reach it with
fewer recurrences (architecture caps at N=6, testing/code-style at
N=8, workflow at N=10).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Optional

# Maps the parsed `category:` prefix on a scratchpad finding to the
# domain field on the emitted anti-pattern instinct. Default "workflow"
# for unrecognised prefixes — keeps unknown findings behind a sensible
# default rather than silently dropping the cluster.
_DOMAIN_BY_CATEGORY = {
    "warning": "workflow",
    "fragility": "architecture",
    "discovery": "workflow",
    "decision": "architecture",
    "pattern": "workflow",
}
_DEFAULT_DOMAIN = "workflow"
_RECURRENCE_THRESHOLD = 3
# Per-domain confidence floor for anti-pattern instincts. Higher floors
# encode "higher-stakes domain" — architecture and security failures
# should ship at confidence 0.7 from the first qualifying recurrence,
# while workflow noise starts at the conservative 0.5. Cap is uniform
# at 0.85 across all domains; higher-floor domains reach it sooner.
_DOMAIN_FLOOR = {
    "workflow": 0.5,
    "testing": 0.6,
    "code-style": 0.6,
    "architecture": 0.7,
    "security": 0.7,
}
# Fallback when a domain is absent from `_DOMAIN_FLOOR` (defensive
# default for forward-compatibility with future category additions).
_DEFAULT_FLOOR = 0.5
_CONFIDENCE_STEP = 0.05
_CONFIDENCE_CAP = 0.85
_BODY_CAP_CHARS = 200
_SUMMARY_PREFIX_CHARS = 80
_NORMALISE = re.compile(r"[\d\s]+")


def _rounds(observation: dict) -> Optional[int]:
    """Return `phases.review.rounds` or None when absent (legacy record)."""
    return observation.get("phases", {}).get("review", {}).get("rounds")


def _passes_gate(observation: dict) -> bool:
    """Iron-law gate: only mine from rounds >= 2 pipelines."""
    rounds = _rounds(observation)
    return rounds is not None and rounds >= 2


def _parse_finding(finding: str) -> Optional[tuple[str, str]]:
    """Split `"category: summary text"` into (category, summary).

    Returns None when the string lacks the `": "` separator — that
    indicates a malformed finding and the cluster cannot be keyed.
    """
    if ": " not in finding:
        return None
    category, summary = finding.split(": ", 1)
    return category.strip(), summary.strip()


def _summary_normalised(summary: str) -> str:
    """Strip digits + whitespace from the first 80 lowercased chars."""
    return _NORMALISE.sub("", summary.lower()[:_SUMMARY_PREFIX_CHARS])


def _cluster_key(category: str, summary: str) -> str:
    """Stable 8-hex-char hash of (category, normalised summary)."""
    payload = f"{category}:{_summary_normalised(summary)}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:8]


def _domain_for(category: str) -> str:
    return _DOMAIN_BY_CATEGORY.get(category, _DEFAULT_DOMAIN)


def _confidence_for(distinct_pipeline_count: int, domain: str) -> float:
    floor = _DOMAIN_FLOOR.get(domain, _DEFAULT_FLOOR)
    raw = floor + _CONFIDENCE_STEP * (
        distinct_pipeline_count - _RECURRENCE_THRESHOLD)
    return min(_CONFIDENCE_CAP, raw)


def _read_observations(observations_path: Path) -> Iterable[dict]:
    """Yield one dict per JSONL line; skip blank or unparseable lines."""
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
                # Mining is a best-effort scan — never crash the loop on
                # one malformed line.
                continue


def _collect_clusters(observations: Iterable[dict]) -> dict:
    """Build {cluster_key: {category, summary, pipeline_ids}} from gated obs."""
    clusters: dict = {}
    for obs in observations:
        if not _passes_gate(obs):
            continue
        pipeline_id = obs.get("pipeline_id")
        if pipeline_id is None:
            continue
        for finding in obs.get("scratchpad_findings") or []:
            parsed = _parse_finding(finding)
            if parsed is None:
                continue
            category, summary = parsed
            key = _cluster_key(category, summary)
            entry = clusters.setdefault(
                key, {"category": category, "summary": summary,
                      "pipeline_ids": set()})
            entry["pipeline_ids"].add(pipeline_id)
    return clusters


def _format_body(summary: str) -> str:
    """Render the `## Pattern` body line, capped at 200 chars."""
    template = (f"When you find yourself doing this, stop — review history "
                f"shows it triggers CHANGES_REQUESTED: {summary}")
    return template[:_BODY_CAP_CHARS]


def _render_instinct(key: str, cluster: dict) -> str:
    distinct = len(cluster["pipeline_ids"])
    # Resolve domain BEFORE computing confidence — confidence depends on
    # the domain-weighted floor, so the order is load-bearing.
    domain = _domain_for(cluster["category"])
    confidence = _confidence_for(distinct, domain)
    body = _format_body(cluster["summary"])
    return (
        "---\n"
        f"id: anti-pattern-{key}\n"
        f"category: anti-pattern\n"
        "roles: [software-engineer, frontend-engineer]\n"
        f"confidence: {confidence}\n"
        f"domain: {domain}\n"
        "---\n"
        "\n"
        "## Pattern\n"
        f"{body}\n"
    )


def _write_cluster(instincts_dir: Path, key: str, cluster: dict) -> Path:
    instincts_dir.mkdir(parents=True, exist_ok=True)
    path = instincts_dir / f"anti-pattern-{key}.md"
    path.write_text(_render_instinct(key, cluster))
    return path


def mine_anti_patterns(observations_path: Path,
                       instincts_dir: Path) -> list[Path]:
    """Mine `observations_path`, emit anti-pattern files into `instincts_dir`.

    Returns the list of files written (empty if no cluster cleared the
    recurrence threshold).
    """
    clusters = _collect_clusters(_read_observations(Path(observations_path)))
    written: list[Path] = []
    for key, cluster in sorted(clusters.items()):
        if len(cluster["pipeline_ids"]) >= _RECURRENCE_THRESHOLD:
            written.append(_write_cluster(Path(instincts_dir), key, cluster))
    return written
