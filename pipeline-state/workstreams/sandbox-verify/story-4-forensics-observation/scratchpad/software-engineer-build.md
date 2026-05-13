---
category: decision
---

Schema doc, helpers, mining, skip-rate, and producer wiring all landed in one slice. The `protocols/` directory is canonical for these docs (not `rules/_detail/` despite the plan's reference) — verified against project CLAUDE.md `## Detailed Protocols` section.

---
category: pattern
---

`is_present` is the canonical filter predicate exposed by `sandbox_verify_observation` for downstream consumers. Mirrors the documented "filter, don't coerce" rule applied to `phases.patch_critic` and `phases.pdr_rtv` — all three readers use the same pattern: filter via the presence helper, then process. Mining helpers (`learn_sandbox_fragility_mining`) import it directly rather than re-implementing the check, single source of truth.

---
category: discovery
---

The build.md `## Sandbox Verify` table parser uses case-insensitive column matching on the `Diff` column header. Column-order is NOT pinned (parser tolerates swap of columns 2-3); only the header text matters. This makes the consumer resilient to future template edits that re-order Worktree/Sandbox columns.

---
category: fragility
---

The `_RECURRENCE_THRESHOLD = 3` constant is the gate. Mutation testing kills the threshold-mutation (2 instead of 3) via `test_2_pipelines_no_emit` and `test_1_pipeline_no_emit`. The verdict filter (SANDBOX_FAILED only) is killed via `test_skipped_verdict_does_not_contribute`. The `is_present` enum check is killed via `test_is_present_false_when_verdict_not_in_enum` and `test_is_present_false_when_verdict_key_missing`.

---
category: warning
---

Skip-rate denominator is `total_invocations` (sum of valid + dropped), NOT `sum(reasons.values())`. The mutation that uses the latter survives the symmetric test cases — added `test_skip_rate_denominator_is_total_invocations_not_sum_reasons` as the adversarial killer. Critical because dropping the denominator distinction would silently mask JSONL corruption rates (rate would always be 1.0 when only valid skips are counted).

---
category: decision
---

`phases.sandbox_verify` schema follows the `phases.patch_critic` / `phases.pdr_rtv` precedent verbatim — top-level sibling under `phases`, not nested under `phases.build`. Documented absence-tolerance rule mirrored in autonomous-intelligence.md after the field reference table. Producer wiring left as commented-out hints in `skills/pipeline/SKILL.md` Step 7b-bis and `skills/batch-pipeline/SKILL.md` Step 6 because the writer is hand-curated by the orchestrator at Reflect time — the comments document the discovery path for the next reader.

---
category: pattern
---

Fragility instinct rendering: `confidence: 0.5`, `roles: [software-engineer, sandbox-verify-engineer]`, `domain: testing`, `category: fragility`. The dual-role injection means both the build agent AND the next sandbox-verify spawn receive the warning — the build agent learns to investigate the flaky test before commit, the sandbox-verify agent learns to expect divergence and capture detail. Confidence 0.5 matches the scratchpad → instinct promotion rule for fragility findings (existing precedent).

---
category: discovery
---

M20/M21 carryforward tests pass on the EXISTING regex/JSONL infrastructure — the canonical `_SESSION_ID_RE` already enforces no-leading-dot via `^[A-Za-z0-9_-]`, and `write_cost_event` already implements per-event JSONL append. New tests are pure carryforward coverage closing the audit register without any source change. This is an acceptable carryforward pattern when the prior story landed the implementation but the test surface was thin.
