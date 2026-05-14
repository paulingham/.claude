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

A new PreToolUse hook `hooks/verification-freshness-guard.sh` that runs on Agent spawns for `patch-critic`, `product-reviewer`, `qa-engineer`, and the `pr-creation` skill dispatcher. The hook reads a small state file written by Verify, compares its mtime to the latest code-mutation mtime in the worktree, and emits a structured warning (or block, once schema lands) if the test output is older than the latest source change.

### State file convention

`pipeline-state/{task-id}/verification-evidence.json`:

```json
{
  "task_id": "abc123",
  "phase": "verify",
  "test_run": {
    "started_at": "2026-05-14T10:32:11Z",
    "completed_at": "2026-05-14T10:33:47Z",
    "command": "pytest tests/ -v",
    "pass_count": 47,
    "fail_count": 0,
    "skip_count": 3,
    "verdict": "PASS",
    "git_head": "a1b2c3d4..."
  },
  "mutation_run": {
    "completed_at": "2026-05-14T10:36:21Z",
    "kill_rate": 0.78,
    "verdict": "PASS"
  },
  "sandbox_run": {
    "completed_at": "2026-05-14T10:38:02Z",
    "verdict": "SANDBOX_VERIFIED"
  }
}
```

The state file is written by the `/verify` skill at the end of each tier and re-written on every re-run. It is read by the freshness guard before any spawn that depends on test evidence.

### Freshness rules

1. **Hard staleness**: `test_run.completed_at` is older than the most recent `git log -1 --format=%ct` on the worktree HEAD → BLOCK the spawn with a clear error and instruction to re-run Verify.
2. **Soft staleness (warning, not block)**: `test_run.completed_at` is within 60 seconds of HEAD commit time → emit a warning (likely a race, possibly OK).
3. **`git_head` mismatch**: `test_run.git_head` does not equal current worktree HEAD → BLOCK regardless of timestamps. This catches the case where someone amended a commit but didn't re-run tests.
4. **Missing state file**: no `verification-evidence.json` exists → BLOCK for `patch-critic` / `pr-creation`; emit warning for `product-reviewer` (it can sometimes operate without).
5. **Sandbox staleness (additive)**: if `sandbox_run` is missing or older than `test_run`, mark `sandbox: STALE` in the spawn prompt — does not block, but downstream agents know not to trust the sandbox verdict.

### Hook is Path-B-aware

Like the existing `pre-agent-thinking.sh` (`protocols/thinking-defaults.md` § Hook Behavior), this hook starts **log-only** because the `permissionDecision: "deny"` field is fully supported on PreToolUse spawns. Promotion to block-mode is a single-file flip once the team has 14 days of forensic data showing the freshness rules don't false-positive on legitimate workflows (e.g. git status changes that don't touch source).

Emit format (matches other Path-B hooks):

```jsonl
{"ts":"2026-05-14T10:39:01Z","hook":"verification-freshness-guard","subagent_type":"patch-critic","verdict":"WOULD_BLOCK","reason":"git_head_mismatch","test_head":"a1b2c3d","current_head":"e5f6g7h","source":"path-b-advisory"}
```

Logged to `metrics/{session}/freshness-guard.jsonl`. `/forensics` consumes the file.

## Integration Points

1. **`skills/verify/SKILL.md`** — add Step Final: "Write `pipeline-state/{task-id}/verification-evidence.json` with the schema above. This file is the only valid evidence of fresh verification for downstream gates."
2. **`skills/patch-critique/SKILL.md` line 27 (Input contract)** — add: "Orchestrator MUST pass `verification-evidence.json` path. If absent or stale per the freshness guard, the orchestrator MUST re-run `/verify` BEFORE dispatching patch-critic. No exceptions."
3. **`skills/pr-creation/SKILL.md` quality-gate check** — load `verification-evidence.json` and block PR creation if any tier is stale. Today the quality gate is hook-driven (`hooks/quality-gate.sh`); this proposal extends it to consume the new state file.
4. **`agents/patch-critic.md`** — its Operating Discipline already states "Stale results from earlier in the session are not evidence" (line 34). Replace the honor-system prose with: "The orchestrator's PreToolUse `verification-freshness-guard` hook has already validated the staging area; if you receive this spawn, treat the test output as fresh and proceed. If you suspect staleness anyway, surface immediately and stop."
5. **`hooks/_lib/state_paths.sh`** — add `_state_verification_evidence_path` helper, parallel to the existing `_psp_find_active_pipelines` helper.

## Edge Cases

