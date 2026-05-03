---
category: pattern
---

Slice C migration of 26 SKILL.md files completed across 7 commits (one per group plus a docs commit for `internal-eval/run/ISOLATION.md`).

## Group-by-group result

| Group | Skills | Tests it satisfies | Commit |
|---|---|---|---|
| 1 — Core writers | pipeline, intake, build-implementation, product-acceptance, pr-creation, deploy, learn (+ no-op for code-review/security-review/verify/qa-test-strategy/patch-critique/deployment-verification — those skills had no flat-layout references) | `test_pipeline_skill_creates_state_under_subdir`, `test_intake_writes_intake_md_under_subdir`, all 4 cleanup tests | fbb6b0f |
| 2 — Greenfield | greenfield-scaffold, creative-direction, design-system-init, project-setup | `test_greenfield_writes_product_brief_under_subdir` | a7b60aa |
| 3 — Module/service | module-extraction, microservices-scaffold, service-extraction | `test_module_extraction_writes_boundary_analysis_under_subdir` | c1324df |
| 4 — Build alts | bug-fix, debug (refactor had no flat refs) | none directly; covered by Slice E debug fixtures | e8bbb32 |
| 5 — Forensics + planning | forensics, continuous-planning | `test_continuous_planning_writes_planning_cursor_under_subdir` | 4ed758e |
| 6+7 — Specialised + POLICY | batch-pipeline, tool-synthesis, health-scan | `test_health_report_relocation.sh` | d41011d |
| Docs annotation | internal-eval/run/ISOLATION.md | none (descriptive) | bc6b5e7 |

## Cross-slice gaps surfaced

1. **Approval-token xfail (expected)**: `tests/test_approval_token_path_migration.sh` is xfail in this isolated worktree (RC=99) because `_at_write_token` lives in `hooks/_lib/approval-token.sh` (Slice B). At integration time when Slice B's diff lands, the test should turn GREEN (RC=0).

2. **`skills/internal-eval/run/ISOLATION.md` was NOT in the plan's Group list**, but it had legacy-only collision-surface descriptions. I annotated it with "canonical X (legacy: Y)" form to keep the document accurate during the soak. This is descriptive, not load-bearing — no test pins it.

3. **`skills/workstream/SKILL.md` is Slice D's domain** but contains 5 references to legacy-form workstream paths (`pipeline-state/workstreams/{name}/{task-id}-pipeline.md` etc.). These intentionally remain unchanged in Slice C — Slice D will refactor.

4. **`skills/pipeline-resume/SKILL.md` is Slice D's domain** — left untouched.

5. **Bare `pipeline-state/*-pipeline.md` glob in `skills/intake/SKILL.md` Step 3.2** (line 189): this is an in-progress-pipeline detection check. Per plan, intake's pre-flight check is read-side and is owned by Slice D's resume-glob update. Left unchanged.

## Pattern: "legacy-fallback-as-pipe" idiom

Forensics added `cmd new || cmd legacy` chains to every read site:

```bash
cat ~/.claude/pipeline-state/{task-id}/trajectory.jsonl 2>/dev/null \
  || cat ~/.claude/pipeline-state/{task-id}-trajectory.jsonl 2>/dev/null
```

This idiom is the cleanest way to express "prefer new layout, fall back to legacy during DUAL_PATH soak" without conditionals. Future skill authors should use it for any read site that needs both layouts.

## R12 mitigation cost

The `_psp_phase_list` enumeration approach in `skills/pipeline/SKILL.md` Step 7d is verbose (~20 lines of bash) compared to a single-glob delete. The verbosity is the price of correctness — bare wildcard globs like `pipeline-state/{task-id}-*.md` would match prefix neighbours (e.g. cleanup of task `tool` would silently delete `tool-timing-capture-pipeline.md`). The test `test_reflect_cleanup_does_not_match_prefix_neighbors` locks this in.

## Decision: do NOT touch product-acceptance approval token writer location text

Slice C does NOT modify `_at_write_token` (Slice B owns the writer). The Slice C update to `skills/product-acceptance/SKILL.md` only documents that the token path is `pipeline-state/{task-id}/approval.token` — the actual write happens via the helper script which Slice B refactors. Cross-slice gap is intentional.

## Branch tip

`bc6b5e7` on `agent-07085b7d` (worktree-local — see verdict notes below regarding the slice-c branch name collision).
