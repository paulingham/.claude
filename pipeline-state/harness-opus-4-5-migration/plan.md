---
task_id: harness-opus-4-5-migration
schema_version: 2
dag: true
phase: plan
verdict: PLAN_DRAFTED
revision: 2
cache_hit: false
model_id_verified: true
model_id_status: GA
model_id_canonical: claude-opus-4-5-20251101
model_release_date: 2025-11-24
named_deviations:
  - id: slice-b-high-floor-named-deviation
    operator_ac: "default medium, promote to high via critical=true OR budget>=N"
    chosen: "preserve existing high floor for code-reviewer/security-engineer/architect; medium floor for all other roles"
    rationale: "Reducing high→medium on review/critic/architect roles is a quality regression with no offsetting cost win — these three roles already gate Iron Law surfaces. Deviation surfaced explicitly per challenger PR1."
    verification_token: "metrics/{session}/reflect-tokens/slice-b-high-floor-named-deviation.json"
    reflect_step_check: "operator acknowledges in Reflect or pipeline halts at Reflect gate"
escalated_acs:
  - id: slice-b-beta-header-consumer-outside-repo
    in_tree_portion_shipped: true
    in_tree_files: ["hooks/pre-agent-thinking.sh", "hooks/_lib/log-injection.sh"]
    deferred_portion: "API runtime consumer (Claude Code binary) — outside this repo"
  - id: slice-c-sdk-enablepromptcaching-consumer-outside-repo
    in_tree_portion_shipped: true
    in_tree_files: ["hooks/cache-breakpoint-injector.sh", "hooks/_lib/log-injection.sh"]
    deferred_portion: "Agent SDK consumer — outside this repo (zero SDK imports in tree per recon D3.2)"
re_scoped_acs:
  - slice-a-verdict-catalog-audit-tautological
  - slice-b-hookinjections-emission-verify-only
  - slice-c-anchor-position-mismatch
  - slice-c-ratio-threshold-staged-flip
---

# Plan: harness-opus-4-5-migration (revision 2)

## Context & Problem

Migrate the harness from `claude-opus-4-7` to `claude-opus-4-5-20251101` (GA, 2025-11-24, verified via anthropic.com/news/claude-opus-4-5). Three slices: (A) model-binding sweep + model-allowlist audit; (B) `effort` param verification + in-tree wire emission; (C) cache anchor promotion + read-ratio threshold + cache-flip-gate skill. Revision 2 responds to product-reviewer (2 HIGHs) and software-engineer (4 HIGHs) findings.

## Revision Summary (changes from r1)

- **HIGH-PR1**: Slice B AC1 — chose path (a) **named deviation with Reflect verification token**.
- **HIGH-PR2 + HIGH-E2**: Slice C AC4 — chose path (c) **ship a new `cache-flip-gate` skill in this slice**, adds verdicts `CACHE_FLIP_GATE_PASS/HOLD/INSUFFICIENT_DATA`.
- **HIGH-E1**: Cherry-pick A→B and A→C — added end-to-end test `test_cost_estimator_e2e_via_cache_jsonl_emit`.
- **HIGH-E3**: Added 4-line API contract for `hooks/_lib/model_allowlist.py`.
- **HIGH-E4**: Tightened ESCALATION wording in B.3 and C.3 to "consumer outside repo". Added in-tree wire emission as new testable ACs B.4 and C.5.
- **MED postmortem allowlist**: Encoded in `tests/_fixtures/postmortem_allowlist.yaml`.
- **MED probe-schema-flips.sh**: Added to Slice A files-to-change.
- **MED pricing citation**: Citation added (anthropic.com/pricing).
- **MED rate_version rollback**: `/cost-report` aggregator accepts both `opus-4-7-2026-04` AND `opus-4-5-2026-05` for 7-day window.
- **LOW**: Consolidated `test_thinking_defaults_doc.py` + `test_cost_discipline_doc.py` → `test_protocols_doc_references.py`.

## Decision Drivers

