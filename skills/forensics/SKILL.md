---
name: "forensics"
description: "Use when user wants to Post-incident investigation of pipeline runs. Reconstructs timelines from trajectory JSONL, analyzes anomalies (gaps, retries, long phases), and produces structured findings. Use after pipeline failures, unexpected rework, or to understand what went wrong."
argument-hint: "Task ID of the pipeline to investigate"
---

# Forensics

## What This Skill Does

Post-incident investigation of pipeline runs. Reconstructs timelines, detects anomalies, verifies artifact integrity, and produces a structured findings report. Evidence-based alternative to memory-based recollection.

## When to Invoke

- After a pipeline fails or requires >2 review rounds
- When reflection identifies issues but root cause is unclear
- When the user asks "what went wrong?"
- Automatically invoked by `/harness:pipeline` Step 7 (Reflect) when failures occurred

## Process

### Step 1: Gather Evidence

```bash
# Trajectory file (agent events timeline) — new layout, with legacy fallback during 90-day DUAL_PATH soak
cat ~/.claude/$state_dir/{task-id}/trajectory.jsonl 2>/dev/null \
  || cat ~/.claude/$state_dir/{task-id}-trajectory.jsonl 2>/dev/null

# Pipeline state file
cat ~/.claude/$state_dir/{task-id}/pipeline.md 2>/dev/null \
  || cat ~/.claude/$state_dir/{task-id}-pipeline.md 2>/dev/null

# Debug state (if debugging loop was entered)
cat ~/.claude/$state_dir/{task-id}/debug.md 2>/dev/null \
  || cat ~/.claude/$state_dir/{task-id}-debug.md 2>/dev/null

# Git history during the pipeline
git log --oneline --since="{pipeline start}" --until="{pipeline end or now}"

# Diff summary
git diff --stat {start-commit}..HEAD
```

If trajectory JSONL is missing, reconstruct from pipeline state file and git log.

### Step 2: Timeline Reconstruction

Parse the trajectory JSONL (one JSON object per line) and build a timeline:

```markdown
### Timeline
| Time | Agent | Event | Duration | Notes |
|------|-------|-------|----------|-------|
| T+0m | software-engineer | agent_stopped | 12m | Build phase |
| T+12m | code-reviewer | agent_stopped | 4m | Review phase |
| T+16m | security-engineer | agent_stopped | 3m | Review phase |
| T+19m | — | gap | 7m | Possible compaction? |
| T+26m | software-engineer | agent_stopped | 8m | Fix for review findings |
```

Compute: total pipeline duration, per-phase duration, gap time.

### Step 3: Anomaly Detection

Flag any of the following:

| Anomaly | Detection Method | Significance |
|---------|-----------------|-------------|
| Long phase | Duration >2x median for that phase type | Possible complexity or rework |
| Retry | Same agent type spawned >1x in same phase | Fix cycle or failure |
| Timeline gap | >5 minutes between events | Context compaction or stall |
| Orphan agent | Agent in trajectory without matching task | Cleanup failure |
| Discipline violation | Files modified outside agent sessions | Orchestrator wrote code |
| Stale state | Pipeline state timestamp >24h old | Abandoned pipeline |

### Step 3a: Sandbox-Verify Divergence Detection

When the pipeline state contains a `build.md` file with a `## Sandbox Verify` section whose verdict is `SANDBOX_FAILED`, surface the diverging test names AND join them against scratchpad findings categorised as `fragility` whose summary text mentions the test name.

```python
import sys
sys.path.insert(0, f"{os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')}/hooks/_lib")
from sandbox_verify_observation import diverging_tests_from_build_md
from pathlib import Path

build_md_path = Path(os.environ.get('CLAUDE_PLUGIN_DATA') or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')) / f"$state_dir/{task_id}/build.md"
if build_md_path.is_file():
    diverging = diverging_tests_from_build_md(build_md_path.read_text())
    if diverging:
        # Render under Anomalies; join against scratchpad fragility findings.
        for test_name in diverging:
            print(f"- diverged: {test_name}")
```

Render in the forensic report under Anomalies as a `## Sandbox Divergence` block:

```markdown
### Sandbox Divergence (verdict: SANDBOX_FAILED)

| Test | Joined scratchpad finding |
|---|---|
| `tests/test_x.py::test_a` | `fragility: timing-sensitive payment fixture` |
| `tests/test_y.py::test_b` | (no scratchpad finding) |
```

The join key is substring match: a scratchpad finding's summary that contains the test name (or a 5+ character substring of it) attaches to the row. Unmatched divergences are still listed — the verdict + test name alone is forensically valuable.

When no `## Sandbox Verify` section exists OR the verdict is `SANDBOX_VERIFIED` / `SANDBOX_SKIPPED`, the helper returns `[]` and this sub-step renders nothing — silent skip, never an empty header.

### Step 3b: Hook Protection Lookup

When a hook violation is detected in `metrics/$SID/*-violations.jsonl`, look up the hook's protection annotations:

```bash
# For each violation record with a hook_name field, extract:
grep -E '^# (enforces|protects):' ~/.claude/hooks/{hook_name}.sh 2>/dev/null
```

Render in the forensic report as a "Rule Protected" annotation under the relevant anomaly:

