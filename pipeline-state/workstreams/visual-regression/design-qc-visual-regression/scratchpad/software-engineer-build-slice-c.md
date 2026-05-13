---
category: decision
---

**Slice-c scope is documentation + gate logic only — production "code"
changes live in two markdown files.**

slice-c is the consumer half of the AC3+AC4 atomicity pair. The only
production surfaces are:
- `agents/product-reviewer.md` Acceptance Review § Outcome (adds the
  literal phrase `visual_regression machine pre-check` + a gate-logic
  paragraph instructing the agent to read `pipeline-state/{task-id}/
  design-qc/index.json` and REJECT on threshold or vlm_verdict == FAIL,
  with fail-closed semantics on missing block).
- `skills/product-acceptance/SKILL.md` lines 54-60 spawn prompt (extends
  the existing Design QC screenshot review block with the literal
  phrases `visual_regression` and `pixel_diff_ratio > threshold OR
  vlm_verdict == FAIL` — both Tier 0 contract-asserted as fixed-string
  greps).

Because the production surface is plain markdown, the Tier 1 unit tests
necessarily assert *documentation contracts* (that the gate logic
described in the markdown exists in a form the dispatched product-reviewer
will obey) rather than running the gate logic against synthetic
index.json fixtures in Python. This mirrors the pattern slice-b used for
`tests/test_vlm_critic.py` — the SKILL.md / agent.md *is* the contract,
and the fixture-based gate execution lives in Tier 2 (real product-reviewer
spawn against fixture index.json).

---
category: pattern
---

**YAML-list parser from slice-b is reusable.** The `_yaml_list_under()`
helper at `tests/contract/spec_vlm_critic_isolation.py:60-85` walks lines
under a YAML key and yields the list items. slice-c does not need it
(no YAML-list assertions in slice-c's contracts), but if AC4 ever
extends to assert a structured config block in product-reviewer.md,
borrow the helper rather than re-rolling a regex.

---
category: discovery
---

**Fail-closed semantics are the dead-producer trap-door.** The Tier 0
contract test `test_index_json_visual_regression_block_is_required_not_optional`
asserts that if the `visual_regression` block is absent on a
frontend-touching change, the gate returns REJECTED with reason
`visual_regression block missing — producer (vlm-critic) did not run`.
This is the AC3+AC4 atomicity guard — PR #105 anti-pattern prevention.

The implementation in `agents/product-reviewer.md` must:
1. Read `pipeline-state/{task-id}/design-qc/index.json`.
2. If the document has any frontend-touching route AND the
   `visual_regression` block is missing → treat as `vlm_verdict == BLOCKED`,
   reason: `visual_regression block missing — producer (vlm-critic) did not run`.
3. REJECT the story-level verdict.

The reason string is asserted verbatim by Tier 0 contract test #3.