- Iron Law 6 — no follow-ups; disguised-deferral check applied to every "raise threshold later" pattern.
- Recon ground truth: 42 files / 108 occurrences (Slice A), 0 SDK call sites (gates Slice B/C wire-only emission).
- Preserve postmortem prose verbatim per allowlist file.
- Cherry-pick A→B→C justified by end-to-end pricing-path test.

## Chosen Approach

A→B→C cherry-pick chain on `refactor/harness-opus-4-5-migration`. Slice A renames bindings, mints `hooks/_lib/model_allowlist.py`, wires into `harness-audit`. Slice B verifies the already-shipped `hook-injections.jsonl` schema, locks in `high` floor as **named deviation**, AND adds in-tree emission of `effort` + `anthropic-beta` tokens. Slice C promotes the `persona-tail` cache anchor, raises `READ_RATIO_TARGET` to 0.65, ships `cache-flip-gate` skill that gates the 0.70 flip on observation data, AND adds in-tree emission of `enable_prompt_caching` annotation.

## Alternatives Considered

- **Single big-bang migration commit.** Rejected — 108 occurrences; one missed `rate_version` token corrupts cost records silently. A→B→C preserves bisectability.
- **Slice B: lower the floor to `medium` per literal AC.** Rejected — code-reviewer/security-engineer/architect gate Iron Law surfaces; `medium` is quality regression with no cost win. Surfaced as named deviation per PR1 path (a).
- **Slice C: defer the 0.70 flip entirely.** Rejected — "carving into ## Watch" is the Iron Law 6 violation per `feedback_disclosure_is_not_deferral` memory. Shipping a real gate skill turns the deferral into a testable artifact.
- **Slice C: ship 0.70 now, accept "below target" during soak.** Rejected — verdict polarity is `info` but operator-visible "BELOW TARGET" header creates false-alarm noise for 30 days; gate-skill path is the same effort with better signal.

## Slices

```yaml
slices:
  - id: slice-a-model-binding-migration
    depends-on: []
    description: opus-4-7 → opus-4-5-20251101 across active configs + fixtures + cost/eval; mint model_allowlist.py and wire into harness-audit. Postmortem prose preserved via allowlist YAML.
    domain: refactor
  - id: slice-b-effort-param-verify-and-wire
    depends-on: [slice-a-model-binding-migration]
    description: Verify high-floor + jsonl emission (named deviation on floor); add in-tree wire emission of effort + anthropic-beta tokens to hook-injections.jsonl; ESCALATE runtime API consumer (outside repo).
    domain: hooks
  - id: slice-c-cache-anchor-threshold-and-gate
    depends-on: [slice-a-model-binding-migration]
    description: Promote persona-tail anchor; raise READ_RATIO_TARGET to 0.65; ship cache-flip-gate skill (gates 0.70 flip on 30-day P50 ≥ 0.70); add in-tree wire emission of enable_prompt_caching token; ESCALATE SDK consumer (outside repo).
    domain: cache
```

**Cherry-pick justification (HIGH-E1)**: B and C both depend on A because A renames the `cost_estimator.py` pricing-table key from `claude-opus-4-7` to `claude-opus-4-5-20251101`. B's hook-injections lines emit cost annotations sourced from this dict; C's cache-jsonl-emit attaches dollar figures via the same dict. The new end-to-end test `test_cost_estimator_e2e_via_cache_jsonl_emit` (Slice A) exercises this dependency: it pipes a synthetic `claude-opus-4-5-20251101` through `cache-jsonl-emit.py` and asserts non-zero `total_cost_usd`. Without A's pricing-key rename, the assertion fails. The dependency is real and tested.

---

### Slice A — Model binding migration

**Operator ACs**:
1. All `opus-4-7` occurrences migrated to `opus-4-5-20251101` except postmortem allowlist.
2. Internal-eval baseline fixtures + symlinks renamed.
3. Cost pricing table + `rate_version` token bumped (with 7-day dual-accept rollback in aggregator).
4a. Verdict-catalog audit passes (existing, no-op).
4b. **NEW**: Model-allowlist check added.

