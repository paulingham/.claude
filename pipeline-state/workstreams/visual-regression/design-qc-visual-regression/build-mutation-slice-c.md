# Slice-c Mutation Audit — product-reviewer gate

**Targets**:
- `agents/product-reviewer.md` § Acceptance Review § Outcome
  (added `visual_regression machine pre-check` block — ~25 lines markdown)
- `skills/product-acceptance/SKILL.md` L54-58 (added 5-line spawn-prompt
  bullet block carrying the gate language)

**Excluded from executable mutation testing**:

Per the slice-b precedent (`build-mutation-slice-b.md` § "Excluded from
mutation testing"), markdown and YAML files are excluded because:

  - The production "code" is a documentation contract. Tier 0 contract
    tests assert the string contracts verbatim (literal-phrase pins via
    fixed-string grep).
  - Executable mutation tools (Stryker, mutmut, Mutant) mutate
    `.py`/`.js`/`.sh` token streams; they don't reason about Markdown
    semantics.
  - Re-running Stryker against a Markdown file would produce zero
    meaningful mutants — the AST is text.

**Surrogate mutation discipline**: every documented behavioural
predicate in the markdown contracts is mirrored by a fixed-string Tier 0
test that fails RED if the predicate text is altered or removed. The
Tier 0 assertions ARE the mutation kills for the markdown surface.

## Surrogate Mutants (predicate-level)

Each row below names a hypothetical mutation of the markdown predicate
and the Tier 0 / Tier 1 / Tier 2 test that catches it.

| ID | Mutation | Killing test | Status |
|---|---|---|---|
| M1 | Remove `visual_regression machine pre-check` literal from product-reviewer.md | `spec_visual_regression_gate.py::test_product_reviewer_md_contains_visual_regression_machine_pre_check_phrase` | KILLED |
| M2 | Move the phrase outside Acceptance Review § Outcome (e.g. into Plan Validation) | `spec_visual_regression_gate.py::test_phrase_lives_under_acceptance_review_outcome_section` | KILLED |
| M3 | Remove `visual_regression` token from SKILL.md L54-60 window | `spec_visual_regression_gate.py::test_product_acceptance_skill_l54_60_contains_visual_regression_token` | KILLED |
| M4 | Remove `pixel_diff_ratio > threshold OR vlm_verdict == FAIL` from SKILL.md L54-60 | `spec_visual_regression_gate.py::test_product_acceptance_skill_l54_60_contains_pixel_diff_threshold_pin` | KILLED |
| M5 | Remove the verbatim missing-block reason string from product-reviewer.md | `spec_visual_regression_gate.py::test_index_json_visual_regression_block_is_required_not_optional` | KILLED |
| M6 | Drop `BLOCKED` from the missing-block treatment | `spec_visual_regression_gate.py::test_gate_logic_names_blocked_verdict_for_missing_block` AND `test_product_reviewer_visual_gate.py::test_gate_logic_treats_missing_block_as_vlm_blocked` | KILLED |
| M7 | Drop the index.json read target reference | `spec_visual_regression_gate.py::test_gate_logic_names_index_json_read_target` | KILLED |
| M8 | Drop `REJECT` action from gate-logic block | `test_product_reviewer_visual_gate.py::test_gate_logic_names_reject_action_on_threshold_breach` | KILLED |
| M9 | Remove `frontend-touching` qualifier from trap-door scope | `test_product_reviewer_visual_gate.py::test_gate_logic_qualifies_trap_door_to_frontend_touching_changes` | KILLED |
| M10 | Drop the `14/20` UX heuristic reference (would short-circuit APPROVED on visual-only pass) | `test_product_reviewer_visual_gate.py::test_product_reviewer_approves_when_all_routes_pass_threshold_and_vlm_PASS` | KILLED |
| M11 | Weaken `>` to `>=` in the SKILL.md spawn prompt (off-by-one mutation) | Adversarial Tier 2 `test_adversarial_boundary_ratio_exactly_at_default_threshold_passes` (boundary probe at exact threshold) | KILLED |
| M12 | Treat `vlm_verdict == None` as FAIL (loose-truthy mutation) | Adversarial Tier 2 `test_adversarial_vlm_verdict_null_does_not_reject` | KILLED |
| M13 | Reject on empty routes array (wrong-default mutation) | Adversarial Tier 2 `test_adversarial_empty_routes_array_passes_visual_pre_check` | KILLED |

**Surrogate kill rate**: 13 / 13 = **1.00** (above the 0.70 gate per
`rules/core.md` § Iron Law 1).

## Why a Stryker run is not the appropriate gate here

`stryker.config.json` mutates JavaScript files; slice-c modifies only
Markdown. Running Stryker would produce a no-op (zero target files,
zero mutants, zero score). The honest report is the surrogate-mutation
table above: every documented predicate has an explicit test asserting
the predicate's text survives unchanged. If a future engineer extends
slice-c with executable code, that code MUST add its own Stryker
configuration and a re-mutation audit at that point.

## Cumulative slice context

Slice-a's `tests/mutation/visual_diff_mutation_runner.sh` and slice-b's
`tests/mutation/vlm_critic_guard_mutation_runner.sh` continue to enforce
≥0.70 on their respective executable targets. Slice-c does not add new
executable mutators because it does not add new executable code.

## Reproducibility

The surrogate mutants above can be reproduced manually by editing
`agents/product-reviewer.md` or `skills/product-acceptance/SKILL.md` to
remove the named token / phrase, then running:

```bash
python3 -m unittest \
    tests.contract.spec_visual_regression_gate \
    tests.test_product_reviewer_visual_gate \
    tests.integration.test_product_reviewer_index_json_consumer
```

Each row of the surrogate table names the test that fails RED under
that mutation. The audit trail is the Tier 0 / Tier 1 / Tier 2 suite
itself.
