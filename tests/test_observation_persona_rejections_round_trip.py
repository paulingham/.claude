"""AC7: producer→consumer end-to-end activation test.

This is the load-bearing test that proves PR #105's
`mine_anti_patterns` consumer is no longer dead code. It builds
synthetic observation records matching the documented producer schema
(per `rules/_detail/autonomous-intelligence.md` § Field reference) and
asserts they flow through the consumer end-to-end:

- multi-persona path: emits an instinct file with persona-categorical
  `roles:` line containing `patch-critic-correctness`.
- single-critic path (sibling case): omits `persona_rejections` (NOT
  `null`); cluster still emits via the review-rounds gate with
  default roles, NOT dropped by the B10-L1 cluster-drop path.

Helpers reused via direct import from
`tests/test_learn_anti_pattern_persona_rejections.py`:
`_make_pipeline_obs`, `_write_observations`, `_emitted`.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from learn_anti_pattern_mining import mine_anti_patterns  # noqa: E402

# Reuse the canonical helpers from the consumer test suite.
from test_learn_anti_pattern_persona_rejections import (  # noqa: E402
    _emitted, _make_pipeline_obs, _write_observations,
)


def _roles_line(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("roles:"):
            return line
    return ""


class TestEndToEndProducerToConsumerActivation(unittest.TestCase):
    """AC7 main: a 3-pipeline observation set produced according to
    the documented schema (multi-persona, persona=correctness,
    severity=HIGH, patch_critic_rounds=2, identical scratchpad
    finding) emits a persona-tagged instinct.
    """

    def test_synthetic_3_pipeline_correctness_emits_persona_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = [
                "warning: synthetic activation correctness signal"]
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
            mine_anti_patterns(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(len(files), 1,
                             "exactly one cluster expected")
            text = files[0].read_text()
            roles_line = _roles_line(text)
            self.assertIn("patch-critic-correctness", roles_line,
                          "persona-categorical role missing")
            self.assertNotIn("software-engineer", roles_line,
                             "default role must NOT appear")
            self.assertNotIn("frontend-engineer", roles_line,
                             "default role must NOT appear")

    def test_single_critic_absent_field_falls_back_to_default_roles(
            self):
        """Sibling case: 3 records with `phases.patch_critic.{verdict,
        rounds, mode: "single-critic"}` AND NO `persona_rejections`
        key, AND `phases.review.rounds=2`. Cluster emits via the
        review-rounds gate with DEFAULT roles, NOT dropped by the
        B10-L1 path.

        This pins the single-critic contract: omitting
        `persona_rejections` (vs. setting it to null) must NOT
        trigger the B10-L1 unknown-persona cluster-drop.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: single critic mode signal"]
            obs = _write_observations(tmp_path, [
                _make_pipeline_obs(
                    f"pipe-{n}",
                    review_rounds=2,
                    patch_critic_rounds=1,  # single-critic, 1 round
                    persona_rejections=None,  # omitted, NOT null
                    scratchpad_findings=findings)
                for n in (1, 2, 3)
            ])
            mine_anti_patterns(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            files = _emitted(tmp_path)
            self.assertEqual(
                len(files), 1,
                "single-critic mode must emit via review-rounds gate")
            roles_line = _roles_line(files[0].read_text())
            self.assertIn("software-engineer", roles_line,
                          "default role missing")
            self.assertIn("frontend-engineer", roles_line,
                          "default role missing")
            self.assertNotIn("patch-critic-", roles_line,
                             "persona role must NOT appear in "
                             "single-critic mode")


if __name__ == "__main__":
    unittest.main()