**`hooks/_lib/model_allowlist.py` API contract (HIGH-E3)**:

```python
# Signature
def check(repo_root: pathlib.Path) -> list[str]:
    """Validate every agent frontmatter model:/executor:/advisor: against allowlist.

    Args:
        repo_root: harness root (e.g. ~/.claude).

    Returns:
        List of error tokens, one per offending entry. Empty list = pass.
        Token format: f"unknown-model: {path}:{line}" — matches verdict-consistency style.
    """
# Call site
# skills/harness-audit/SKILL.md Step 4 (new): invokes via
#   python3 -c "from hooks._lib import model_allowlist; print(model_allowlist.check(...))"
# Allowlist source: hooks/_lib/model_allowlist.py:_ALLOWED frozenset (hard-coded, code-reviewed).
```

**Postmortem exclusion file (MED resolution)**: `tests/_fixtures/postmortem_allowlist.yaml`:

```yaml
paths:
  - protocols/_proposals/
  - session-memory/
prose_tokens_in_file:
  CLAUDE.md:
    - "Postmortem note ("
    - "Default Opus model"
inline_paragraphs:
  CLAUDE.md:
    - L43-49
```

**Files to change** (delta vs r1):
| Category | Files |
|---|---|
| (unchanged from r1) | agent frontmatter, hooks/cost-feed.sh, best-of-n, internal-eval fixtures, doc prose, test fixtures |
| ADDED (MED) | `scripts/probe-schema-flips.sh` |
| ADDED (MED) | `tests/_fixtures/postmortem_allowlist.yaml` (new fixture) |
| ADDED (E3) | `hooks/_lib/model_allowlist.py` (new), `tests/test_model_allowlist.py` (new), `skills/harness-audit/SKILL.md` (add check) |
| ADDED (E1) | end-to-end test `tests/test_cost_estimator_e2e.py` |
| ADDED (MED rollback) | `skills/cost-report/SKILL.md` — accept both `rate_version` tokens for 7-day window post-merge |

**Failing test stubs (RED-first)**:

| AC | Test File | Test Name | Assertion Intent |
|---|---|---|---|
| A.1 | `tests/test_no_residual_opus_4_7.py` (new) | `test_zero_active_config_occurrences` | `rg 'opus-4-7'` returns 0 hits outside `tests/_fixtures/postmortem_allowlist.yaml` paths/prose. |
| A.1 | `tests/test_no_residual_opus_4_7.py` | `test_postmortem_preserved` | `CLAUDE.md:47` contains exact literal `Opus 4.7`. |
| A.1 | `tests/test_no_residual_opus_4_7.py` | `test_allowlist_fixture_well_formed` | Allowlist YAML loads; every `paths:` entry resolves; every `inline_paragraphs:` line range is non-empty. |
| A.2 | `tests/test_executor_resolution.py` (extend) | `test_fallback_returns_opus_4_5` | `executor_resolver._fallback() == "claude-opus-4-5-20251101"`. |
| A.2 | `tests/test_advisor_resolver.py` (extend) | `test_model_conditional_arms_use_4_5` | Both arms of `code-reviewer`'s `model_conditional` resolve to `claude-opus-4-5-20251101`. |
| A.3 | `tests/test_cost_estimator.py` (extend) | `test_pricing_table_keyed_on_opus_4_5` | `_PRICING["claude-opus-4-5-20251101"]` exists; matches $5 input / $25 output per-M (citation: anthropic.com/pricing 4.5 row, verified 2026-05-15). |
| A.3 | `tests/shell/test_cost_feed.bats` (extend) | `rate_version_bumped_to_opus_4_5` | Emitted JSONL includes `"rate_version":"opus-4-5-2026-05"`. |
| A.3 (E1) | `tests/test_cost_estimator_e2e.py` (new) | `test_cost_estimator_e2e_via_cache_jsonl_emit` | Synthetic spawn with `model=claude-opus-4-5-20251101` → `cache-jsonl-emit.py` → JSONL line has `total_cost_usd > 0` AND `rate_version == "opus-4-5-2026-05"`. Proves the A→B→C dependency chain. |
| A.3 (MED rollback) | `tests/test_cost_report_dual_rate_version.py` (new) | `test_aggregator_accepts_both_tokens_during_window` | Feed aggregator both `opus-4-7-2026-04` and `opus-4-5-2026-05` lines from same week → both summed; window expiry = merge_date + 7d. |
| A.4a | `tests/test_verdict_consistency.py` (existing) | (no change) | Existing passes unchanged. |
| A.4b | `tests/test_model_allowlist.py` (new) | `test_all_agent_frontmatter_in_allowlist` | Every `model:`/`executor:`/`advisor:` value across `agents/*.md` ∈ allowlist. |
| A.4b | `tests/test_model_allowlist.py` | `test_unknown_model_rejected` | Inject `model: claude-fictional-9-9`; assert `check()` returns `["unknown-model: <path>:<line>"]`. |

