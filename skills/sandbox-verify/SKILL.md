---
name: "sandbox-verify"
description: "Build-phase gate that runs the project's test suite in a remote sandbox (E2B) and compares per-test pass sets against the worktree. Emits SANDBOX_VERIFIED when pass sets match, SANDBOX_FAILED when they diverge with diverging test names enumerated, and SANDBOX_SKIPPED when the sandbox is unavailable (no E2B token, cost cap exceeded, provisioning failure). Inspired by SolidCoder's sandbox-vs-local execution divergence detection."
verdict: SANDBOX_VERIFIED|SANDBOX_FAILED|SANDBOX_SKIPPED
phase: build
dispatch: subagent
agent: sandbox-verify-engineer
---

# Sandbox Verify

## What This Skill Does

Adds a Build-phase gate that runs the project's test suite in a remote sandbox (E2B) alongside the local worktree run, then compares **per-test pass sets** by name. Identical pass sets → `SANDBOX_VERIFIED`. Divergent pass sets → `SANDBOX_FAILED` with the diverging test names enumerated. Sandbox unavailable (no E2B token in env, cost cap exceeded, provision timeout) → `SANDBOX_SKIPPED` with the reason logged.

Story 1 (this slice) mints the skill + agent contract, the three verdicts in the catalog, and the pure-function diff algorithm. Story 2 wires in test-runner discovery and per-language output parsing. Story 3 wires in the E2B HTTP/SDK provisioning and the cost cap. Story 4 wires in forensics and observation-emit.

## When to Invoke

- Build phase, after the worktree's local test suite passes — sandbox-verify is a *cross-check* of that green, not a substitute for it.
- After Step 1d (Property-Based Tests) and Step 2b (Adversarial Tests) have run — the sandbox runs the full union suite.
- BEFORE the inline code-review step (Step 5 of `/harness:build-implementation`) — a code-reviewer should never APPROVE a build that fails sandbox-verify.
- **Do NOT use when**: the project has no test command in `CLAUDE.md` Commands (no signal to compare). The skill emits `SANDBOX_SKIPPED` in that case downstream of Story 2.

## Inputs

- **Pipeline state**: `pipeline-state/{task-id}/build.md` containing the worktree's local test verdict.
- **External**: `E2B_API_KEY` environment variable (if missing → `SANDBOX_SKIPPED(no-e2b-token)`); `CLAUDE_SESSION_ID` for skip-log path resolution.
- **Worktree**: the build engineer's worktree path (read-only).
- **Project**: `CLAUDE.md` Commands section for the test command (Story 2).

## Procedure

> **Story-3 scope:** Steps 1-5 are now end-to-end live. Story 4 carryforward: skip-rate forensics, observation schema enrichment, per-language parsers beyond pytest, cost-cap dollar calibration. The contract surface is exercisable today via either the no-token branch (`emit_skip_if_no_token`) or the token-present `provision_and_run` orchestrator.

### Step 1: Pre-flight — check for `E2B_API_KEY`

If the env var `E2B_API_KEY` is unset OR empty:

```bash
python3 -c "
import os
from sandbox_verify_skip import emit_skip_if_no_token
result = emit_skip_if_no_token(
    session_id=os.environ.get('CLAUDE_SESSION_ID', 'local'),
    metrics_dir=os.environ.get('CLAUDE_METRICS_DIR',
                               os.path.expanduser('~/.claude/metrics')))
print(result['verdict'])
"
```

The helper at `hooks/_lib/sandbox_verify_skip.py:emit_skip_if_no_token(session_id, metrics_dir)` does the work:
- Runs `session_id` through `_resolve_session_id` — canonical path-traversal regex `[A-Za-z0-9_.-]+`. Reject inputs fall back to `"local"` + stderr warning.
- Returns `{"verdict": "SANDBOX_SKIPPED", "reason": "no-e2b-token", "timestamp": "<ISO-8601>"}`.
- Appends one JSON line to `{metrics_dir}/{session_id}/sandbox-verify-skips.jsonl` using `os.open(path, O_WRONLY|O_CREAT|O_APPEND, 0o600)` + `os.write`. Mode 0o600 hardens the Story-1 security LOW; bash-write-guard blocks `>>` from shell.
- Emit verdict and EXIT — no sandbox provisioning is attempted.

