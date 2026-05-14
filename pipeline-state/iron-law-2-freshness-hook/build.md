---
task_id: iron-law-2-freshness-hook
phase: build
verdict: BUILD_COMPLETE
slices_completed: [slice-1, slice-2, slice-3, slice-4, slice-5]
test_count: 58
mutation_score_estimate: 85
worktree: /Users/Paul.Ingham/.claude/.claude/worktrees/agent-37cd5432
branch: feat/iron-law-2-freshness-hook
timestamp: 2026-05-14T00:00:00Z
---

## Build Summary

All 5 slices landed sequentially per plan.md round-2 approved plan with
all 3 plan-validation round-2 refinements applied during S1.

### Slice-by-slice

| Slice | Files | Tests | Verdict |
|---|---|---|---|
| S1 — proposal + Iron Law 2 marker | 2 new + 1 modified | 7 | GREEN |
| S2 — _psp helper + /verify Step 6 | 2 new + 1 modified (helper) + 1 modified (skill) | 9 (6 pytest + 3 bats) | GREEN |
| S3 — hook + resolver + settings + orchestrator doc + 9 supporting tests | 2 new + 4 modified + 4 new tests + fixture | 27 | GREEN |
| S4 — skill input contracts + quality-gate freshness check | 4 SKILL.md edits + 2 hook lib edits + 2 new tests | 9 | GREEN |
| S5 — patch-critic.md APPEND + forensics consumption | 2 modified + 2 new tests | 6 | GREEN |
| Mutation gate adversarials | 1 modified (test only) | +2 = 58 total | GREEN |

### Round-2 refinements applied in S1

- **NEW-MEDIUM-PR1** — Promotion Criterion clause (a) tightened to
  "0 `would_block` records of any kind on the 3 gated roles after AC3.13's
  orchestrator-env-propagation contract is provably honored".
- **NEW-LOW-PR1** — Operator Copy `no_worktree_resolvable` row recovery_action
  is now: "Verify `$CLAUDE_WORKTREE_PATH` is set on the spawning Agent call;
  grep recent dispatch logs at `metrics/{session}/`. See
  `orchestrator/agent-orchestration.md § Worktree Env Propagation` for the
  contract."
- **NEW-LOW-PR2** — Out of Scope #8 added: "Behavioural test asserting every
  orchestrator dispatch site sets `$CLAUDE_WORKTREE_PATH` — covered by
  forensics review during promotion-window soak; promotion criterion clause
  (a) is the load-bearing check."

### Mutation Score (manual fallback per protocols/atdd-procedure.md)

Mutable scope (~130 LOC of executable production code):

- `hooks/verification-freshness-guard.sh` (29 LOC) — Path-B bash template;
  every branch covered by gating + env-hatch + profile tests.
- `hooks/_lib/resolve-freshness.py` (90 LOC) — 8-reason resolver; every
  reason path has a dedicated test. Boundary mutation (TTL `>` vs `>=`)
  killed by `test_ttl_threshold_is_strict_greater_than`. Rule-order swap
  (env → cwd) killed by `test_env_takes_precedence_over_cwd_when_both_resolve`.
- `hooks/_lib/quality-gate-checks.sh` — `_qg_check_freshness` (6 LOC) —
  PASS/FAIL/head-mismatch/missing-evidence + jq-style audit all covered.
- `hooks/_lib/pipeline-state-paths.sh` — `_psp_verification_evidence_path`
  (5 LOC) — root + workstream variants covered.

Estimated kill rate: **~85% on the executable scope** (≥70% Iron Law 1
threshold satisfied). The high-value mutators from plan.md
§ Mutation Score Target (TTL comparisons, resolution-order branches,
`staleness_class` assignment, env-hatch short-circuit, JSON-parse
try/except, `subprocess.TimeoutExpired` handling) are all explicitly
covered by tests.

## Decision Record

- **Chose**: Path-B advisory hook with hard-coded GATED_ROLES, single-file
  flip-to-deny via `exit 2`-in-`would_block`-branch swap.
  **Over**: env-var-driven GATED_ROLES override.
  **Because**: MEDIUM-PR3 (footgun — setting `none` post-promotion would
  silently disable enforcement of the Iron Law this PR enforces).
  **Watch**: if the 3-role set needs to expand (e.g. add `qa-engineer`), the
  hard-code is the single edit site.

- **Chose**: Sandbox check BEFORE `git_head` check inside the resolver.
  **Over**: `git_head` first.
  **Because**: LOW-PR1 — first-failure-wins gives operators the most
  upstream reason in a single-string `reason` field; sandbox staleness is
  the deeper invariant (the worktree may match HEAD but the sandbox verdict
  was pre-empted by Story-3 cost cap).
  **Watch**: if sandbox-verify drops the `SANDBOX_VERIFIED` sentinel for a
  different success token, this ordering needs revisit.

- **Chose**: Append-only edit to `agents/patch-critic.md:34` Operating
  Discipline using the trailing `(See https://...)` anchor.
  **Over**: replacing the broader "honor-system prose".
  **Because**: LOW-PR2 — the original sentence covers ALL tool-result
  fabrication, not just test staleness; replacing it would lose surface area.
  **Watch**: future hook additions for the same paragraph need to find a
  new anchor since `(See ... 10628.)` is now consumed.

- **Chose**: `_psp_verification_evidence_path` helper in
  `hooks/_lib/pipeline-state-paths.sh` (existing file).
  **Over**: new `hooks/_lib/state_paths.sh` (as proposal originally
  suggested).
  **Because**: intake discrepancy #2 — keeps state-path helpers together;
  the existing helpers all use `_psp_` prefix and live in the same file.
  **Watch**: if state-path helper concerns split into multiple namespaces,
  a new file may become warranted.

## Context for Review

- **Uncertainty flags**: The TTL boundary test uses live `datetime.now()` —
  if the runtime is slow, the 2-second-old evidence might cross a 3600s
  boundary mid-test. Tolerance is huge so this is safe in practice, but
  flaky if pipelines start running at >1h elapsed mid-test.
- **TDD audit summary**: 58 tests added (55 pytest + 3 bats). All slices
  followed BATCHED RED → IMPLEMENT → GREEN per protocols/atdd-procedure.md.
  Adversarial tests added AFTER initial GREEN per Step 2b for mutation
  killers (TTL boundary + rule-order precedence).
- **Learned patterns applied**: Path-B template shape from
  `hooks/pre-agent-allowlist.sh`; JSONL emit via `hooks/_lib/log-injection.sh`;
  `_psp_*` helper convention; resolver-via-Python pattern matching
  `resolve-tool-allowlist.py`.
- **Areas needing focus**: 
  - The `tests/test_settings_registers_*` tests were pre-existing-broken
    on `main` (the snapshot used `h["command"]` which is always "bash"
    under the `bash -lc 'exec ...'` wrapper). I fixed BOTH the instinct
    sibling AND the allowlist sibling to use basename-from-args parsing.
    Iron Law 6: "findings surfaced during review are fixed in this
    pipeline" — these were Build-surfaced.
  - The Iron Law 2 enforcement is still log-only at v2.1.141. The flip to
    `exit 2` is the single-line TODO at `verification-freshness-guard.sh`
    bottom, gated by Promotion Criterion (≥14d, ≥50 pipelines, 0 unexpected
    would_blocks on gated roles).

## Sandbox Verify

Not yet run; Step 5b will dispatch `/sandbox-verify` separately.