---

### Slice B — `effort` param verify + in-tree wire emission

**Operator ACs**:
1. Default `effort=medium`; promote to `high` via `critical=true OR budget>=N`. **NAMED DEVIATION** (HIGH-PR1, path a).
2. Emit decisions to `hook-injections.jsonl` — verify-only.
3. **Beta header `effort-2025-11-24`** — ESCALATED, scope tightened to "consumer outside repo" (HIGH-E4).
4. **NEW (HIGH-E4)**: In-tree wire emission — `hooks/pre-agent-thinking.sh` writes `effort` + `anthropic-beta: effort-2025-11-24` tokens into `metrics/{session}/hook-injections.jsonl` under `resolved.beta_header` and `resolved.api_effort` fields. ~15 LOC.

**HIGH-PR1 Named Deviation — full rationale**:

> **Operator AC**: "default medium, promote to high via critical=true OR budget>=N"
> **Reality**: `hooks/_lib/thinking_role.py:29-32` pins `code-reviewer` and `security-engineer` to `high` floor; `architect` falls through to default `high` at `thinking_resolver.py:42`. xhigh promotion gates fire at `thinking_role.py:42-50`.
> **Chosen**: Keep `high` floor for review/critic/architect; medium floor applies to remaining roles. xhigh promotion preserved verbatim.
> **Why not lower to medium**: All three high-floor roles gate Iron Law surfaces. Reducing reasoning budget is a quality regression. Cost differential is small because these roles are review-only (single spawn per phase, not parallel build).
> **Verification token**: `metrics/{session}/reflect-tokens/slice-b-high-floor-named-deviation.json` written at Reflect step 6e. Pipeline halts at Reflect gate if operator does not acknowledge.

**Files to change**:
| Purpose | Files |
|---|---|
| B.1 verification | `tests/test_thinking_defaults.py`, `tests/test_thinking_resolver.py` (lockstep extensions) |
| B.2 verification | `tests/test_hook_injection_schema.py` (new) |
| B.3 ESCALATION doc | `protocols/thinking-defaults.md` (append "Beta header — consumer outside repo, in-tree wire emission shipped 2026-05-15") |
| B.4 in-tree wire | `hooks/pre-agent-thinking.sh` (~15 LOC), `hooks/_lib/log-injection.sh` (add 2 fields to JSON) |
| B.1 named deviation | `protocols/thinking-defaults.md` (append "Named deviation: high floor preserved on review/critic/architect"), Reflect-token writer in `hooks/reflect-token-emit.sh` (new helper) |

**Failing test stubs**:

