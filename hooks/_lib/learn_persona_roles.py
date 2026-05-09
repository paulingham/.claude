"""Persona-categorical role tagging for `/learn` Step 3d (Slice B).

Translates `phases.patch_critic.persona_rejections` entries on a
pipeline observation into the role-name tokens consumed by the
instinct-injector's per-agent `instinct_categories:` filter
(see `agents/patch-critic.md` lines 14-19 for the role tokens).

The mapping is canonical and single-sourced as `_PERSONA_TO_ROLE`.
When a future persona is added the mapping AND
`agents/patch-critic.md::instinct_categories` MUST update in lockstep
(Tier 0 round-trip + agent-frontmatter snapshot tests catch drift in
either direction).

Persona path REPLACES the default `[software-engineer, frontend-engineer]`
roles list (M3 — never unions). When a cluster has NO persona signal
across ANY contributing observation, the caller falls back to defaults.
"""
from __future__ import annotations


# Default roles for the review-only path — preserved for backward
# compatibility with existing pipelines whose anti-patterns have never
# carried a persona signal.
_DEFAULT_ROLES = ["software-engineer", "frontend-engineer"]


# Slice B canonical mapping: persona name (as written by the patch-critic
# in `phases.patch_critic.persona_rejections[].persona`) → role-name
# token consumed by the instinct-injector's per-agent
# `instinct_categories:` filter.
_PERSONA_TO_ROLE = {
    "correctness": "patch-critic-correctness",
    "regression-risk": "patch-critic-regression",
    "scope-creep": "patch-critic-scope",
}


def _has_persona_rejections_field(observation: dict) -> bool:
    """True when the observation declares a `persona_rejections` field.

    Distinguishes "patch-critic ran but produced no persona signal"
    (field absent → default roles) from "patch-critic produced data
    but it was malformed" (field present, every entry malformed →
    cluster dropped if review path also did not clear). This is the
    semantic distinction between B1 (no rejections at all) and B10
    (rejections present but all malformed/unknown).
    """
    pc = observation.get("phases", {}).get("patch_critic", {})
    return isinstance(pc, dict) and "persona_rejections" in pc


def _persona_role_tokens(observation: dict) -> set[str]:
    """Extract recognised persona-categorical role tokens for one observation.

    Walks `phases.patch_critic.persona_rejections` and returns the SET
    of mapped role tokens for entries whose `persona` field is in
    `_PERSONA_TO_ROLE`. Malformed entries (non-list rejections, missing
    `persona` key, non-string `persona`, unknown persona) are silently
    skipped from the role-tagging path. Returns the empty set when no
    valid mapping is derivable — the caller falls back to default
    roles iff the entire cluster has no persona signal.

    The defensive try/except guards against deeper pathologies in
    user-supplied data (e.g. mock objects with surprising `__getitem__`,
    iterables that raise mid-walk). Mining is best-effort; one bad
    record must not crash the loop.
    """
    rejections = (observation.get("phases", {})
                              .get("patch_critic", {})
                              .get("persona_rejections"))
    if not isinstance(rejections, list):
        return set()
    tokens: set[str] = set()
    for entry in rejections:
        token = _entry_role_token(entry)
        if token is not None:
            tokens.add(token)
    return tokens


def _entry_role_token(entry):
    """Return the role token for one rejection entry, or None if malformed."""
    try:
        if not isinstance(entry, dict):
            return None
        persona = entry.get("persona")
        if not isinstance(persona, str):
            return None
        # Unknown persona (B10-L1) — silently skip from the
        # role-tagging path. `dict.get` returns None for unknowns.
        return _PERSONA_TO_ROLE.get(persona)
    except Exception:  # pragma: no cover (defensive guard)
        # Defensive: pathological entry shapes (mock objects, custom
        # __getitem__) must not break mining. Not killable by manual
        # mutation without explicit fault injection.
        return None


def _resolve_roles(persona_tokens: set[str]) -> list[str]:
    """Choose roles for a cluster: persona path REPLACES defaults.

    M3 resolution: persona path REPLACES, never unions with, defaults.
    M5 resolution: union of persona tokens rendered alphabetically for
    diff stability.
    Mixed-path rule: if ANY contributing pipeline carries a recognised
    persona, persona-only roles emit; else default roles.
    """
    if persona_tokens:
        return sorted(persona_tokens)
    return list(_DEFAULT_ROLES)


def _empty_cluster(category: str, summary: str) -> dict:
    """Initial cluster record used by `_collect_clusters`."""
    return {"category": category, "summary": summary,
            "pipeline_ids": set(),
            "persona_tokens": set(),
            "any_review_clear": False,
            "any_persona_rejections_field": False}


def _emits(cluster: dict) -> bool:
    """Decide whether a recurrence-3+ cluster has a derivable role tag.

    Three emission paths:
      (1) any contributing obs cleared via review.rounds (default roles)
      (2) at least one recognised persona resolved (persona roles)
      (3) gate cleared via patch-critic AND no persona_rejections field
          present anywhere in the cluster (default roles — patch-critic
          ran but produced no persona signal yet)

    Dropped: gate cleared ONLY via patch-critic AND every contributing
    observation carried a persona_rejections field BUT every entry was
    malformed or unknown — no derivable role tag (B10/B10-L1).
    """
    if cluster.get("any_review_clear", False):
        return True
    if cluster.get("persona_tokens"):
        return True
    return not cluster.get("any_persona_rejections_field", False)
