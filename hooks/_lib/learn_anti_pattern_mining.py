"""Anti-pattern mining for `/learn` Step 3d.

Gates pipeline observations on
`phases.review.rounds >= 2 OR phases.patch_critic.rounds >= 2`
(legacy records missing both fields are skipped, never coerced to 0),
clusters scratchpad findings by `sha1(category + ":" + summary)[:8]`,
and emits one anti-pattern instinct file per cluster recurring across
THREE+ distinct pipelines.

Confidence formula: `min(0.85, floor + 0.05 * (N - 3))` where `floor`
is resolved from the domain-weighted `_DOMAIN_FLOOR` map; cap is
uniform at 0.85 (architecture/security caps at N=6; workflow at N=10).

Persona-categorical role tagging (Slice B): the emitted instinct's
`roles:` is the persona-categorical token(s) drawn from
`phases.patch_critic.persona_rejections[].persona` via
`_PERSONA_TO_ROLE`, REPLACING the default
`[software-engineer, frontend-engineer]` (M3). Multi-persona union
rendered alphabetically (M5). Mixed-path rule: if ANY contributing
pipeline carries a recognised persona, persona-only roles emit; else
defaults. Clusters whose gate cleared ONLY via patch-critic AND have
no recognised persona are dropped (B10-L1).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Optional

# Persona → role mapping and helpers live in a sibling module so this
# file stays under the harness 300-line cap and persona handling can
# evolve independently. Re-exported here for backward-compat with
# callers (and tests) that import `_PERSONA_TO_ROLE` directly from this
# module.
from learn_persona_roles import (  # noqa: F401
    _DEFAULT_ROLES,
    _PERSONA_TO_ROLE,
    _emits,
    _empty_cluster,
    _has_persona_rejections_field,
    _persona_role_tokens,
    _resolve_roles,
)

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


def _patch_critic_rounds(observation: dict) -> Optional[int]:
    """Return `phases.patch_critic.rounds` or None when absent.

    Slice B: an observation predating the patch-critic emitter has the
    block missing entirely. Absent is NOT zero — only an explicit
    `rounds == 0` would be coerced.
    """
    return (observation.get("phases", {})
                       .get("patch_critic", {})
                       .get("rounds"))


def _gate_clauses(observation: dict) -> tuple[bool, bool]:
    """Return (review_clears, patch_critic_clears) for the OR-clause gate.

    Slice B: gate is `phases.review.rounds >= 2 OR
    phases.patch_critic.rounds >= 2`. Both clauses are tracked
    separately because emission requires the cluster to ALSO have a
    derivable role tag — when ALL contributing observations clear
    only via the patch-critic clause AND no recognised persona is
    present, the cluster has no role to emit and is dropped (B10-L1).
    """
    review_rounds = _rounds(observation)
    patch_critic_rounds = _patch_critic_rounds(observation)
    review_clears = review_rounds is not None and review_rounds >= 2
    patch_critic_clears = (patch_critic_rounds is not None
                           and patch_critic_rounds >= 2)
    return review_clears, patch_critic_clears


def _passes_gate(observation: dict) -> bool:
    """Iron-law gate: mine from rounds >= 2 pipelines.

    Slice B extension: gate is the OR clause
    `phases.review.rounds >= 2 OR phases.patch_critic.rounds >= 2`.
    Records missing BOTH fields are skipped (legacy invariant — never
    coerced to 0).
    """
    review_clears, patch_critic_clears = _gate_clauses(observation)
    return review_clears or patch_critic_clears


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
    """Build cluster records from gated observations.

    Returns `{cluster_key: {category, summary, pipeline_ids,
    persona_tokens, any_review_clear}}`. `persona_tokens` is the
    union of persona-tagged role tokens contributed by every
    observation in this cluster (Slice B). `any_review_clear` is
    True when at least one contributing observation cleared the
    gate via `phases.review.rounds >= 2` — the caller uses this to
    decide whether the review-only path falls back to default roles
    or whether the cluster should be dropped (B10-L1: gate cleared
    only via patch-critic AND no recognised persona).
    """
    clusters: dict = {}
    for obs in observations:
        review_clears, patch_critic_clears = _gate_clauses(obs)
        if not (review_clears or patch_critic_clears):
            continue
        pipeline_id = obs.get("pipeline_id")
        if pipeline_id is None:
            continue
        obs_persona_tokens = _persona_role_tokens(obs)
        obs_has_rejections_field = _has_persona_rejections_field(obs)
        for finding in obs.get("scratchpad_findings") or []:
            parsed = _parse_finding(finding)
            if parsed is None:
                continue
            category, summary = parsed
            key = _cluster_key(category, summary)
            entry = clusters.setdefault(key, _empty_cluster(category, summary))
            entry["pipeline_ids"].add(pipeline_id)
            entry["persona_tokens"].update(obs_persona_tokens)
            if review_clears:
                entry["any_review_clear"] = True
            if obs_has_rejections_field:
                entry["any_persona_rejections_field"] = True
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
    # Slice B: persona path REPLACES defaults (M3). Multi-persona union
    # rendered alphabetically (M5 — diff stability). Mixed-path rule:
    # if ANY contributing pipeline has a recognised persona, persona
    # roles emit; else defaults.
    roles = _resolve_roles(cluster.get("persona_tokens", set()))
    roles_yaml = "[" + ", ".join(roles) + "]"
    return (
        "---\n"
        f"id: anti-pattern-{key}\n"
        f"category: anti-pattern\n"
        f"roles: {roles_yaml}\n"
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
        if len(cluster["pipeline_ids"]) < _RECURRENCE_THRESHOLD:
            continue
        if not _emits(cluster):
            # B10-L1: gate cleared only via patch-critic AND every
            # persona was unknown/malformed — no role tag derivable,
            # cluster dropped.
            continue
        written.append(_write_cluster(Path(instincts_dir), key, cluster))
    return written
