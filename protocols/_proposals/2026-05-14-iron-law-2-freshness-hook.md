# Proposal: Mechanical Enforcement of Iron Law 2 (Verification Evidence Freshness)

**Status:** PROPOSED (2026-05-14)
**Owner:** orchestrator-derived recommendation from production-readiness audit
**Implementation track:** requires `/pipeline` run (touches a new hook, state-file schema, and 3 skill input contracts)

---

## Problem

Iron Law 2 (`rules/core.md:10`) states:

> NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE. Stale test output from earlier in the session is not evidence — re-run before claiming done.

Audit finding: **this iron law is not enforced by any hook or gate**. Three places accept "fresh test output" as an input contract:

- `skills/patch-critique/SKILL.md` line 34: "Most recent **fresh** test-suite run."
- `agents/patch-critic.md` line 52: "the most recent fresh test-suite run."
- `agents/patch-critic.md` line 34 (Operating Discipline): "Stale results from earlier in the session are not evidence. Re-invoke the tool if the failure mode warrants a retry; otherwise surface the missing result to the orchestrator and stop."

None of these check timestamps. The orchestrator is **told** to pass fresh output; agents are **told** to push back if it's stale; but nothing measures it. This is the primary structural reason production code can pass review/tests but fail at runtime — the failure mode is "test output looked green; code had mutated since the run; nobody noticed."

## Proposed Solution

A new PreToolUse hook `hooks/verification-freshness-guard.sh` that runs on Agent spawns for `patch-critic`, `product-reviewer`, and the `pr-creation` skill dispatcher. The hook reads a small state file written by Verify, compares its recorded `git_head` to the current worktree HEAD, and emits a structured JSONL record (advisory log at v2.1.141; will block once `permissionDecision` ships on the Agent matcher) if the recorded HEAD does not match.

### State file convention

`pipeline-state/{task-id}/verification-evidence.json` (schema_version 1):

```json
{
  "schema_version": 1,
  "task_id": "abc123",
  "git_head": "a1b2c3d4...",
  "generated_at": "2026-05-14T10:33:47Z",
  "verdict": "VERIFIED",
  "tier_results": {
    "contract": {"status": "PASS"},
    "smoke": {"status": "PASS"},
    "mutation": {"status": "PASS", "score": 0.78},
    "mutation_llm": {"status": "PASS", "score": 0.65},
    "e2e": {"mobile": "N/A", "web": "N/A", "composite": "VERIFIED"}
  },
  "sandbox_run": {"status": "SANDBOX_VERIFIED", "session": "e2b-abc123"}
}
```

The state file is written by the `/verify` skill at the end of each tier and re-written on every re-run. It is read by the freshness guard before any spawn that depends on test evidence.

### Freshness rules

1. **`git_head` mismatch**: `verification-evidence.git_head` does not equal current worktree HEAD → `would_block` with `reason: git_head_mismatch`, `staleness_class: hard`. This catches the case where a fix-engineer re-dispatch (the In-Cycle Fix loop hot path) advanced HEAD after `/verify`.
2. **Missing state file**: no `verification-evidence.json` exists → `would_block` with `reason: state_file_missing`.
3. **Hard staleness (TTL)**: `generated_at` is older than `HARD_TTL_SEC` (default 86400 / 24h) → `would_block` with `reason: hard_staleness`. Soft staleness (`advisory_warn`) is deferred to a follow-up — see § Out of Scope.
4. **Sandbox staleness**: `sandbox_run.status` is not `SANDBOX_VERIFIED` → `would_block` with `reason: sandbox_staleness`. Sandbox check runs BEFORE `git_head` check; first-failure wins.
5. **Worktree unresolvable**: neither `$CLAUDE_WORKTREE_PATH` env nor stdin `tool_input.cwd` resolves to a git directory → skip-clean (`action: fresh`, `reason: no_worktree_resolvable`). NEVER block — the orchestrator-env-propagation contract (see `orchestrator/agent-orchestration.md § Worktree Env Propagation`) is the load-bearing fix; the hook must not deadlock spawns that lack a worktree at v1.

### Hook is Path-B-aware

Like the existing `pre-agent-thinking.sh` (`protocols/thinking-defaults.md` § Hook Behavior), this hook starts **log-only** at v2.1.141 because the `permissionDecision: "deny"` field is NOT yet schema-exposed on the Agent matcher. Promotion to block-mode is a single-file flip once the team has the promotion criterion (§ Promotion Criterion) satisfied.

Emit format (matches other Path-B hooks; written via `hooks/_lib/log-injection.sh` with custom filename `freshness-guard.jsonl`):

```jsonl
{"timestamp":"2026-05-14T12:35:00Z","source":"path-b-advisory","agent_role":"patch-critic","resolved":{"action":"would_block","reason":"git_head_mismatch","state_file_head":"9a1b2c3d","worktree_head":"deadbeef","task_id":"iron-law-2-freshness-hook","tier_results_summary":"VERIFIED","staleness_class":"hard"}}
```

