# Verdict Catalog

Single source of truth for every verdict any skill in `~/.claude/skills/` is allowed to emit. The `/harness:harness-audit` `verdict-consistency` step asserts this catalog and the actual skill frontmatter agree in both directions:

- Forward: every verdict declared in a skill MUST appear here.
- Reverse: every catalog entry MUST be emitted by at least one skill.

Polarity legend:

- `success` — work completed, gate passed
- `failure` — gate failed, halt or retry
- `info` — informational outcome (no gate; pipeline continues)

When adding a new skill or extending an existing skill's verdict set, update this file in the same PR. The audit step will surface drift on the next run.

## Catalog

| Verdict | Polarity | Emitter skill | Phase | Downstream branch |
|---------|----------|---------------|-------|-------------------|
| `ROUTED` | info | `intake` | intake | `/harness:pipeline`, `/harness:tech-spike`, `/harness:epic-breakdown`, or direct answer — payload includes `gear: PAIR|BUILD|PIPELINE` (set by `hooks/_lib/gear-select.sh`, read by `/harness:intake` Step 1.5) |
| `STORIES_READY` | info | `epic-breakdown` | plan | One `/harness:pipeline` per story |
| `ESTIMATED` | info | `estimation` | plan | Pipeline continues with budget |
| `STORY_READY` | info | `story-writing` | plan | `/harness:build-implementation` |
| `RECON_COMPLETE` | info | `architect-context-recon` (agent) | plan | Architect reads concatenated `architect-context.md` before drafting |
| `RECON_NULL` | info | `architect-context-recon` (agent) | plan | Architect proceeds with greenfield assumption; output file still written (anti-findings only) |
| `PLAN_CACHE_MISS` | info | `plan-cache-lookup` | plan | Continue to Stage 1 recon dispatch — reason ∈ {`no-template`, `disabled`, `shadow-mode`} in Slice B; Slice C adds `adapter-rejected`, `adapter-pending-stale`, `template-corrupt`; Slice F adds `hash-drift`, `key-mismatch` |
| `PLAN_CACHE_HIT` | info | `plan-cache-lookup` | plan | HIT path: Haiku adapter rewrote cached template; structural validator passed; skip Stage 1 (recon) and Stage 2 (architect) — Architect plan ready at `$state_dir/{task-id}/plan.md` with `cache_hit: true` marker (Plan Validation challengers skip citation-alignment per `parallel-dispatch-details.md:134`) |
| `GROUNDED` | success | `spec-grounding` | plan | All ACs grounded against codebase evidence; `$state_dir/{task-id}/spec-grounding.md` written with inline citations; architect reads it at Pre-Drafting Recon |
| `GROUNDING_GAPS` | info | `spec-grounding` | plan | One or more ACs have no codebase match or recall hit; gap ACs listed in `spec-grounding.md` § Gaps with `[grounded: gap]` markers; architect must supply evidence for gap ACs; pipeline continues (non-blocking) |
| `SPEC_CONTRADICTIONS_FOUND` | info | `spec-grounding` | plan | One or more AC pairs are structurally opposed (antonym or negation asymmetry on a shared subject); pairs listed in `spec-grounding.md` § Contradictions with indices + reason; architect reviews at Pre-Drafting Recon; **non-blocking** — Plan proceeds |
| `SPEC_CONTRADICTIONS_NONE` | info | `spec-grounding` | plan | No structurally-opposed AC pairs detected; advisory check clean; **non-blocking** |
| `SPIKE_COMPLETE` | info | `tech-spike` | utility | Findings feed back into planning |
| `PLAN_APPROVED` | success | `plan-self-validation` | plan-validation | `/harness:build-implementation` |
| `PLAN_HOLES` | failure | `plan-self-validation` | plan-validation | Architect re-plans (max 1 revision, then escalate to heavy challengers) |
| `ROUTING_UPSHIFTED` | info | `plan-self-validation` | plan-validation | Plan-phase re-fingerprint detected gear upshift {gear_initial}→PIPELINE; pipeline re-dispatches downstream phases at new gear (per `protocols/work-class-routing.md` § Plan-phase re-gear sanity check) |
| `PLAN_FEASIBILITY_REJECTED` | failure | `plan-self-validation` | plan-validation | LIGHT-gate self-judgment: architect-context.md Feasibility Finding says FEASIBILITY_REJECTED and the self-validation rubric concurs. Premise/feasibility veto distinct from CHANGES_REQUESTED: surfaces to user, writes feasibility_drift forensic field, does NOT trigger silent architect re-work. No overturn-to-feasible in light gate. |
| `PLAN_FEASIBILITY_REJECTED` | failure | `product-reviewer` (agent), `software-engineer` (agent) | plan-validation | HEAVY-gate agent-emitted: either challenger emits it when the request's PREMISE is false, regardless of the architect's call. Overturnable BOTH directions (Step 2d). Surfaces to user, writes feasibility_drift. Agent-emitted — reverse-audit exempt (see Notes). |
| `BUILD_COMPLETE` | success | `build-implementation` | build | `/harness:code-review` + `/harness:security-review` |
| `BUILD_FAILED` | failure | `build-implementation` | build | Halt; user escalation or re-dispatch |
| `PAIR_COMPLETE` | info | `pair` | build | None — conversation continues; user may say "build it" or "ship it properly" to escalate the same request to `BUILD`/`PIPELINE` |
| `REFACTOR_COMPLETE` | success | `refactor` | build | `/harness:code-review` + `/harness:security-review` |
| `REFACTOR_FAILED` | failure | `refactor` | build | Halt; user escalation |
| `BUG_FIXED` | success | `bug-fix` | build | `/harness:code-review` + `/harness:security-review` — payload MUST include `reproducer_artifact:` as a mapping with required keys `{path, red_evidence, green_evidence}` per AssertFlip Step 0 (arXiv 2507.17542). `red_evidence` captures the failing assertion (pre-fix RED state); `green_evidence` captures the passing assertion (post-fix). Verdict without all three keys is rejected by `hooks/bug-fixed-payload-validator.sh`. Single-string `<path>` form retained ONLY during DUAL_PATH soak (log-only 30d → warn 60d → strict — soak-end TBD). |
| `BUG_UNRESOLVED` | failure | `bug-fix` | build | Halt; user escalation with hypothesis log |
| `TOOL_SYNTHESISED` | info | `tool-synthesis` | build | Build agent uses the scratch tool, deletes after use |
| `TOOL_SYNTHESISED_PROMOTABLE` | info | `tool-synthesis` | build | Same as TOOL_SYNTHESISED + flagged as reusable across pipelines; `/harness:learn` counts cross-pipeline recurrences and scaffolds a permanent skill on the third hit (human review gate) |
| `TOOL_UNNECESSARY` | info | `tool-synthesis` | build | Build agent proceeds with standard tools |
| `PBT_AUTHORED` | success | `property-based-test` | build | Build proceeds; ≥1 property authored at Step 1d, ≥0 counterexamples frozen, ≥0 functions justified-impossible |
| `PBT_SKIPPED` | info | `property-based-test` | build | Build proceeds; reason ∈ {`env-hatch` (CLAUDE_PBT=0 set), `no-candidates` (no public-typed-changed-line functions), `no-framework-for-language` (language has no shipped PBT harness or harness not installed)} |
| `PBT_BLOCKED` | failure | `property-based-test` | build | Build halts; reason ∈ {`harness-crash`, `unrecoverable-error`}; recovery = set CLAUDE_PBT=0 and re-run; does NOT count against retry-twice-then-escalate budget per `protocols/operational-protocol.md` |
| `DOM_SMOKE_PASSED` | success | `build-implementation` | build | All routes loaded with no console errors and no 4xx/5xx XHR; Build proceeds to Step 3 |
| `DOM_SMOKE_SKIPPED` | info | `build-implementation` | build | Step skipped; reason ∈ {`env-hatch`, `no-changed-routes`, `no-route-resolver`, `mcp-unavailable-first-run`}; Build proceeds |
| `DOM_SMOKE_FAILED` | failure | `build-implementation` | build | Console error or 4xx/5xx XHR detected after ignore-filter, OR `mcp-unavailable-after-warm`, OR `ignore-list-overbroad`, OR `dev-server-non-loopback`; payload `{route, errors: [{type, message, url, status}]}`; HALT Build, spawn fix-engineer in-cycle |
| `PLAN_REFINED` | info | `continuous-planning` | build | Build agents re-read plan; never gates Build completion |
| `PLAN_UNCHANGED` | info | `continuous-planning` | build | No effect; Build proceeds |
| `BoN_WINNER_SELECTED` | success | `best-of-n` | build | `/harness:code-review` + `/harness:security-review` |
| `BoN_FALLBACK_TO_SINGLE` | info | `best-of-n` | build | Single-candidate Build dispatch on the same slice |
| `BoN_INSUFFICIENT_RESOURCES` | failure | `best-of-n` | build | Halt; user escalation |
| `PDR_WINNER_SELECTED` | success | `pdr-rtv` | build | `/harness:code-review` + `/harness:security-review` |
| `PDR_NO_CONSENSUS` | failure | `pdr-rtv` | build | Silent fallback to Best-of-N → standard Build; logged in `## Re-routes` with `fallback_reason` enum (`worktree-cap-exceeded` / `insufficient-green-builds` / `all-finalists-rejected`) |
| `SANDBOX_VERIFIED` | success | `sandbox-verify` | build | Worktree pass set equals sandbox pass set; Build advances |
| `SANDBOX_FAILED` | failure | `sandbox-verify` | build | Pass sets diverge OR cost-cap hard-trip; spawn fix-engineer with `diverging_tests` enumerated (or `reason: "cost-exceeded"` set) per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule |
| `SANDBOX_SKIPPED` | info | `sandbox-verify` | build | Sandbox unavailable OR not applicable; reason ∈ {`no-e2b-token`, `no-testable-changes`, `env-hatch`, `e2b-unavailable`}; one JSONL line appended to `metrics/{session-id}/sandbox-verify-skips.jsonl`; Build advances |
| `APPROVE` | success | `code-review` | build (final step) | Build emits BUILD_COMPLETE; advance to Security Review |
| `APPROVE` | success | `security-review` | security-review | Final Gate (verify + test + accept + patch-critique) |
| `CHANGES_REQUESTED` | failure | `code-review` | build (final step) | Spawn fix-engineer in-line; re-dispatch code-reviewer; max 2 rounds inside Build |
| `CHANGES_REQUESTED` | failure | `security-review` | security-review | Spawn fix-engineer; security-engineer re-reviews; max 2 rounds |
| `ORCHESTRATOR_APPLY_REQUIRED` | failure | `fix-engineer` | review | Fix-engineer hit the harness Edit-denial path (≥2 denials, no PreToolUse hook fired) and returned a structured `{file_path, old_string, new_string}` payload. Orchestrator applies each pair via its `.md`-allowed Edit pathway, then re-dispatches the raising reviewer (counts as 1 round). Fix-engineer is NOT spawned again on the same finding after this verdict |
| `VERIFIED` | success | `verify` | final-gate | Pipeline advances to Test phase |
| `VERIFIED_WITH_SKIP` | info | `verify` | final-gate | Tier skipped with documented reason; advances |
| `E2E_SKIP_NO_ENV` | info | `verify` | final-gate | Side-channel verdict emitted alongside the composite when Tier 4 web target = `SKIP` (driver config present but real-environment stack unavailable, per `protocols/e2e-protocol.md` § Pass/Fail Criteria). Pipeline advances; Final Gate summary renders the loud yellow line `E2E: SKIPPED (no execution environment) — UI/API changes shipped without browser verification`; product-reviewer MUST acknowledge the skip in its verdict body — failure to acknowledge → CHANGES REQUESTED |
| `UNVERIFIED` | failure | `verify` | final-gate | Halt; back to Build to address tier failures |
| `COVERED` | success | `qa-test-strategy` | final-gate | Pipeline advances to Accept phase |
| `GAPS_FOUND` | failure | `qa-test-strategy` | final-gate | Spawn fix-engineer to fill test gaps |
| `APPROVED` | success | `product-acceptance` | final-gate | Writes approval token; `/harness:pr-creation` unblocked |
| `APPROVED_WITH_CONDITIONS` | success | `product-acceptance` | final-gate | Approval token written; conditions resolved in-cycle |
| `REJECTED` | failure | `product-acceptance` | final-gate | Halt; back to Build with AC violations |
| `PATCH_APPROVED` | success | `patch-critique` | final-gate | `/harness:pr-creation` unblocked |
| `PATCH_REJECTED` | failure | `patch-critique` | final-gate | Spawn fix-engineer (in-cycle, no user escalation) |
| `SPEC_BLIND_VALIDATED` | success | `spec-blind-validate` | final-gate | Pipeline advances to next gate |
| `SPEC_BLIND_FAILED` | failure | `spec-blind-validate` | final-gate | Spawn fix-engineer per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule (code-fix-only — fix-engineer MUST NOT mutate ACs) |
| `SPEC_BLIND_INSUFFICIENT_SURFACE` | info | `spec-blind-validate` | final-gate | Pipeline advances to next gate; Final Gate summary renders `spec-blind: SKIPPED (no public surface)` (verbatim) |
| `SPEC_BLIND_BLOCKED` | failure | `spec-blind-validate` | final-gate | HALT pipeline + emit operator-visible escalation message; do NOT auto-advance and do NOT route to fix-engineer |
| `VISUAL_DIFF_PASS` | success | `vlm-critic` | final-gate | Pipeline advances to next gate; product-reviewer reads `index.json.visual_regression` and gates APPROVE on `pixel_diff_ratio < threshold AND vlm_verdict == PASS` for every route |
| `VISUAL_DIFF_FAIL` | failure | `vlm-critic` | final-gate | Spawn fix-engineer per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule (code-fix-only — fix-engineer MUST NOT mutate ACs); fix-engineer rebuilds frontend, design-qc re-runs (baseline capture → pixel diff → vlm-critic), product-reviewer re-checks |
| `POLISHED` | info | `polish` | utility | Continue to Review |
| `NO_CHANGES_NEEDED` | info | `polish` | utility | Continue to Review |
| `SCREENSHOTS_CAPTURED` | info | `design-qc` | utility | Product-reviewer consumes screenshots |
| `CAPTURE_FAILED` | failure | `design-qc` | utility | Product-reviewer warned; falls back to text review |
| `SKILL_LINT_CLEAN` | info | `skill-security-lint` | utility | No injection patterns, secrets, or over-broad tool grants found in scanned skill files; advisory — security-engineer folds result into assessment |
| `SKILL_LINT_FLAGGED` | info | `skill-security-lint` | utility | One or more findings detected (injection / secret / over_broad_tool); advisory — security-engineer folds findings into OWASP AA02/AA03 items; never a hard block |
| `SMELLS_FOUND` | info | `smell-scan` | utility | ≥1 ranked smell candidate detected (Feature Envy, Data Clumps, etc.); advisory — code-reviewer folds findings into review output as an advisory section; never a hard block |
| `SMELLS_CLEAN` | info | `smell-scan` | utility | No smell candidates detected, or 0 source files in scope after filtering; advisory; non-blocking |
| `DEBT_LEDGER_WRITTEN` | info | `debt-ledger` | utility | ≥1 `DEBT:` marker found; ledger rendered grouped by file with ceiling/upgrade-trigger per entry and the `no-trigger` (silent-rot) count; advisory — reader decides whether to pay down debt; never a hard block |
| `DEBT_LEDGER_CLEAN` | info | `debt-ledger` | utility | Zero `DEBT:` markers in scope after exclusions ("No DEBT markers found"); advisory; non-blocking |
| `PR_CREATED` | success | `pr-creation` | ship | `/harness:deploy` (if CD configured) |
| `PR_BLOCKED` | failure | `pr-creation` | ship | Halt; missing approval token or quality-gate failure |
| `CI_GREEN` | success | `pr-creation` | ship | All `gh pr checks` runs concluded SUCCESS against the pushed head (headRefOid verified); CI-green gate passed — proceed to cost annotator (Step 6) then Deploy. |
| `CI_RED` | failure | `pr-creation` | ship | ≥1 `gh pr checks` run concluded FAILURE or CI status unreadable; HALTS Ship→Deploy at the CI-green gate — pull `--log-failed`, re-enter in-cycle fix loop (fix-engineer SAME build worktree → commit → push), verify `git ls-remote` == claimed SHA, re-arm watch. |
| `CHANGELOG_WRITTEN` | success | `changelog` | ship | PR narrative returned for `pr-creation` `## Summary`; `CHANGELOG.md` updated under `Unreleased` |
| `CHANGELOG_SKIPPED` | info | `changelog` | ship | No functional change in diff (docs/test-only); narrative returned, no changelog edit; non-blocking |
| `DEPLOYED` | success | `deploy` | deploy | `/harness:deployment-verification` |
| `DEPLOY_FAILED` | failure | `deploy` | deploy | Auto-rollback path |
| `ROLLED_BACK` | failure | `deploy` | deploy | Halt; user notified |
| `DEPLOYMENT_VERIFIED` | success | `deployment-verification` | deploy | Reflect |
| `DEPLOYMENT_VERIFIED_WITH_WARNINGS` | info | `deployment-verification` | deploy | Reflect; warnings captured in observation |
| `AUTO_ROLLBACK` | failure | `deployment-verification` | deploy | Triggered automatic rollback; user notified |
| `PIPELINE_COMPLETE` | success | `pipeline` | reflect | End of pipeline |
| `PIPELINE_IN_PROGRESS` | info | `pipeline` | utility | Pipeline state mid-flight; resumable |
| `RESUMED` | info | `pipeline-resume` | utility | Pipeline resumes from current phase |
| `NO_ACTIVE_PIPELINE` | info | `pipeline-resume` | utility | No-op; new pipeline must be started |
| `STATE_INVALID` | failure | `pipeline-resume` | utility | Halt; manual cleanup required |
| `BATCH_COMPLETE` | success | `batch-pipeline` | utility | End of batch |
| `LEARNED` | info | `learn` | reflect | Instincts written to `learning/` |
| `NO_NEW_PATTERNS` | info | `learn` | reflect | Nothing to extract; skip |
| `NO_OBSERVATIONS` | info | `learn` | reflect | No observations available; skip |
| `RECOMMENDATIONS_READY` | info | `eval-model-effectiveness` | utility | Advisory report written; human reviews |
| `INSUFFICIENT_DATA` | info | `eval-model-effectiveness` | utility | Skip; need more observations |
| `INSUFFICIENT_DATA` | info | `plan-cache-rollout-gate` | utility | Fewer than 30 pipelines AND <14 days of `plan-cache.jsonl` records; gate refuses to grade. Re-run after more data arrives. |
| `ROLLOUT_GATE_PASS` | success | `plan-cache-rollout-gate` | utility | All three thresholds met (`hit_rate >= 0.10` AND `pv_pass_rate_on_hit >= 0.95` AND `cost_delta > 0`); operator may author a flip-to-`on` PR citing the PASS payload as evidence (HIGH-prod-1). |
| `ROLLOUT_GATE_FAIL` | failure | `plan-cache-rollout-gate` | utility | One or more thresholds not met; payload `failed_thresholds[]` cites which. Flip-to-`on` PR must NOT merge until a re-run returns PASS. |
| `NO_CHANGE` | info | `eval-model-effectiveness` | utility | Recommendations unchanged from prior run |
| `COST_REPORT_READY` | info | `cost-report` | utility | Advisory report written to `metrics/reports/{date}-cost.md`; human reviews |
| `CACHE_AUDIT_READY` | info | `cache-audit` | utility | Advisory report written to `metrics/reports/{date}-cache.md`; human reviews |
| `MUTATION_SCORE_REPORT_READY` | info | `mutation-score-report` | utility | Advisory mutation-score convergence report written; human reviews soak progress vs the >=10-session / >=70% promotion criterion |
| `CACHE_FLIP_GATE_PASS` | success | `cache-flip-gate` | utility | 30-day P50 read_ratio >= 0.70 AND n_observations >= 100; operator may raise `READ_RATIO_TARGET` from 0.65 to 0.70 in `skills/cache-audit/SKILL.md` (manual constant edit, requires PASS observed twice ≥7 days apart per Slice C safeguard) |
| `CACHE_FLIP_GATE_HOLD` | info | `cache-flip-gate` | utility | 30-day P50 read_ratio < 0.70 (with n_observations >= 30); flip from 0.65 to 0.70 NOT recommended; operator re-runs in ≥7 days |
| `CACHE_FLIP_GATE_INSUFFICIENT_DATA` | info | `cache-flip-gate` | utility | Fewer than 30 cache.jsonl observations in window; gate refuses to grade; re-run after more data arrives |
| `EVAL_PASSED` | success | `internal-eval` | utility | Harness PR can merge |
| `EVAL_FAILED` | failure | `internal-eval` | utility | Harness PR blocked; regressions on deterministic cases |
| `EVAL_BASELINE_CAPTURED` | info | `internal-eval` | utility | Baseline written; subsequent runs diff against it |
| `INSUFFICIENT_CASES` | info | `internal-eval` | utility | Not enough cases to score; rerun later |
| `EVAL_IMPROVEMENT_CONFIRMED` | info | `internal-eval` | utility | `ab` mode: arm B reduced diff-economy (LOC/USD) with safety floor held; advisory, never gates |
| `EVAL_REGRESSION_DETECTED` | info | `internal-eval` | utility | `ab` mode: arm B safety dropped; Iron Law 1 guard-return; advisory, non-gating by design |
| `EVAL_NEUTRAL` | info | `internal-eval` | utility | `ab` mode: safety held but no significant diff-economy change beyond noise thresholds |
| `CLEAN` | info | `forensics` | utility | No anomalies found in pipeline trajectory |
| `ANOMALIES_FOUND` | info | `forensics` | utility | Anomalies surfaced; report written for human review |
| `INVESTIGATION_INCOMPLETE` | info | `forensics` | utility | More data needed; user instructed |
| `DEBUG_ACTIVE` | info | `debug` | utility | Persistent debug state created/updated |
| `DEBUG_RESOLVED` | success | `debug` | utility | Bug resolved; pipeline resumes from Review — payload MUST include `reproducer_artifact: <path \| env-only>` (AssertFlip Step 0 test; `env-only` permitted when bug reproduces only in non-test environment with documented justification) |
| `DEBUG_ESCALATED` | failure | `debug` | utility | Iteration cap hit; user escalation |
| `TRACE_TOGGLED` | info | `debug-trace` | utility | Per-session prompt tracing on/off |
| `HEALTHY` | info | `harness-audit`, `health-scan` | utility | No issues |
| `TOOLS_VALID` | info | `harness-audit` | utility | All agent tools resolve to known catalog or MCP servers |
| `WARNINGS` | info | `harness-audit` | utility | Non-blocking issues found |
| `CRITICAL` | failure | `harness-audit` | utility | Blocking issues; harness needs repair |
| `NEEDS_ATTENTION` | failure | `health-scan` | utility | Issues found; user reviews |
| `CRITICAL_ISSUES` | failure | `health-scan` | utility | Severe issues (security/CVE/coverage); urgent action required |
| `CONFIG_APPLIED` | info | `harness-config` | utility | Hooks/settings updated |
| `PROJECT_SETUP_COMPLETE` | info | `project-setup` | utility | Project CLAUDE.md scaffolded |
| `GREENFIELD_SCAFFOLD_COMPLETE` | info | `greenfield-scaffold` | utility | New project bootstrapped end-to-end |
| `CREATIVE_DIRECTION_COMPLETE` | info | `creative-direction` | utility | Design brief written |
| `CREATIVE_DIRECTION_SKIPPED` | info | `creative-direction` | utility | Existing brief honoured; no change |
| `DESIGN_SYSTEM_READY` | info | `design-system-init` | utility | Tokens + primitives generated |
| `PATTERNS_APPLIED` | info | `web-frontend-patterns` | utility | Pattern reference consumed |
| `API_SCAFFOLDED` | info | `api-scaffold` | utility | API boilerplate generated |
| `MIGRATION_COMPLETE` | success | `db-migration` | utility | Schema change applied |
| `MIGRATION_BLOCKED` | failure | `db-migration` | utility | Halt; reversibility or zero-downtime concern |
| `INFRA_SCAFFOLDED` | info | `infra-scaffold` | utility | Dockerfile + CI/CD generated |
| `OBSERVABILITY_CONFIGURED` | info | `observability-setup` | utility | Logging/metrics/tracing wired |
| `PERFORMANCE_VERIFIED` | success | `load-test` | utility | SLA met |
| `PERFORMANCE_WARNING` | info | `load-test` | utility | SLA met with margin concerns |
| `PERFORMANCE_FAILED` | failure | `load-test` | utility | SLA breached |
| `VOICE_SCAFFOLDED` | info | `voice-scaffold` | utility | Voice skill scaffold generated |
| `BFF_SCAFFOLDED` | info | `bff-scaffold` | utility | BFF layer scaffold generated |
| `SERVICE_SCAFFOLDED` | success | `microservices-scaffold` | utility | New service scaffolded (FF gate passed) |
| `WRONG_SKILL` | failure | `microservices-scaffold`, `module-extraction` | utility | Routed to correct skill (forcing-function check) |
| `MODULE_EXTRACTED` | success | `module-extraction` | utility | All six phases green |
| `BOUNDARY_READY` | info | `module-extraction` | utility | Phases 1-2 complete (MVP); Build pipeline drives 3-6 via TDD |
| `EXTRACTION_BLOCKED` | failure | `module-extraction`, `service-extraction` | utility | Boundary or contract concern; not yet extractable |
| `SERVICE_EXTRACTED` | success | `service-extraction` | utility | Module promoted to service |
| `CROSS_SERVICE_VERIFIED` | success | `cross-service-pipeline` | utility | Multi-repo contract + deploy verified |
| `CROSS_SERVICE_BLOCKED` | failure | `cross-service-pipeline` | utility | Halt; contract or coordination issue |
| `WORKSTREAM_CREATED` | info | `workstream` | utility | New workstream isolated under `$state_dir/workstreams/` |
| `WORKSTREAM_LISTED` | info | `workstream` | utility | Active workstreams reported |
| `WORKSTREAM_ARCHIVED` | info | `workstream` | utility | Workstream removed |
| `REINDEXED` | info | `reindex-memory` | utility | FTS5 index rebuilt |
| `NOOP` | info | `reindex-memory` | utility | Nothing to do |
| `FAILED` | failure | `reindex-memory` | utility | Fatal error during reindex |
| `A11Y_CHECK_PASSED` | success | `accessibility-check` | utility | Pipeline continues |
| `A11Y_CHECK_FAILED` | failure | `accessibility-check` | utility | Halt; list gating violations with id, help, nodes, route_url |
| `A11Y_CHECK_SKIPPED` | info | `accessibility-check` | utility | Pipeline continues; reason ∈ {no-dev-server-contract, browser-launch-failed, env-hatch} |