### Step 2: Provision E2B sandbox via stdlib urllib

When `E2B_API_KEY` is present, the caller invokes `provision_and_run` from `hooks/_lib/sandbox_verify_skip.py`:

```python
from sandbox_verify_skip import provision_and_run
import sandbox_e2b_client as e2b
result = provision_and_run(
    session_id=session_id,
    metrics_dir=metrics_dir,
    test_command="pytest -v",
    worktree_outcomes=worktree_outcomes,
    e2b_client=e2b,
    secrets_allowlist=allowlist,  # from project CLAUDE.md ## Sandbox Secrets
)
```

`provision_and_run` orchestrates the full lifecycle:

1. **State-before-expensive-op tick** — writes a `starting` event to `metrics/{session-id}/sandbox-verify-cost.jsonl` BEFORE the first E2B HTTP call. This is the forensic breadcrumb that lets `/harness:forensics` detect leaked microVMs (a `starting` tick with no matching `teardown` line means the subagent was killed mid-run).
2. **Provision** via `sandbox_e2b_client.provision_microvm(template)` — pure stdlib `urllib.request`, hardcoded `_API_BASE = "https://api.e2b.dev"` SSRF guard, narrow exception catch on `(TimeoutError, urllib.error.URLError, E2BProvisionError)`. Retry-once-then-skip: first failure sleeps 2s and retries; second failure returns `{"ok": False, "reason": "e2b-unavailable", "attempts": 2}`.
3. **Provision failure** → `SANDBOX_SKIPPED` with the reason from the envelope (`no-e2b-token` or `e2b-unavailable`).

### Step 3: Forward only allowlisted env vars; run tests inside the microVM

Secrets policy is **default-deny**. `hooks/_lib/sandbox_secrets_allowlist.py:forward_env(allowlist)` returns ONLY the env vars whose names appear in the allowlist. Empty allowlist → empty dict (zero secrets forwarded). The allowlist is sourced by the caller from the project CLAUDE.md `## Sandbox Secrets` section (the schema is greenfield — no precedent existed before this story).

`sandbox_e2b_client.exec_in_microvm(microvm_id, command, env)` runs the test command inside the microVM with the forwarded env. The stdout is parsed by `sandbox_verify_diff.parse_test_outcomes(output, runner='pytest')` — a regex over pytest `-v` output mapping PASSED → `"pass"`, FAILED/ERROR → `"fail"`.

Cost-cap pre-check: before exec, `sandbox_cost_meter.tick(elapsed_seconds)` returns `{"soft_warn", "hard_trip", "elapsed_usd"}`. Past soft cap → `soft-cap-warn` event written to cost JSONL, run continues. Past hard cap → `hard-cap-trip` event written, exec aborted, `SANDBOX_FAILED` emitted with `reason: "cost-exceeded"`. Env-var overrides: `CLAUDE_SANDBOX_VERIFY_COST_CAP_SOFT_USD` (default 0.50) / `CLAUDE_SANDBOX_VERIFY_COST_CAP_HARD_USD` (default 2.00). Dollar values are placeholders pending Story 4 calibration from real spend data.

### Step 4: Compare pass sets and tear down

After exec, `sandbox_verify_diff.compare_pass_sets(worktree, sandbox)` runs the symmetric-difference algorithm. The verdict (`SANDBOX_VERIFIED` or `SANDBOX_FAILED`) is returned to the caller.

Teardown via `sandbox_e2b_client.destroy_microvm(microvm_id)` runs in a `try/finally` block — the call is guaranteed on EVERY exit path (happy comparison, parser raises, hard-cap trip). A `teardown` event is written to the cost JSONL after destroy. No leaked microVMs.