> **This violation by `{hook-name}` protects:**
> - **Rule**: `{value from # enforces:}`
> - **Skills**: `{value from # protects:}`

Update the **Anomalies table** schema to include a `Rule Protected` column:

```markdown
| # | Type | Description | Root Cause | Rule Protected |
|---|------|------------|------------|----------------|
| 1 | Main-branch violation | Bare `git checkout` detected | Agent omitted `git -C` delegation | `protocols/agent-protocol.md:Main-Branch Invariant` (build-implementation, pr-creation) |
```

This traceability lets forensics readers immediately see which rule and which skill the hook was guarding when it fired — eliminating the "what does this hook protect?" question.

### Step 3b.1: Verification Freshness Drift

Iron Law 2 enforcement (mechanical at v2.1.141 via `hooks/verification-freshness-guard.sh`) emits one JSONL line per gated Agent spawn to `metrics/{session}/freshness-guard.jsonl`. Surface every `would_block` record:

```bash
# Pull the path-b-advisory would_block records — these are the spawns that
# WOULD have been blocked once permissionDecision ships on Agent matcher.
jq -c 'select(.resolved.action == "would_block" and .source == "path-b-advisory")' \
  ~/.claude/metrics/{session-id}/freshness-guard.jsonl 2>/dev/null
```

Render in the Anomalies table with `Rule Protected: rules/core.md:Iron Law 2`:

```markdown
| # | Type | Description | Root Cause | Rule Protected |
|---|------|------------|------------|----------------|
| N | Stale verification evidence | `freshness-guard` logged `would_block`/`{reason}` on `{agent_role}` spawn | See § Operator Copy in proposal | `rules/core.md:Iron Law 2` (verify, patch-critique, pr-creation, product-acceptance) |
```

Recurring `no_worktree_resolvable` records are an orchestrator-side dispatch-env drift — operators should check `orchestrator/agent-orchestration.md § Worktree Env Propagation` for the load-bearing contract and verify `$CLAUDE_WORKTREE_PATH` is set on every Build-onward Agent dispatch.

### Step 3c: Tool Output Size Warnings

Auto-compact thrash precursor: a single tool result returning enough tokens to push the buffer past compaction threshold. The `tool-output-bytes.sh` PostToolUse hook records `char_count` and `estimated_tokens` per call, so this regression class is detectable in forensics.

```bash
# Top-N largest tool outputs (descending) for the session
jq -s 'sort_by(-.estimated_tokens) | .[:10]' \
  ~/.claude/metrics/{session-id}/tool-output-bytes.jsonl 2>/dev/null

# All threshold breaches (estimated_tokens > 20000)
jq -c 'select(.estimated_tokens > 20000)' \
  ~/.claude/metrics/{session-id}/tool-output-bytes.jsonl 2>/dev/null
```

If breaches exist, render in the forensic report under Anomalies:

```markdown
| # | Type | Description | Root Cause | Rule Protected |
|---|------|------------|------------|----------------|
| N | Large tool output | `Bash` returned 95k chars (~23750 tokens) at T+12m | Unscoped log fetch — needs `head`/`tail` | `tool-output-bytes.sh` (forensics) |
```

Cross-reference the `ts` of the largest outputs against timeline gaps from Step 2 — a >20k-token output immediately before a gap is a strong compaction signal.

### Step 4: Artifact Integrity

Cross-reference pipeline state with git:

1. Are all files listed in pipeline state actually committed?
2. Does `git log` match the expected phase order?
3. Are there commits not accounted for in the pipeline state?
4. Do branch names follow the expected convention?

### Step 5: Root Cause Analysis

For each anomaly, propose a cause:
- "Phase X took 15 minutes because review found 3 findings requiring 2 fix cycles"
- "Gap at T+23m — context compaction occurred (PreCompact hook fired)"
- "Orphan agent — pipeline was interrupted before cleanup"

### Step 6: Produce Findings

Write `$state_dir/{task-id}/forensics.md`:

```markdown
---
task_id: {task-id}
phase: forensics
verdict: {CLEAN / ANOMALIES_FOUND / INVESTIGATION_INCOMPLETE}
timestamp: {ISO 8601}
---

## Forensics: {task-id}

### Summary
{1-3 sentence overview of findings}

### Timeline
| Time | Agent | Event | Duration | Notes |
|------|-------|-------|----------|-------|

### Metrics
- Total duration: {Xm}
- Phase durations: Build {Xm}, Review {Xm}, Verify {Xm}, ...
- Review rounds: {N}
- Fix cycles: {N}
- Timeline gaps: {N} ({total gap time})

### Anomalies
| # | Type | Description | Root Cause |
|---|------|------------|------------|

### Artifact Integrity
- Pipeline state consistent with git: {yes/no}
- Files in state: {N}, Files in git: {M}
- Unaccounted commits: {list or none}

### Recommendations
- {recommendation 1}
- {recommendation 2}
```

## Phase Output

```
Verdict: CLEAN / ANOMALIES_FOUND / INVESTIGATION_INCOMPLETE
Next: Feed findings into /harness:pipeline Step 7 (Reflect)
Artifacts: $state_dir/{task-id}/forensics.md
```
$ARGUMENTS