Logged to `metrics/{session}/freshness-guard.jsonl`. `/forensics` consumes the file.

## Integration Points

1. **`skills/verify/SKILL.md`** — add Step 6: "Write `pipeline-state/{task-id}/verification-evidence.json` with the schema above using `os.replace` atomic rename. Resolve the write target via `_psp_verification_evidence_path` relative to `$CLAUDE_REPO_ROOT` (not cwd)."
2. **`skills/patch-critique/SKILL.md`** — append one row to the `## Inputs` table: `Verification evidence | pipeline-state/{task-id}/verification-evidence.json written by /verify Step 6`. Existing missing-input semantics inherit (returns `PATCH_REJECTED` with `reason: missing input: {name}`).
3. **`skills/pr-creation/SKILL.md` quality-gate check** — `_qg_check_freshness` is added to `hooks/_lib/quality-gate-checks.sh` and `freshness` is added to the `for check in tests lint audit shape contract` loop in `hooks/quality-gate.sh:31`. Synchronous blocking gate on `gh pr create`.
4. **`agents/patch-critic.md`** — its Operating Discipline already states "Stale results from earlier in the session are not evidence" (line 34). APPEND a sentence after the trailing parenthetical pointing at the hook: ` Enforcement: hooks/verification-freshness-guard.sh (log-only at v2.1.141; blocks once permissionDecision ships on Agent matcher).` (S5 — append-only edit, not a replacement of the broader paragraph).
5. **`hooks/_lib/pipeline-state-paths.sh`** — add `_psp_verification_evidence_path "$task" "$ws"` helper, follows the existing `_psp_*` convention (corrects the proposal's earlier `_state_verification_evidence_path` / `state_paths.sh` reference — see intake discrepancy #2).
6. **`orchestrator/agent-orchestration.md`** — new `## Worktree Env Propagation` H2 mandating the orchestrator set `$CLAUDE_WORKTREE_PATH` on every Build-onward Agent dispatch. This is the load-bearing contract for HEAD resolution rule 1 in the hook.

## Edge Cases

- **Worktree HEAD vs. main HEAD**: the agent worktree always runs ahead of `main`. The hook reads from `$CLAUDE_WORKTREE_PATH` first (orchestrator-supplied), `tool_input.cwd` second, skip-clean third. State file is per-task-id, not per-worktree.
- **No changes since last test run**: PASS — `git_head` matches → fresh.
- **CI pre-merge re-run**: orthogonal to this hook. CI runs are separate from local pipeline verification evidence; the PR-creation gate already integrates CI status separately.
- **`isolation: "worktree"` race**: state file is task-id-scoped, not slice-scoped. `/verify` writes via `os.replace` for atomic rename.
- **`fix-engineer` re-dispatch in code-review loop**: every fix-engineer Edit invalidates the state file's `git_head`. The hook will log `would_block` (v2.1.141) / block (post-promotion) on the next patch-critic dispatch until `/verify` re-runs. This is the intended behaviour — fix-engineer rounds are the most common source of stale-evidence completion claims.

## Cost

- Hook execution time: < 50ms (single file read + `timeout 2 git rev-parse HEAD`). Negligible against subagent spawn cost.
- New state file write per `/verify` run: < 1KB. Negligible.
- Failure recovery: if `/verify` must re-run because the freshness guard blocked patch-critic, the cost is one extra `/verify` spawn (~10–15% of a pipeline's total cost). This is **a feature, not a bug**: the alternative is shipping code that doesn't work and re-doing the entire pipeline.

## Implementation Checklist

1. **`hooks/verification-freshness-guard.sh`** (new) — ~80 LOC bash script following the Path-B advisory pattern from `hooks/pre-agent-allowlist.sh`. Reads `pipeline-state/{task-id}/verification-evidence.json`, compares to worktree HEAD, emits JSONL via `_lib/log-injection.sh` with filename `freshness-guard.jsonl`.
2. **`hooks/_lib/resolve-freshness.py`** (new) — ~60 LOC Python resolver delegate, mirrors `resolve-tool-allowlist.py`.
3. **`hooks/_lib/pipeline-state-paths.sh`** — add `_psp_verification_evidence_path` helper.
4. **`hooks/_lib/quality-gate-checks.sh`** — add `_qg_check_freshness` (≤8 lines, `jq`-based, matches existing `_qg_*` style).
5. **`hooks/quality-gate.sh:31`** — add `freshness` to the iterated check list.
6. **`settings.json`** — register the hook on PreToolUse with `matcher: "Agent"`, array index 6 (after `instinct-injector` at index 5; before `scratchpad-bytes`).
7. **`skills/verify/SKILL.md`** — add Step 6 (Write Verification Evidence State File).
8. **`skills/patch-critique/SKILL.md`**, **`skills/pr-creation/SKILL.md`**, **`skills/product-acceptance/SKILL.md`** — update input contracts.
9. **`agents/patch-critic.md`** — APPEND hook reference to the Operating Discipline paragraph (NOT replace).
10. **`tests/test_freshness_guard.py`** (new) — ≥17 unit tests covering the spec scenarios.
11. **`tests/test_settings_registers_freshness_hook.py`** (new) and update of `tests/test_settings_registers_instinct_hook.py` EXPECTED_ORDER (10 entries).
12. **`rules/core.md` Iron Law 2** — append parenthetical naming hook at v2.1.141.
13. **`/forensics`** — add a check for `freshness-guard.jsonl` records with `action="would_block"` and `source="path-b-advisory"`. These are the cases where a pipeline almost-shipped on stale evidence and the team needs to see them.

## Counter-arguments considered

- **"Iron Laws are honored by all agents; mechanical enforcement is overkill."** Empirically false in this codebase. The audit found explicit prose telling agents to push back on staleness; no measurement of whether they actually do. Pure honor systems fail proportional to load. Mechanical enforcement is cheap.
- **"This will false-positive on git operations that don't change source (e.g. amended commit messages, .gitignore tweaks)."** Possible. Amended commits DO change `git_head` — but they also change semantics, so re-running tests is correct policy.
- **"The state-file approach couples Verify and Patch-Critic via filesystem state. Why not pass test output directly?"** Direct passing exists today and is the failure mode this proposal closes. Filesystem state is the verifiable handoff; the alternative requires the orchestrator to never make a mistake about which test output is current. Decoupling-via-state is the standard pattern.
- **"This is the kind of governance that bureaucratizes the pipeline."** Considered. The hook adds < 50ms per spawn, blocks zero spawns until proven necessary (Path-B), and the only "bureaucracy" it adds is "the pipeline does what it says it does." Iron Law 2 already exists; this proposal just makes it true.

## Rollback

Remove the hook from `settings.json`, delete `verification-freshness-guard.sh` and `resolve-freshness.py`, revert the SKILL.md edits. The state file becomes unused but harmless. Single-file flip target for promotion is the `exit 0` at the end of the `would_block` branch in `verification-freshness-guard.sh` — replace with `exit 2` once promotion criterion (§ Promotion Criterion) is satisfied.

## Promotion Criterion

Flip from Path-B advisory to Path-A `exit 2` ONLY after ALL of:

1. **≥14 days post-merge AND ≥50 pipelines complete** with 0 `would_block` records of any kind on the 3 gated roles after AC3.13's orchestrator-env-propagation contract is provably honored.
2. **`permissionDecision` schema-exposed on PreToolUse Agent matcher** per Claude Code release notes.
3. **Operator review** of forensics report from at least the last 7 days; sign-off recorded in promotion PR.

Promotion PR is a single-file change to `hooks/verification-freshness-guard.sh` — replace `exit 0` at end of the `would_block` branch with `exit 2`.

## Operator Copy

| reason | stderr_post_promotion | forensics_label | recovery_action |
|---|---|---|---|
| `fresh` | (no stderr — PASS path) | Fresh | (no action) |
| `state_file_missing` | `[freshness] no verification-evidence; run /verify` | Missing evidence | Re-run `/verify` |
| `git_head_mismatch` | `[freshness] state=X worktree=Y; HEAD moved since /verify` | HEAD moved post-/verify | Re-run `/verify` |
| `hard_staleness` | `[freshness] evidence is older than 24h; re-verify` | Evidence stale | Re-run `/verify` |
| `no_worktree_resolvable` | `[freshness] cannot resolve worktree; set $CLAUDE_WORKTREE_PATH on dispatch` | Worktree unresolvable | Verify `$CLAUDE_WORKTREE_PATH` is set on the spawning Agent call; grep recent dispatch logs at `metrics/{session}/`. See `orchestrator/agent-orchestration.md § Worktree Env Propagation` for the contract. |
| `sandbox_staleness` | `[freshness] sandbox verdict missing or pre-empted; re-run sandbox-verify` | Sandbox stale | Re-run `/sandbox-verify` |
| `state_file_parse_error` | `[freshness] evidence file unparseable; re-verify` | Parse error | Re-run `/verify` |
| `git_timeout` | `[freshness] git rev-parse hung; investigate worktree state` | git timeout | Inspect worktree `.git/index.lock` |

## Out of Scope

1. Post-promotion Path-A `exit 2` enforcement — separate follow-up PR.
2. Soft staleness / `advisory_warn` — deferred follow-up after orchestrator-env-propagation soak.
3. BFF / multi-channel propagation of `verification-evidence.json`.
4. Cross-pipeline freshness check.
5. Auto-re-run `/verify` on staleness from orchestrator — state-machine concern, separate PR.
6. GUI dashboard for `freshness-guard.jsonl`.
7. Modifying `/verify`'s tier-execution logic — only adds Step 6.
8. Behavioural test asserting every orchestrator dispatch site sets `$CLAUDE_WORKTREE_PATH` — covered by forensics review during promotion-window soak; promotion criterion clause (a) is the load-bearing check.

---

**Linked PR for the freshness-hook track:** PR #125 (this proposal) + implementation PR (track this branch).