### Step 5: Emit verdict

The diff algorithm at `hooks/_lib/sandbox_verify_diff.py:compare_pass_sets()` is the source of truth for verdicts:

```python
from sandbox_verify_diff import compare_pass_sets
result = compare_pass_sets(worktree_outcomes, sandbox_outcomes)
# result == {"verdict": "SANDBOX_VERIFIED", "diverging_tests": []}
# OR        {"verdict": "SANDBOX_FAILED", "diverging_tests": ["t2", "t5"]}
```

The diff algorithm uses symmetric difference of pass sets:
- `worktree_passes = {t for t, v in worktree.items() if v == "pass"}`
- `sandbox_passes = {t for t, v in sandbox.items() if v == "pass"}`
- `diverging_tests = sorted(worktree_passes ^ sandbox_passes)`
- Empty diff → `SANDBOX_VERIFIED`; non-empty → `SANDBOX_FAILED`.

## Output

- **State file**: `pipeline-state/{task-id}/sandbox-verify.md` with the verdict in frontmatter.
- **Skip log**: `metrics/{session-id}/sandbox-verify-skips.jsonl` (only on `SANDBOX_SKIPPED`).
- **Scratchpad**: `pipeline-state/{task-id}/scratchpad/sandbox-verify-engineer-build.md` for any divergence diagnostics.

### Output File Format

```markdown
---
task_id: {task-id}
phase: build
verdict: SANDBOX_VERIFIED | SANDBOX_FAILED | SANDBOX_SKIPPED
timestamp: <ISO-8601>
---

## Summary
One-line outcome.

## Diverging Tests (SANDBOX_FAILED only)
- test_name_1
- test_name_2

## Skip Reason (SANDBOX_SKIPPED only)
- no-e2b-token | e2b-unavailable

## Failure Reason (SANDBOX_FAILED only — when not a pass-set divergence)
- cost-exceeded (cost-cap hard trip; teardown ran, microVM destroyed)

## Next Phase Input
On VERIFIED: Build emits BUILD_COMPLETE. On FAILED: fix-engineer dispatched with diverging tests. On SKIPPED: Build advances; reason captured for forensics.
```

## Verdict

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `SANDBOX_VERIFIED` | Worktree pass set equals sandbox pass set. | Build advances to inline code-review step. |
| `SANDBOX_FAILED` | Pass sets diverge; `diverging_tests` enumerated. | Spawn fix-engineer per `rules/_detail/pipeline-protocol.md` § In-Cycle Fix Rule. |
| `SANDBOX_SKIPPED` | Sandbox unavailable; reason ∈ `{no-e2b-token, e2b-unavailable}` (Story 3 extended the enum). | Build advances; skip line logged for forensics. |

The skill emits exactly one verdict per invocation.

## Anti-Patterns

- **Retrying the sandbox until pass sets match** — divergence IS the signal. Convergence-via-retry hides the bug the gate exists to find.
- **Treating `SANDBOX_SKIPPED` as failure** — SKIP is informational (`info` polarity in catalog). CI environments without sandbox credentials are first-class; the build advances.
- **Using `echo ... >> sandbox-verify-skips.jsonl`** — bash-write-guard blocks `>>` to `.jsonl`. Use the Python `os.open` pattern in `emit_skip_if_no_token` or `jq -c '...' >> file`.
- **Editing the worktree to make the sandbox green** — the agent's `tools:` allowlist excludes Write/Edit/MultiEdit for exactly this reason.

## Tests

Skill-level tests live at `tests/test_sandbox_verify.py`, `tests/test_sandbox_verify_catalog.py`, `tests/test_sandbox_verify_diff.py`. The skill's tests directory (`skills/sandbox-verify/tests/`) is reserved for future skill-specific fixtures; the harness-audit `tests/` directory check is satisfied by a `.gitkeep`.
