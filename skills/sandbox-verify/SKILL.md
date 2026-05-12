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
- BEFORE the inline code-review step (Step 5 of `/build-implementation`) — a code-reviewer should never APPROVE a build that fails sandbox-verify.
- **Do NOT use when**: the project has no test command in `CLAUDE.md` Commands (no signal to compare). The skill emits `SANDBOX_SKIPPED` in that case downstream of Story 2.

## Inputs

- **Pipeline state**: `pipeline-state/{task-id}/build.md` containing the worktree's local test verdict.
- **External**: `E2B_API_KEY` environment variable (if missing → `SANDBOX_SKIPPED(no-e2b-token)`); `CLAUDE_SESSION_ID` for skip-log path resolution.
- **Worktree**: the build engineer's worktree path (read-only).
- **Project**: `CLAUDE.md` Commands section for the test command (Story 2).

## Procedure

> **Story-1 scope:** Steps 1, 2 (no-token branch only), and 5 are implemented. Steps 3-4 are stubs that downstream stories will fill in. The contract surface is exercisable today via the no-E2B-token branch and the pure-function diff algorithm at `hooks/_lib/sandbox_verify_diff.py`.

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
- Returns `{"verdict": "SANDBOX_SKIPPED", "reason": "no-e2b-token", "timestamp": "<ISO-8601>"}`.
- Appends one JSON line to `{metrics_dir}/{session_id}/sandbox-verify-skips.jsonl` using `os.open(path, O_WRONLY|O_CREAT|O_APPEND)` + `os.write` (NEVER `>>` from shell — the `bash-write-guard` hook blocks that).
- Emit verdict and EXIT — no sandbox provisioning is attempted.

### Step 2: Provision E2B sandbox (Story 3)

**Story-1 stub** — `E2B_API_KEY` is set but the provisioning helper does not yet exist. Story 1 emits a placeholder verdict and exits; Story 3 will wire in the actual HTTP/SDK provisioning, cost cap, and retry-once-then-skip logic per the workstream default.

When Story 3 lands, this step:
1. Provisions a fresh E2B sandbox via the E2B HTTP API (using `E2B_API_KEY`).
2. Clones the worktree into the sandbox.
3. On provision failure (network, quota, API error), emits `SANDBOX_SKIPPED(e2b-provision-failed)` after one retry.
4. On cost-cap breach, emits `SANDBOX_SKIPPED(cost-cap-exceeded)`.

### Step 3: Discover the test runner (Story 2)

**Story-1 stub** — `hooks/_lib/sandbox_verify_diff.py:parse_test_outcomes(output, runner='pytest')` returns an empty dict today. Story 2 will:

1. Read `CLAUDE.md` Commands section for the project's canonical test command.
2. Match against the test-runner enumeration (`pytest`, `npm test`, `bundle exec rspec`, `cargo test`, `go test`, …).
3. Choose the per-language parser from `parse_test_outcomes(output, runner)`.

If no runner discovered → `SANDBOX_SKIPPED(no-test-runner-discoverable)` (Story 2 adds to enum).

### Step 4: Run tests in both environments and parse outcomes (Story 2)

**Story-1 stub.** Story 2 will:

1. Run the test command in the worktree → capture output → `parse_test_outcomes(output, runner)` → `dict[str, "pass"|"fail"]`.
2. Run the same command in the E2B sandbox → capture output → parse → `dict[str, "pass"|"fail"]`.
3. Pass both dicts to `compare_pass_sets(worktree, sandbox)` (pure function, lives in `hooks/_lib/sandbox_verify_diff.py`).

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
- no-e2b-token | e2b-provision-failed | cost-cap-exceeded

## Next Phase Input
On VERIFIED: Build emits BUILD_COMPLETE. On FAILED: fix-engineer dispatched with diverging tests. On SKIPPED: Build advances; reason captured for forensics.
```

## Verdict

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `SANDBOX_VERIFIED` | Worktree pass set equals sandbox pass set. | Build advances to inline code-review step. |
| `SANDBOX_FAILED` | Pass sets diverge; `diverging_tests` enumerated. | Spawn fix-engineer per `rules/_detail/pipeline-protocol.md` § In-Cycle Fix Rule. |
| `SANDBOX_SKIPPED` | Sandbox unavailable; reason ∈ Story-1 enum `{no-e2b-token}` (Story 3 extends). | Build advances; skip line logged for forensics. |

The skill emits exactly one verdict per invocation.

## Anti-Patterns

- **Retrying the sandbox until pass sets match** — divergence IS the signal. Convergence-via-retry hides the bug the gate exists to find.
- **Treating `SANDBOX_SKIPPED` as failure** — SKIP is informational (`info` polarity in catalog). CI environments without sandbox credentials are first-class; the build advances.
- **Using `echo ... >> sandbox-verify-skips.jsonl`** — bash-write-guard blocks `>>` to `.jsonl`. Use the Python `os.open` pattern in `emit_skip_if_no_token` or `jq -c '...' >> file`.
- **Editing the worktree to make the sandbox green** — the agent's `tools:` allowlist excludes Write/Edit/MultiEdit for exactly this reason.

## Tests

Skill-level tests live at `tests/test_sandbox_verify.py`, `tests/test_sandbox_verify_catalog.py`, `tests/test_sandbox_verify_diff.py`. The skill's tests directory (`skills/sandbox-verify/tests/`) is reserved for future skill-specific fixtures; the harness-audit `tests/` directory check is satisfied by a `.gitkeep`.
