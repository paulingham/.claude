"""Slice B — Multi-Persona Divergence Miner Consumer in `/learn`.

Tests `hooks/_lib/learn_anti_pattern_mining.py`'s extension to consume
`phases.patch_critic.rounds` and `phases.patch_critic.persona_rejections`.

Acceptance criteria covered (per `pipeline-state/wave5-followups/plan.md`
§ Slice B):

- Tier 0 #1: `_PERSONA_TO_ROLE` module-load contract (dict equality).
- B1: gate fires on patch-critic-only rounds.
- B2: legacy-record skip preserved (regression invariant — first in dep order).
- B3: default roles preserved on review-only path (second regression invariant).
- B4-B6: per-persona role tagging REPLACES default roles (M3 resolution).
- B7: multi-persona union rendered alphabetically (M5 resolution).
- B10: defensive parsing of malformed `persona_rejections` shapes.
- B10-L1: unknown persona silently skipped from role-tagging path.
- Tier 0 #2: valid persona-rejection schema round-trips through gate.
- B8: Step 3d body documents OR-gate.
- B9: Step 3d body documents persona-categorical roles mapping.

Plus a 13th challenger-recommended test (Slice B Finding 2): a mixed
cross-pipeline cluster (some pipelines persona-pathed, some review-only)
emits with persona-only roles when ANY contributing pipeline carries a
recognised persona — `test_mixed_path_cluster_persona_dominates`.

Helpers `_make_pipeline_obs`, `_write_observations`, `_emitted` follow
the architect-recommended pattern (scratchpad: pattern-3): copy / extend
the existing helpers from `tests/test_learn_anti_pattern_mining.py`,
adding `patch_critic_rounds` and `persona_rejections` kwargs.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from learn_anti_pattern_mining import mine_anti_patterns  # noqa: E402


def _make_pipeline_obs(pipeline_id, *, review_rounds=None,
                       patch_critic_rounds=None, persona_rejections=None,
                       scratchpad_findings=None):
    """Builder for a single synthetic pipeline observation record.

    Extends the helper from `tests/test_learn_anti_pattern_mining.py` with
    optional `patch_critic_rounds` and `persona_rejections` kwargs. Mirrors
    the production schema in `rules/_detail/autonomous-intelligence.md` §
    Field reference.

    `review_rounds=None` simulates a legacy record missing the
    `phases.review.rounds` field; `patch_critic_rounds=None` simulates a
    legacy record missing the `phases.patch_critic` block entirely.
    """
    record = {
        "record_type": "pipeline",
        "pipeline_id": pipeline_id,
        "scratchpad_findings": scratchpad_findings or [],
        "phases": {},
    }
    if review_rounds is not None:
        record["phases"]["review"] = {"rounds": review_rounds}
    if patch_critic_rounds is not None:
        block = {"rounds": patch_critic_rounds}
        if persona_rejections is not None:
            block["persona_rejections"] = persona_rejections
        record["phases"]["patch_critic"] = block
    return record


def _write_observations(tmp_path, records):
    """Write records to {tmp_path}/observations.jsonl (one per line)."""
    obs = tmp_path / "observations.jsonl"
    with obs.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return obs


def _emitted(tmp_path):
    """All anti-pattern files emitted into {tmp_path}/instincts/."""
    instincts_dir = tmp_path / "instincts"
    if not instincts_dir.exists():
        return []
    return sorted(instincts_dir.glob("anti-pattern-*.md"))


def _roles_line(text):
    """Extract the `roles: [...]` frontmatter line from a rendered file."""
    for line in text.splitlines():
        if line.startswith("roles:"):
            return line
    return ""


# ---------------------------------------------------------------------------
# Tier 0 #1 — `_PERSONA_TO_ROLE` mapping is canonical
# ---------------------------------------------------------------------------
class PersonaToRoleMappingIsCanonical(unittest.TestCase):
    """Tier 0 #1: module-load contract.

    `from learn_anti_pattern_mining import _PERSONA_TO_ROLE` returns
    exactly the three canonical entries (dict equality).
    """

    def test_persona_to_role_mapping_is_canonical(self):
        from learn_anti_pattern_mining import _PERSONA_TO_ROLE
        self.assertEqual(_PERSONA_TO_ROLE, {
            "correctness": "patch-critic-correctness",
            "regression-risk": "patch-critic-regression",
            "scope-creep": "patch-critic-scope",
        })


# ---------------------------------------------------------------------------
# B2 — Legacy-record skip preserved (regression invariant, first in dep order)
# ---------------------------------------------------------------------------
class LegacyRecordMissingBothRoundsSkipped(unittest.TestCase):
    """B2: regression invariant.

    Observations missing BOTH `phases.review.rounds` AND
    `phases.patch_critic.rounds` (or both null) are still skipped.
    Legacy records must not be coerced to 0.
    """

    def test_legacy_record_missing_both_rounds_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: legacy record absence"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"legacy-{n}",
                                   review_rounds=None,
                                   patch_critic_rounds=None,
                                   scratchpad_findings=findings)
                for n in range(4)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            self.assertEqual(_emitted(tmp_path), [])


# ---------------------------------------------------------------------------
# B1 — Gate fires on patch-critic-only rounds
# ---------------------------------------------------------------------------
class GateFiresOnPatchCriticRoundsOnly(unittest.TestCase):
    """B1: an observation with `review.rounds=1` AND
    `patch_critic.rounds=2` AND non-empty findings clears the gate
    (i.e. contributes to a cluster). Three such pipelines → emission.
    """

    def test_gate_fires_on_patch_critic_rounds_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: patch critic gate signal"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}",
                                   review_rounds=1,
                                   patch_critic_rounds=2,
                                   scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            self.assertEqual(len(_emitted(tmp_path)), 1)


# ---------------------------------------------------------------------------
# B3 — Default roles preserved on review-only path (regression invariant)
# ---------------------------------------------------------------------------
class ReviewOnlyPathKeepsDefaultRoles(unittest.TestCase):
    """B3: a cluster where every contributing observation has
    `review.rounds >= 2` and EITHER no `phases.patch_critic` block OR
    `persona_rejections` is empty/absent emits an instinct with the
    default roles `[software-engineer, frontend-engineer]`.
    """

    def test_review_only_path_keeps_default_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: review only path signal"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}",
                                   review_rounds=2,
                                   scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            text = files[0].read_text()
            roles_line = _roles_line(text)
            self.assertIn("software-engineer", roles_line)
            self.assertIn("frontend-engineer", roles_line)
            self.assertNotIn("patch-critic-", roles_line)


# ---------------------------------------------------------------------------
# B4 — Correctness persona REPLACES default roles
# ---------------------------------------------------------------------------
class CorrectnessPersonaReplacesDefaultRoles(unittest.TestCase):
    """B4 (M3): persona path REPLACES default roles, never unions.

    `agents/patch-critic.md::instinct_categories` does not include
    `software-engineer`/`frontend-engineer`; emitting persona-only
    tokens lands the instinct at patch-critic spawns and nowhere else.
    """

    def test_correctness_persona_replaces_default_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rejections = [{"persona": "correctness", "dimension": 1,
                           "severity": "HIGH"}]
            findings = ["warning: correctness persona signal"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}",
                                   patch_critic_rounds=2,
                                   persona_rejections=rejections,
                                   scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            roles_line = _roles_line(files[0].read_text())
            self.assertIn("patch-critic-correctness", roles_line)
            self.assertNotIn("software-engineer", roles_line)
            self.assertNotIn("frontend-engineer", roles_line)


# ---------------------------------------------------------------------------
# B5 — Regression-risk persona REPLACES default roles
# ---------------------------------------------------------------------------
class RegressionRiskPersonaReplacesDefaultRoles(unittest.TestCase):
    """B5: same as B4 with `persona:regression-risk`."""

    def test_regression_risk_persona_replaces_default_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rejections = [{"persona": "regression-risk", "dimension": 2,
                           "severity": "HIGH"}]
            findings = ["warning: regression risk persona signal"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}",
                                   patch_critic_rounds=2,
                                   persona_rejections=rejections,
                                   scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            roles_line = _roles_line(files[0].read_text())
            self.assertIn("patch-critic-regression", roles_line)
            self.assertNotIn("software-engineer", roles_line)
            self.assertNotIn("frontend-engineer", roles_line)


# ---------------------------------------------------------------------------
# B6 — Scope-creep persona REPLACES default roles
# ---------------------------------------------------------------------------
class ScopeCreepPersonaReplacesDefaultRoles(unittest.TestCase):
    """B6: same as B4 with `persona:scope-creep`."""

    def test_scope_creep_persona_replaces_default_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rejections = [{"persona": "scope-creep", "dimension": 3,
                           "severity": "MEDIUM"}]
            findings = ["warning: scope creep persona signal"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(f"pipe-{n}",
                                   patch_critic_rounds=2,
                                   persona_rejections=rejections,
                                   scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            roles_line = _roles_line(files[0].read_text())
            self.assertIn("patch-critic-scope", roles_line)
            self.assertNotIn("software-engineer", roles_line)
            self.assertNotIn("frontend-engineer", roles_line)


# ---------------------------------------------------------------------------
# B7 — Multi-persona union rendered alphabetically (deterministic order)
# ---------------------------------------------------------------------------
class MultiPersonaUnionAlphabetical(unittest.TestCase):
    """B7 (M5): multi-persona union rendered alphabetically for diff
    stability. Same input produces same `roles:` line regardless of
    observation arrival order.
    """

    def test_multi_persona_union_alphabetical(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: multi persona union signal"]
            # Pipeline 1 rejects on regression-risk; pipeline 2 on
            # correctness; pipeline 3 on regression-risk again. All
            # three contribute to the SAME cluster (same finding); the
            # union is `{correctness, regression-risk}` and renders as
            # `[patch-critic-correctness, patch-critic-regression]`.
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(
                    "pipe-1", patch_critic_rounds=2,
                    persona_rejections=[
                        {"persona": "regression-risk", "dimension": 2,
                         "severity": "HIGH"}],
                    scratchpad_findings=findings),
                _make_pipeline_obs(
                    "pipe-2", patch_critic_rounds=2,
                    persona_rejections=[
                        {"persona": "correctness", "dimension": 1,
                         "severity": "HIGH"}],
                    scratchpad_findings=findings),
                _make_pipeline_obs(
                    "pipe-3", patch_critic_rounds=2,
                    persona_rejections=[
                        {"persona": "regression-risk", "dimension": 2,
                         "severity": "HIGH"}],
                    scratchpad_findings=findings),
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            roles_line = _roles_line(files[0].read_text())
            self.assertIn("patch-critic-correctness", roles_line)
            self.assertIn("patch-critic-regression", roles_line)
            # Alphabetical: correctness BEFORE regression in the rendered line.
            correctness_idx = roles_line.find("patch-critic-correctness")
            regression_idx = roles_line.find("patch-critic-regression")
            self.assertLess(correctness_idx, regression_idx,
                            "alphabetical order required for diff stability")
            self.assertNotIn("software-engineer", roles_line)
            self.assertNotIn("frontend-engineer", roles_line)


# ---------------------------------------------------------------------------
# B10 — Defensive parsing of malformed `persona_rejections` shapes
# ---------------------------------------------------------------------------
class MalformedPersonaRejectionsSilentlySkipped(unittest.TestCase):
    """B10: malformed shapes silently skipped from the role-tagging
    path. `persona_rejections` not a list, entry missing `persona` key,
    `persona: null`, `persona` not a string — all silently skipped. The
    mining loop MUST NOT raise.
    """

    def test_malformed_persona_rejections_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: malformed shapes regression"]
            # Each pipeline has malformed persona rejections in
            # different shapes. The gate clears via patch_critic.rounds
            # but the role-tagging path silently skips every entry,
            # so the cluster does not emit a persona-tagged file
            # (no derivable role from the patch-critic branch); review
            # branch does not clear (review.rounds absent), so no
            # default-roles emission either. Result: no file.
            malformed_shapes = [
                "not-a-list",                                         # B10a
                [{"dimension": 1}],                                   # B10b
                [{"persona": None, "dimension": 2}],                  # B10c
                [{"persona": 42, "dimension": 3}],                    # B10d
            ]
            obs_records = []
            for n, shape in enumerate(malformed_shapes):
                obs_records.append(_make_pipeline_obs(
                    f"malformed-{n}",
                    patch_critic_rounds=2,
                    persona_rejections=shape,
                    scratchpad_findings=findings))
            obs = _write_observations(tmp_path, obs_records)
            # Must NOT raise.
            written = mine_anti_patterns(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            # No persona-tagged file emitted; review-rounds branch absent
            # so the gate clears via patch_critic-only path which yields
            # no role tags from any malformed entry.
            self.assertEqual(written, [])

    def test_malformed_alongside_valid_sibling_observations_still_works(self):
        """Valid sibling observations on the same cluster still emit."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: mixed malformed plus valid signal"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(
                    "pipe-1", patch_critic_rounds=2,
                    persona_rejections="not-a-list",
                    scratchpad_findings=findings),
                _make_pipeline_obs(
                    "pipe-2", patch_critic_rounds=2,
                    persona_rejections=[
                        {"persona": "correctness", "dimension": 1,
                         "severity": "HIGH"}],
                    scratchpad_findings=findings),
                _make_pipeline_obs(
                    "pipe-3", patch_critic_rounds=2,
                    persona_rejections=[
                        {"persona": "correctness", "dimension": 1,
                         "severity": "HIGH"}],
                    scratchpad_findings=findings),
            ])
            written = mine_anti_patterns(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            # Cluster recurs across 3 distinct pipelines; persona-only
            # role tag derived from the two valid contributors.
            self.assertEqual(len(written), 1)
            roles_line = _roles_line(written[0].read_text())
            self.assertIn("patch-critic-correctness", roles_line)
            self.assertNotIn("software-engineer", roles_line)


# ---------------------------------------------------------------------------
# B10-L1 — Unknown persona silently skipped from role-tagging path
# ---------------------------------------------------------------------------
class UnknownPersonaSilentlySkippedDefaultRolesWhenReviewPathClears(
        unittest.TestCase):
    """B10-L1: unknown persona (not in `_PERSONA_TO_ROLE`) is treated
    as malformed and silently skipped from the role-tagging path.

    - When the gate ALSO clears via `review.rounds >= 2` on the same
      observation: cluster emits with default roles.
    - When the gate clears ONLY via `patch_critic.rounds >= 2` and
      ALL persona entries are unknown/malformed: cluster does NOT
      emit a persona-tagged file (no derivable role).
    """

    def test_unknown_persona_with_review_clear_emits_default_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: unknown persona review path clear"]
            unknown = [{"persona": "accessibility-strict", "dimension": 1,
                        "severity": "HIGH"}]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(
                    f"pipe-{n}",
                    review_rounds=2,
                    patch_critic_rounds=2,
                    persona_rejections=unknown,
                    scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            roles_line = _roles_line(files[0].read_text())
            self.assertIn("software-engineer", roles_line)
            self.assertIn("frontend-engineer", roles_line)
            self.assertNotIn("patch-critic-", roles_line)

    def test_unknown_persona_only_patch_critic_path_no_emission(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: unknown persona patch critic only path"]
            unknown = [{"persona": "accessibility-strict", "dimension": 1,
                        "severity": "HIGH"}]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(
                    f"pipe-{n}",
                    patch_critic_rounds=2,
                    persona_rejections=unknown,
                    scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            written = mine_anti_patterns(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            # No file: the review-rounds branch did NOT clear (review
            # absent) and the patch-critic-only path produced no
            # derivable role (every persona is unknown).
            self.assertEqual(written, [])


# ---------------------------------------------------------------------------
# Tier 0 #2 — Valid persona-rejection schema round-trips through the gate
# ---------------------------------------------------------------------------
class ValidPersonaRejectionSchemaRoundTrips(unittest.TestCase):
    """Tier 0 #2: a `persona_rejections` entry with valid shape
    `{persona: str ∈ _PERSONA_TO_ROLE.keys(), dimension: int|str,
    severity: str ∈ {CRITICAL, HIGH, MEDIUM}}` passes the gate AND
    contributes to role tagging end-to-end.
    """

    def test_valid_persona_rejection_schema_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: schema round trip signal"]
            valid = [{"persona": "correctness", "dimension": 1,
                      "severity": "HIGH"}]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(
                    f"pipe-{n}",
                    patch_critic_rounds=2,
                    persona_rejections=valid,
                    scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            roles_line = _roles_line(files[0].read_text())
            self.assertIn("patch-critic-correctness", roles_line)


# ---------------------------------------------------------------------------
# Mixed-path cluster: persona dominates when ANY pipeline carries one
# (challenger-recommended 13th test, Slice B Finding 2)
# ---------------------------------------------------------------------------
class MixedPathClusterPersonaDominates(unittest.TestCase):
    """Cross-pipeline mixed-gate cluster. Spec: if ANY contributing
    pipeline carries a recognised persona, persona-only roles emit;
    else default roles. Documented in the production code's Step 3d
    body comment.

    Case: cluster across 3 pipelines where P1 has persona path
    (`correctness`), P2 has review-only path (no patch_critic block),
    P3 has persona path (`regression-risk`). Emitted roles: alphabetical
    union of `{correctness, regression-risk}` =
    `[patch-critic-correctness, patch-critic-regression]`. Default
    tokens excluded.
    """

    def test_mixed_path_cluster_persona_dominates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: mixed path cluster signal"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(
                    "pipe-1", patch_critic_rounds=2,
                    persona_rejections=[
                        {"persona": "correctness", "dimension": 1,
                         "severity": "HIGH"}],
                    scratchpad_findings=findings),
                _make_pipeline_obs(
                    "pipe-2", review_rounds=2,
                    scratchpad_findings=findings),
                _make_pipeline_obs(
                    "pipe-3", patch_critic_rounds=2,
                    persona_rejections=[
                        {"persona": "regression-risk", "dimension": 2,
                         "severity": "HIGH"}],
                    scratchpad_findings=findings),
            ])
            mine_anti_patterns(observations_path=obs,
                               instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1)
            roles_line = _roles_line(files[0].read_text())
            self.assertIn("patch-critic-correctness", roles_line)
            self.assertIn("patch-critic-regression", roles_line)
            self.assertNotIn("software-engineer", roles_line)
            self.assertNotIn("frontend-engineer", roles_line)


# ---------------------------------------------------------------------------
# Documentation regression: `skills/learn/SKILL.md` Step 3d body
# ---------------------------------------------------------------------------
def _step_3d_body():
    """Return the Step 3d body from `skills/learn/SKILL.md`.

    Extracts the section starting at `#### 3d. Anti-Pattern Mining`
    up to the next `### ` or `#### ` heading.
    """
    skill = (Path(__file__).resolve().parents[1]
             / "skills" / "learn" / "SKILL.md")
    text = skill.read_text()
    marker = "#### 3d. Anti-Pattern Mining"
    start = text.find(marker)
    assert start != -1, "Step 3d heading not found"
    rest = text[start:]
    # Find next `### ` or `#### ` heading after the start.
    cursor = len(marker)
    end = len(rest)
    while True:
        idx_h3 = rest.find("\n### ", cursor)
        idx_h4 = rest.find("\n#### ", cursor)
        candidates = [i for i in (idx_h3, idx_h4) if i != -1]
        if not candidates:
            break
        end = min(candidates)
        break
    return rest[:end]


class Step3dBodyDocumentsOrGate(unittest.TestCase):
    """B8: Step 3d prose contains both
    `phases.review.rounds >= 2` and `phases.patch_critic.rounds >= 2`
    in the same paragraph.
    """

    def test_step_3d_body_documents_or_gate(self):
        body = _step_3d_body()
        self.assertIn("phases.review.rounds >= 2", body)
        self.assertIn("phases.patch_critic.rounds >= 2", body)
        # "Same paragraph" = both tokens appear in a single contiguous
        # block separated only by inline whitespace/punctuation. We
        # check at least one paragraph contains both tokens.
        paragraphs = body.split("\n\n")
        same_paragraph = any(
            "phases.review.rounds >= 2" in p
            and "phases.patch_critic.rounds >= 2" in p
            for p in paragraphs)
        self.assertTrue(
            same_paragraph,
            "OR-gate clauses must appear in the same paragraph for B8")


class Step3dBodyDocumentsPersonaCategoricalRoles(unittest.TestCase):
    """B9: Step 3d prose mentions all three persona tokens AND all
    three role tokens.
    """

    def test_step_3d_body_documents_persona_categorical_roles(self):
        body = _step_3d_body()
        for persona in ("correctness", "regression-risk", "scope-creep"):
            self.assertIn(persona, body,
                          f"persona token {persona!r} missing from Step 3d")
        for role in ("patch-critic-correctness",
                     "patch-critic-regression",
                     "patch-critic-scope"):
            self.assertIn(role, body,
                          f"role token {role!r} missing from Step 3d")


if __name__ == "__main__":
    unittest.main()