| AC | Test File | Test Name | Assertion Intent |
|---|---|---|---|
| B.1 | `tests/test_thinking_defaults.py` (extend) | `test_high_floor_for_code_reviewer_security_architect` | `_DOWNGRADE_TO_HIGH` ⊇ `{"code-reviewer","security-engineer"}`; architect resolves to `high` at `critical=False, budget=0`. |
| B.1 | `tests/test_thinking_defaults.py` | `test_xhigh_promotion_preserved` | architect@budget=6 → xhigh; software-engineer@budget=7 → xhigh. |
| B.1 (deviation) | `tests/test_named_deviation_token.py` (new) | `test_reflect_token_emitted_for_high_floor_deviation` | Reflect step writes `slice-b-high-floor-named-deviation.json` with `acknowledged: false`; pipeline halts if not flipped to `true`. |
| B.2 | `tests/test_hook_injection_schema.py` (new) | `test_hook_injections_jsonl_emits_effort_field` | JSONL line parses; `resolved.effort ∈ {low,high,xhigh}`; `resolved.source != ""`. |
| B.3 (escalated) | `tests/test_protocols_doc_references.py` (new, LOW consolidation) | `test_beta_header_consumer_outside_repo_documented` | `protocols/thinking-defaults.md` contains literal `Beta header — consumer outside repo` AND `in-tree wire emission shipped`. |
| B.4 (E4 wire) | `tests/test_hook_injection_schema.py` | `test_jsonl_emits_beta_header_token` | After synthetic spawn, JSONL line contains `resolved.beta_header == "effort-2025-11-24"` AND `resolved.api_effort ∈ {low,medium,high,xhigh}`. |
| B.4 | `tests/test_hook_injection_schema.py` | `test_beta_header_omitted_when_role_disables_effort` | For `planning-agent` (effort=low, no beta needed), `resolved.beta_header` is absent. |

---

### Slice C — Cache anchor + threshold + flip-gate skill + wire emission

**Operator ACs**:
1. Promote deferred `persona-tail` anchor.
2. Verify min cacheable ≥4096 tokens; enumerate small-agent skip list.
3. **Enable Agent SDK `enablePromptCaching: true`** — ESCALATED, "consumer outside repo" (HIGH-E4).
4. **Cache-read ratio ≥0.70** — **PATH (c) per HIGH-PR2 + HIGH-E2: ship `cache-flip-gate` skill in this slice**. Raise constant to 0.65; the flip to 0.70 is gated by a real skill that evaluates 30-day `metrics/{session}/cache.jsonl` records.
5. **NEW (HIGH-E4)**: In-tree wire emission — `hooks/cache-breakpoint-injector.sh` writes `enable_prompt_caching: true` annotation into `hook-injections.jsonl`.

**`cache-flip-gate` skill contract**:

- **Location**: `skills/cache-flip-gate/SKILL.md` (new).
- **Inputs**: `metrics/{session}/cache.jsonl` across last 30 days (glob).
- **Computation**: P50 of `read_ratio` across all spawns in window.
- **Verdicts** (added to `rules/verdict-catalog.md`):
  - `CACHE_FLIP_GATE_PASS` (success): `P50 >= 0.70` AND `n_observations >= 100`.
  - `CACHE_FLIP_GATE_HOLD` (info): below threshold.
  - `CACHE_FLIP_GATE_INSUFFICIENT_DATA` (info): `n_observations < 30`.
- **Polarity**: `info` or `success` only — never gates a pipeline phase. Operator-invoked manually.

**Files to change**:
| Purpose | Files |
|---|---|
| C.1 anchor | `hooks/_lib/resolve-cache-breakpoints.py` (promote `persona-tail` from deferred to active) |
| C.2 skip list | `skills/cache-audit/SKILL.md` (add "Small-agent skip list") |
| C.3 ESCALATION doc | `protocols/cost-discipline.md` (append "SDK flag — consumer outside repo, in-tree wire emission shipped 2026-05-15") |
| C.4 threshold + gate | `skills/cache-audit/SKILL.md:32-40` (`READ_RATIO_TARGET = 0.65`), `skills/cache-flip-gate/SKILL.md` (new), `hooks/_lib/cache_flip_gate.py` (new), `tests/test_cache_audit_read_ratio_target_constant.py` (lockstep), `rules/verdict-catalog.md` (3 new verdicts) |
| C.5 wire emission | `hooks/cache-breakpoint-injector.sh` (add `cache_flag: true` to log line) |