- **Worktree HEAD vs. main HEAD**: the agent worktree always runs ahead of `main`. The hook reads from the worktree's git directory, not the repo-root's. State file is per-task-id, not per-worktree.
- **No changes since last test run**: PASS — freshness only fails on *staleness relative to source mutations*, not chronological age.
- **CI pre-merge re-run**: orthogonal to this hook. CI runs are separate from local pipeline verification evidence; the PR-creation gate already integrates CI status separately.
- **`isolation: "worktree"` race**: if two parallel build-engineer subagents share a state file path, race is possible. Mitigation: state file is task-id-scoped, not slice-scoped. Use file locks (`flock`) on write — implementation detail for the spawn.
- **`fix-engineer` re-dispatch in code-review loop**: every fix-engineer Edit invalidates the state file. The hook will block the next patch-critic until `/verify` re-runs. This is the intended behaviour — fix-engineer rounds are the most common source of stale-evidence completion claims.

## Cost

- Hook execution time: < 50ms (single file read + git command). Negligible against subagent spawn cost.
- New state file write per `/verify` run: < 1KB. Negligible.
- Failure recovery: if Verify must re-run because the freshness guard blocked patch-critic, the cost is one extra `/verify` spawn (~10–15% of a pipeline's total cost). This is **a feature, not a bug**: the alternative is shipping code that doesn't work and re-doing the entire pipeline.

## Implementation Checklist

1. **`hooks/verification-freshness-guard.sh`** (new) — 60–80 LOC bash script following the Path-B advisory pattern from `hooks/pre-agent-thinking.sh`. Reads `pipeline-state/{task-id}/verification-evidence.json`, compares to worktree HEAD, emits JSONL.
2. **`hooks/_lib/state_paths.sh`** — add `_state_verification_evidence_path` helper.
3. **`settings.json`** — register the hook on PreToolUse with `matcher: "Agent"`, position 7 (after `instinct-injector` at position 6).
4. **`skills/verify/SKILL.md`** — add Step Final to write the state file. Schema versioned.
5. **`skills/patch-critique/SKILL.md`**, **`skills/pr-creation/SKILL.md`**, **`skills/product-acceptance/SKILL.md`** — update input contracts.
6. **`agents/patch-critic.md`** — replace honor-system prose with reference to the hook.
7. **`tests/test_freshness_guard.py`** (new) — 5+ unit tests covering: state file missing, git_head mismatch, hard staleness, soft staleness, fresh.
8. **`rules/core.md` Iron Law 2** — append parenthetical: "(Enforcement: `hooks/verification-freshness-guard.sh`, log-only at v2.1.140, blocks once `permissionDecision` ships on Agent matcher.)"
9. **`/forensics`** — add a check for `freshness-guard.jsonl` records with `verdict="WOULD_BLOCK"` and `source="path-b-advisory"`. These are the cases where a pipeline almost-shipped on stale evidence and the team needs to see them.
10. **One observation post-rollout** — `eval/baselines/{latest}-freshness-baseline.md` capturing pre/post staleness-block frequency. Target: any non-zero count is a win (each block is a stale-evidence ship that didn't happen).

## Counter-arguments considered

- **"Iron Laws are honored by all agents; mechanical enforcement is overkill."** Empirically false in this codebase. The audit found explicit prose telling agents to push back on staleness; no measurement of whether they actually do. Pure honor systems fail proportional to load. Mechanical enforcement is cheap.
- **"This will false-positive on git operations that don't change source (e.g. amended commit messages, .gitignore tweaks)."** Possible. Mitigation: the `git_head` mismatch rule is strict but the staleness rule uses `git log -1 --format=%ct` on the worktree HEAD, which only changes on commit. Amended commits DO change `git_head` — but they also change semantics, so re-running tests is correct policy.
- **"The state-file approach couples Verify and Patch-Critic via filesystem state. Why not pass test output directly?"** Direct passing exists today and is the failure mode this proposal closes. Filesystem state is the verifiable handoff; the alternative requires the orchestrator to never make a mistake about which test output is current. Decoupling-via-state is the standard pattern.
- **"This is the kind of governance that bureaucratizes the pipeline."** Considered. The hook adds < 50ms per spawn, blocks zero spawns until proven necessary (Path-B), and the only "bureaucracy" it adds is "the pipeline does what it says it does." Iron Law 2 already exists; this proposal just makes it true.

## Rollback

Remove the hook from `settings.json`, delete `verification-freshness-guard.sh`, revert the SKILL.md edits. The state file becomes unused but harmless.

---

**Linked PR for the freshness-hook track:** none yet — this proposal precedes implementation. Once approved, dispatch `/pipeline` with prompt: "Implement protocols/_proposals/2026-05-14-iron-law-2-freshness-hook.md exactly as specified. Budget: 7. Critical: true (this closes a production-correctness gap)."
