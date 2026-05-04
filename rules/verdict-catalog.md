# Verdict Catalog

Single source of truth for every verdict any skill in `~/.claude/skills/` is allowed to emit. The `/harness-audit` `verdict-consistency` step asserts this catalog and the actual skill frontmatter agree in both directions:

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
| `ROUTED` | info | `intake` | intake | `/pipeline`, `/tech-spike`, `/epic-breakdown`, or direct answer |
| `STORIES_READY` | info | `epic-breakdown` | plan | One `/pipeline` per story |
| `ESTIMATED` | info | `estimation` | plan | Pipeline continues with budget |
| `STORY_READY` | info | `story-writing` | plan | `/build-implementation` |
| `SPIKE_COMPLETE` | info | `tech-spike` | utility | Findings feed back into planning |
| `PLAN_APPROVED` | success | `plan-self-validation` | plan-validation | `/build-implementation` |
| `PLAN_HOLES` | failure | `plan-self-validation` | plan-validation | Architect re-plans (max 1 revision, then escalate to heavy challengers) |
| `BUILD_COMPLETE` | success | `build-implementation` | build | `/code-review` + `/security-review` |
| `BUILD_FAILED` | failure | `build-implementation` | build | Halt; user escalation or re-dispatch |
| `REFACTOR_COMPLETE` | success | `refactor` | build | `/code-review` + `/security-review` |
| `REFACTOR_FAILED` | failure | `refactor` | build | Halt; user escalation |
| `BUG_FIXED` | success | `bug-fix` | build | `/code-review` + `/security-review` |
| `BUG_UNRESOLVED` | failure | `bug-fix` | build | Halt; user escalation with hypothesis log |
| `TOOL_SYNTHESISED` | info | `tool-synthesis` | build | Build agent uses the scratch tool, deletes after use |
| `TOOL_UNNECESSARY` | info | `tool-synthesis` | build | Build agent proceeds with standard tools |
| `PLAN_REFINED` | info | `continuous-planning` | build | Build agents re-read plan; never gates Build completion |
| `PLAN_UNCHANGED` | info | `continuous-planning` | build | No effect; Build proceeds |
| `APPROVE` | success | `code-review`, `security-review` | review | Final Gate (verify + test + accept + patch-critique) |
| `CHANGES_REQUESTED` | failure | `code-review`, `security-review` | review | Spawn fix-engineer; raising reviewer re-reviews; max 2 rounds |
| `VERIFIED` | success | `verify` | final-gate | Pipeline advances to Test phase |
| `VERIFIED_WITH_SKIP` | info | `verify` | final-gate | Tier skipped with documented reason; advances |
| `UNVERIFIED` | failure | `verify` | final-gate | Halt; back to Build to address tier failures |
| `COVERED` | success | `qa-test-strategy` | final-gate | Pipeline advances to Accept phase |
| `GAPS_FOUND` | failure | `qa-test-strategy` | final-gate | Spawn fix-engineer to fill test gaps |
| `APPROVED` | success | `product-acceptance` | final-gate | Writes approval token; `/pr-creation` unblocked |
| `APPROVED_WITH_CONDITIONS` | success | `product-acceptance` | final-gate | Approval token written; conditions resolved in-cycle |
| `REJECTED` | failure | `product-acceptance` | final-gate | Halt; back to Build with AC violations |
| `PATCH_APPROVED` | success | `patch-critique` | final-gate | `/pr-creation` unblocked |
| `PATCH_REJECTED` | failure | `patch-critique` | final-gate | Spawn fix-engineer (in-cycle, no user escalation) |
| `POLISHED` | info | `polish` | utility | Continue to Review |
| `NO_CHANGES_NEEDED` | info | `polish` | utility | Continue to Review |
| `SCREENSHOTS_CAPTURED` | info | `design-qc` | utility | Product-reviewer consumes screenshots |
| `CAPTURE_FAILED` | failure | `design-qc` | utility | Product-reviewer warned; falls back to text review |
| `PR_CREATED` | success | `pr-creation` | ship | `/deploy` (if CD configured) |
| `PR_BLOCKED` | failure | `pr-creation` | ship | Halt; missing approval token or quality-gate failure |
| `DEPLOYED` | success | `deploy` | deploy | `/deployment-verification` |
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
| `NO_CHANGE` | info | `eval-model-effectiveness` | utility | Recommendations unchanged from prior run |
| `EVAL_PASSED` | success | `internal-eval` | utility | Harness PR can merge |
| `EVAL_FAILED` | failure | `internal-eval` | utility | Harness PR blocked; regressions on deterministic cases |
| `EVAL_BASELINE_CAPTURED` | info | `internal-eval` | utility | Baseline written; subsequent runs diff against it |
| `INSUFFICIENT_CASES` | info | `internal-eval` | utility | Not enough cases to score; rerun later |
| `CLEAN` | info | `forensics` | utility | No anomalies found in pipeline trajectory |
| `ANOMALIES_FOUND` | info | `forensics` | utility | Anomalies surfaced; report written for human review |
| `INVESTIGATION_INCOMPLETE` | info | `forensics` | utility | More data needed; user instructed |
| `DEBUG_ACTIVE` | info | `debug` | utility | Persistent debug state created/updated |
| `DEBUG_RESOLVED` | success | `debug` | utility | Bug resolved; pipeline resumes from Review |
| `DEBUG_ESCALATED` | failure | `debug` | utility | Iteration cap hit; user escalation |
| `TRACE_TOGGLED` | info | `debug-trace` | utility | Per-session prompt tracing on/off |
| `HEALTHY` | info | `harness-audit`, `health-scan` | utility | No issues |
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
| `WORKSTREAM_CREATED` | info | `workstream` | utility | New workstream isolated under `pipeline-state/workstreams/` |
| `WORKSTREAM_LISTED` | info | `workstream` | utility | Active workstreams reported |
| `WORKSTREAM_ARCHIVED` | info | `workstream` | utility | Workstream removed |
| `REINDEXED` | info | `reindex-memory` | utility | FTS5 index rebuilt |
| `NOOP` | info | `reindex-memory` | utility | Nothing to do |
| `FAILED` | failure | `reindex-memory` | utility | Fatal error during reindex |

## Notes

- `WRONG_SKILL` and `EXTRACTION_BLOCKED` appear in two emitters each (microservices-scaffold + module-extraction; module-extraction + service-extraction). The audit step accepts a verdict shared across multiple emitters as long as every entry's emitter list resolves to a real skill.
- Skills that act as pure utilities or pattern references and emit no verdict (e.g., `react-native-patterns`, `web-frontend-patterns` referenced as knowledge), or skills that are infrastructure for other systems (`capture`, `embedder`, `mcp_memory`, `recall`, `skill-builder`), are deliberately absent. The audit step's "every skill emits a verdict declared in catalog" check applies to skills WITH a `verdict:` field in their frontmatter — not to skills without one.
- The catalog is alphabetically loose but grouped roughly by phase (intake → plan → build → review → final-gate → ship → deploy → reflect → utility) for human reading. The audit step parses the table by row, not by section.