**Failing test stubs**:

| AC | Test File | Test Name | Assertion Intent |
|---|---|---|---|
| C.1 | `tests/test_cache_breakpoints.py` (new) | `test_persona_tail_anchor_active` | `resolve_cache_breakpoints()` returns ≥1 anchor with id `persona-tail`. |
| C.2 | `tests/test_cache_audit_small_agent_skip.py` (new) | `test_small_agent_skip_list_documented` | Skill contains "Small-agent skip list" enumerating `planning-agent`, `sandbox-verify-engineer`, `vlm-critic`. |
| C.3 (escalated) | `tests/test_protocols_doc_references.py` | `test_sdk_flag_consumer_outside_repo_documented` | `protocols/cost-discipline.md` contains literal `SDK flag — consumer outside repo` AND `in-tree wire emission shipped`. |
| C.4 | `tests/test_cache_audit_read_ratio_target_constant.py` (extend) | `test_target_raised_to_0_65` | Constant parsed from skill = 0.65. |
| C.4 (gate) | `tests/test_cache_flip_gate.py` (new) | `test_gate_emits_pass_when_p50_above_threshold` | Synthetic 30-day window P50=0.72, n=150 → `CACHE_FLIP_GATE_PASS`. |
| C.4 | `tests/test_cache_flip_gate.py` | `test_gate_emits_hold_when_below_threshold` | P50=0.62 → `CACHE_FLIP_GATE_HOLD`. |
| C.4 | `tests/test_cache_flip_gate.py` | `test_gate_emits_insufficient_when_n_below_30` | n=20 → `CACHE_FLIP_GATE_INSUFFICIENT_DATA`. |
| C.4 | `tests/test_verdict_catalog_new_entries.py` | `test_cache_flip_gate_verdicts_in_catalog` | `rules/verdict-catalog.md` declares all three `CACHE_FLIP_GATE_*` verdicts. |
| C.5 (wire) | `tests/test_hook_injection_schema.py` (extend) | `test_jsonl_emits_cache_flag_token` | JSONL line contains `resolved.cache_flag == true` when cache breakpoint resolved. |

## Pre-Mortem (3 named failure modes)

| Failure Mode | Likelihood | Detection | Mitigation |
|---|---|---|---|
| `cost_estimator.py` pricing key missed on cache-aggregator path → `costs.jsonl` rows show $0 for Opus. | low | `/cost-report` shows Opus row at $0. | **Resolved by E1**: new `test_cost_estimator_e2e_via_cache_jsonl_emit` pipes synthetic spawn through full chain and asserts `total_cost_usd > 0`. |
| `CLAUDE.md:47` postmortem prose rewritten by over-broad sed → falsifies historical record. | high | `test_postmortem_preserved` asserts literal `Opus 4.7`. | RED-first stub + `postmortem_allowlist.yaml` fixture (deterministic). |
| `READ_RATIO_TARGET` raised to 0.65 but harness operates at 0.55 → alarm fatigue. | med | Weekly cache-audit shows `read_ratio < 0.65` for ≥4 weeks. | `cache-flip-gate` skill consumes 30-day data; revert constant to 0.60 in 5-LOC follow-up if needed. |

## Risk Register (operator-noted, addressed)

| Operator Risk | Address |
|---|---|
| Model direction (4.5 < 4.7) | GA verified; named deviation surfaces re-acknowledgment at Reflect. |
| Adaptive-thinking loss | `_is_xhigh()` per-role gates preserved verbatim per Slice B AC1. |
| Cache regression on 4.5 | Threshold staged: 0.65 today; 0.70 gated by `cache-flip-gate` skill on 30-day P50 ≥ 0.70 + n ≥ 100. |
| Small-agent < 4096 tokens | Slice C AC2 enumerates skip list; no forced consolidation. |

## Verdict

`PLAN_DRAFTED` (round 2 ready for re-review). All 6 HIGH findings + 4 MED + 1 LOW addressed inline.