## Notes

- `ROUTED` carries a `gear: PAIR|BUILD|PIPELINE` field in its payload, classified by `hooks/_lib/gear-select.sh` and read by the `/harness:intake` Step 1.5 gear read (per `protocols/work-class-routing.md`). The field gates downstream dispatch: PAIR exits before `/harness:pipeline` is ever invoked; BUILD and PIPELINE proceed into `/harness:pipeline` at lightweight/standard or heavy dispatch respectively.
- `WRONG_SKILL` and `EXTRACTION_BLOCKED` appear in two emitters each (microservices-scaffold + module-extraction; module-extraction + service-extraction). The audit step accepts a verdict shared across multiple emitters as long as every entry's emitter list resolves to a real skill.
- `ORCHESTRATOR_APPLY_REQUIRED` is emitted by the `fix-engineer` agent (via its spawn output), not a skill — agents emit verdicts through their structured output rather than a `verdict:` frontmatter field. The catalog tracks it for forensic completeness; the verdict-consistency audit step skips reverse-direction enforcement for agent-emitted entries (`Emitter skill` does not need to resolve to a `skills/<name>/SKILL.md` when it names an agent).
- `RECON_COMPLETE` and `RECON_NULL` are emitted by the `architect-context-recon` agent (Stage 1 of Plan Phase Dispatch), same agent-emitted-verdict pattern as `ORCHESTRATOR_APPLY_REQUIRED`. The catalog tracks them for forensic completeness.
- `VISUAL_DIFF_PASS` and `VISUAL_DIFF_FAIL` are emitted by the `vlm-critic` agent (via its structured stdout), not a skill — agents emit verdicts through their structured output rather than a `verdict:` frontmatter field. The catalog tracks them for forensic completeness; the verdict-consistency audit step skips reverse-direction enforcement for agent-emitted entries.
- Skills that act as pure utilities or pattern references and emit no verdict (e.g., `react-native-patterns`, `web-frontend-patterns` referenced as knowledge), or skills that are infrastructure for other systems (`capture`, `embedder`, `mcp_memory`, `recall`, `skill-builder`), are deliberately absent. The audit step's "every skill emits a verdict declared in catalog" check applies to skills WITH a `verdict:` field in their frontmatter — not to skills without one.
- The catalog is alphabetically loose but grouped roughly by phase (intake → plan → build → review → final-gate → ship → deploy → reflect → utility) for human reading. The audit step parses the table by row, not by section.
- `DOM_SMOKE_*` verdicts emit from build-implementation Step 2d; reason enums documented in `skills/build-implementation/SKILL.md` § Step 2d.
- `PLAN_FEASIBILITY_REJECTED` has two emitter rows: the light-gate row (emitter `plan-self-validation`, a real skill with the verdict declared in its `verdict:` frontmatter field) and the heavy-gate row (emitter `product-reviewer` + `software-engineer` agents). The agent-emitted heavy-gate row is exempt from reverse-direction enforcement, same pattern as `RECON_COMPLETE` / `ORCHESTRATOR_APPLY_REQUIRED` / `VISUAL_DIFF_*` — the audit step does not require it to resolve to a `skills/<name>/SKILL.md`.
- `feasibility_drift` is recorded in `learning/{project-hash}/observations.jsonl` under `phases.plan_validation.feasibility_drift` with shape `{architect_said: "FEASIBLE"|"FEASIBILITY_REJECTED", reviewers_concluded: "FEASIBLE"|"FEASIBILITY_REJECTED", overturned: bool}`; written by the 4d-i observation-append step (`skills/pipeline/SKILL.md` § 4d-i). Present with `overturned:false` when a feasibility pass RAN and both parties agreed FEASIBLE; absent ONLY when no feasibility pass ran (the absence rule keys on pass-ran, not on outcome).
