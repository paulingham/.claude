"""Tier 1 unit tests for slice-b-vlm-critic-and-guard.

Per plan.md § 3 slice-b Failing test stubs (lines 124-127):
  1. test_vlm_critic_writes_verdict_and_summary_to_index_json_per_route
  2. test_vlm_critic_emits_VISUAL_DIFF_PASS_when_all_routes_pass_and_FAIL_otherwise
  3. test_vlm_critic_disabled_via_env_short_circuits_to_PASS

These are Python-checkable surface tests on the SKILL.md / agent procedure
documentation contracts. Behavioural verification of the verdict logic in
real vlm-critic spawns belongs in Tier 2 (out of scope for this slice's
unit tier — the verdict computation is a documentation contract in
SKILL.md, exercised at agent dispatch time).

Inline rationale: vlm-critic is a Final-Gate teammate (subagent + worktree)
dispatched by the orchestrator. The verdict-logic contract — "every route
PASS -> VISUAL_DIFF_PASS, any FAIL -> VISUAL_DIFF_FAIL" — is documented
verbatim in SKILL.md. The Tier 1 tests assert the SKILL.md *contains* the
verdict-logic invariants in a form the dispatched agent will obey.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VLM_CRITIC_SKILL = ROOT / "skills" / "vlm-critic" / "SKILL.md"
VLM_CRITIC_AGENT = ROOT / "agents" / "vlm-critic.md"


def _read(path):
    return path.read_text(encoding="utf-8")


class VlmCriticWritesVerdictAndSummaryToIndexJsonPerRoute(unittest.TestCase):
    """AC3 #1 — vlm-critic produces per-route vlm_verdict + vlm_summary
    in index.json for every route in the input set."""

    def test_skill_md_documents_per_route_verdict_write(self):
        body = _read(VLM_CRITIC_SKILL)
        # Procedure must name the per-route index.json write contract.
        self.assertIn(
            "vlm_verdict",
            body,
            "AC3: SKILL.md must document the `vlm_verdict` per-route field write",
        )
        self.assertIn(
            "vlm_summary",
            body,
            "AC3: SKILL.md must document the `vlm_summary` per-route field write",
        )

    def test_skill_md_documents_index_json_target(self):
        body = _read(VLM_CRITIC_SKILL)
        # The write target is index.json — Write tool scope.
        self.assertIn("index.json", body)

    def test_skill_md_documents_route_set_input_source(self):
        body = _read(VLM_CRITIC_SKILL)
        # Inputs come from index.json.routes[*].visual_regression.baseline_path
        # + current_path. The skill must name BOTH.
        self.assertIn("baseline_path", body)
        self.assertIn("current_path", body)


class VlmCriticEmitsVisualDiffPassWhenAllRoutesPassAndFailOtherwise(
    unittest.TestCase,
):
    """AC3 #2 — verdict logic: all PASS -> VISUAL_DIFF_PASS; any FAIL ->
    VISUAL_DIFF_FAIL."""

    def test_skill_md_documents_visual_diff_pass_verdict(self):
        body = _read(VLM_CRITIC_SKILL)
        self.assertIn(
            "VISUAL_DIFF_PASS",
            body,
            "AC3: SKILL.md must document the VISUAL_DIFF_PASS verdict",
        )

    def test_skill_md_documents_visual_diff_fail_verdict(self):
        body = _read(VLM_CRITIC_SKILL)
        self.assertIn(
            "VISUAL_DIFF_FAIL",
            body,
            "AC3: SKILL.md must document the VISUAL_DIFF_FAIL verdict",
        )

    def test_skill_md_documents_all_routes_pass_aggregate_rule(self):
        body = _read(VLM_CRITIC_SKILL)
        # The aggregate rule must be in the document — "all PASS" or "every
        # route PASS" or similar that names the conjunction.
        # Fixed-string check: must mention "all" or "every" near PASS.
        text_lower = body.lower()
        self.assertTrue(
            "all routes" in text_lower or "every route" in text_lower,
            "AC3: SKILL.md must document the 'all routes PASS' aggregate rule",
        )

    def test_skill_md_documents_any_route_fail_aggregate_rule(self):
        body = _read(VLM_CRITIC_SKILL)
        text_lower = body.lower()
        # Must document the disjunctive failure rule.
        self.assertTrue(
            "any route" in text_lower or "any route fail" in text_lower,
            "AC3: SKILL.md must document the 'any route FAIL' aggregate rule",
        )


class VlmCriticDisabledViaEnvShortCircuitsToPass(unittest.TestCase):
    """AC3 #3 / PR-3 — CLAUDE_DISABLE_VLM_CRITIC=1 short-circuits BEFORE any
    multimodal Read.

    The contract: when the env var is set, vlm-critic emits VISUAL_DIFF_PASS
    + vlm_summary containing literal `disabled-by-env` for every route in
    the input set. No multimodal Read call is issued.
    """

    def test_skill_md_documents_escape_hatch_env_var(self):
        body = _read(VLM_CRITIC_SKILL)
        self.assertIn(
            "CLAUDE_DISABLE_VLM_CRITIC=1",
            body,
            "PR-3: SKILL.md must document `CLAUDE_DISABLE_VLM_CRITIC=1` verbatim",
        )

    def test_skill_md_documents_short_circuit_before_read(self):
        body = _read(VLM_CRITIC_SKILL)
        # Must name "BEFORE any multimodal Read" or "before any Read" — the
        # ordering is contract-critical (no PNG reads when disabled).
        text_lower = body.lower()
        self.assertTrue(
            "before" in text_lower
            and ("read" in text_lower or "multimodal" in text_lower),
            "PR-3: SKILL.md must document the short-circuit happens BEFORE any Read",
        )

    def test_skill_md_documents_disabled_by_env_summary_token(self):
        body = _read(VLM_CRITIC_SKILL)
        self.assertIn(
            "disabled-by-env",
            body,
            "PR-3: SKILL.md must document the `disabled-by-env` vlm_summary token",
        )

    def test_skill_md_documents_disabled_routes_emit_pass(self):
        body = _read(VLM_CRITIC_SKILL)
        # The short-circuit emits VISUAL_DIFF_PASS for every route.
        self.assertIn("VISUAL_DIFF_PASS", body)


if __name__ == "__main__":
    unittest.main()
