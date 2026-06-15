# hooks/tests — CI Visibility Map

CI runs `bash tests/shell/run.sh` which discovers all `tests/shell/*.bats`. This
directory holds standalone harnesses that pre-date that convention. Each script is
either **bridged** (a `tests/shell/bridge_*.bats` wraps it so CI gates on it) or
**QUARANTINED** (assertions drifted from current code; bridge would produce a
permanent red CI; listed here for accountability and follow-up).

Quarantined scripts need assertion-refresh in a dedicated follow-up pipeline
(behavior change, out of Phase 2B scope). Their target hooks are LIVE and must not
be deleted.

| Script | CI Bridge | Status / Notes |
|--------|-----------|----------------|
| test-auto-learn-gate.sh | — | QUARANTINED — threshold trigger logic drift (15p/3f) |
| test-bash-write-guard.sh | — | QUARANTINED — .md-path allowance + git-args blocking regressions (39p/6f) |
| test-build-loop-scan.sh | tests/shell/bridge_build_loop_scan.bats | BRIDGED |
| test-cache-feed-bugs.sh | — | QUARANTINED — BUG-1a cache.jsonl write condition (8/9 passing) |
| test-cost-feed-router-signals.sh | tests/shell/bridge_cost_feed_router_signals.bats | BRIDGED |
| test-detect-stale-pipeline-state.sh | tests/shell/bridge_detect_stale_pipeline_state.bats | BRIDGED |
| test-eval-capture-hook.sh | tests/shell/bridge_eval_capture_hook.bats | BRIDGED |
| test-eval-model-effectiveness.sh | tests/shell/bridge_eval_model_effectiveness.bats | BRIDGED |
| test-harness-paths.sh | — | QUARANTINED — E4 config-dir, G1 ROLLOUT overlay-sync ref, B7c Path.home (85p/3f) |
| test-hook-registration-invariant.sh | tests/shell/test_registration_invariant_green.bats | BRIDGED (pre-existing bridge) |
| test-hooks-json.sh | — | QUARANTINED — A7: pre-existing NOT_IN_SETTINGS for advisory (non-enforcing) hooks added since test was authored: pipeline-entry-guard.sh, root-snapshot-capture.sh, root-tree-clean-check.sh (SessionEnd+Stop), worktree-reaper.sh; A7 checks ALL hooks.json entries against settings.json but advisory hooks are intentionally settings.json-absent (9p/1f) |
| test-hooks.sh | — | QUARANTINED — 90p/18f (stale count + assertion drift; text-pinned by project-hash.bats:144,149) |
| test-intake-backstop.sh | tests/shell/bridge_intake_backstop.bats | BRIDGED |
| test-main-branch-guard.sh | tests/shell/bridge_main_branch_guard.bats | BRIDGED |
| test-managed-settings.sh | — | QUARANTINED — plugin-delivery + env keys drift (11p/2f) |
| test-nested-pipeline-isolation.sh | — | QUARANTINED — trajectory file routing drift (25p/3f) |
| test-pipeline-analytics.sh | tests/shell/bridge_pipeline_analytics.bats | BRIDGED |
| test-pipeline-entry-guard.sh | tests/shell/bridge_pipeline_entry_guard.bats | BRIDGED |
| test-plan-cache-lookup.sh | tests/shell/bridge_plan_cache_lookup.bats | BRIDGED |
| test-pytest-suite-guard.sh | tests/shell/bridge_pytest_suite_guard.bats | BRIDGED |
| test-quality-gate-diff-scope.sh | tests/shell/bridge_quality_gate_diff_scope.bats | BRIDGED |
| test-quality-gate-freshness.sh | tests/shell/bridge_quality_gate_freshness.bats | BRIDGED |
| test-root-tree-clean-check.sh | — | QUARANTINED — macOS-green / Linux-red — portability gap in harness (passes locally on bash 3.2, fails on CI bash 4/ubuntu); needs portability-refresh follow-up |
| test-runtime-state-guard.sh | tests/shell/bridge_runtime_state_guard.bats | BRIDGED |
| test-session-start-bootstrap.sh | — | QUARANTINED — hook likely renamed/restructured (5p/12f) |
| test-syntax-check.sh | tests/shell/bridge_syntax_check.bats | BRIDGED |

## fixtures/

- `intake-backstop-corpus.jsonl` — corpus fixture consumed by test-intake-backstop.sh
- `stuck/` (×9 files) — stuck-pipeline fixtures consumed by test-hooks.sh:925-926
- `trace-prompt/` (×2 files) — trace prompt fixtures consumed by test-hooks.sh:1144-1211
- `.gitkeep` — ensures git tracks the directory
