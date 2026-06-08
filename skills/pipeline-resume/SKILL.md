---
name: "pipeline-resume"
description: "Use when user wants to Resume an in-progress pipeline from pipeline-state/ files. Validates state schema, determines current phase, and re-enters the pipeline at the correct point."
argument-hint: "Optional: task ID to resume (auto-detects if only one active pipeline)"
---

# Pipeline Resume

## What This Skill Does

Detects and resumes in-progress pipelines from structured state files in `pipeline-state/`. Handles the case where a pipeline was interrupted by context compaction, session end, or agent failure.

## When to Invoke

- At session start when `pipeline-state/` contains active state files
- When user asks to continue previous work
- When the SessionStart hook detects in-progress pipelines

## Process

### Step 0: Arm the intake-backstop marker (resume is a legitimate "intake ran" event)

The intake-backstop gate (`hooks/intake-backstop.sh`) blocks orchestrator work
when no per-session intake marker exists. Resuming an interrupted pipeline is a
legitimate continuation that did NOT run `/harness:intake` in THIS session, so it must
arm the marker itself — otherwise the first work-bash or specialized-agent
spawn after resume is BLOCKED. The earlier global "any in_progress pipeline
satisfies the gate" shortcut was REMOVED (it let one orphaned dead-session
pipeline disable the gate for everyone — see `hooks/intake-backstop.sh` header
and AC-12), so the marker is the only signal.

Run this BEFORE any other resume work (idempotent; SID derivation matches the
hook reader exactly):

```bash
HARNESS_DATA="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
SID_RAW="${CLAUDE_SESSION_ID:-local-$$}"; SID="${SID_RAW//[^A-Za-z0-9_-]/}"
[[ -z "$SID" ]] && SID="local-$$"
mkdir -p "$HARNESS_DATA/intake-markers" && touch "$HARNESS_DATA/intake-markers/$SID.marker"
```

If `CLAUDE_SESSION_ID` is not injected for the shell event that runs this step,
the marker SID may not match the backstop reader's SID; the failure mode is an
OVER-block (recoverable via `CLAUDE_INTAKE_BACKSTOP=off` for the session), never
an under-block.

### Step 1: Scan for Active Pipelines

The DUAL_PATH soak (see `protocols/pipeline-protocol.md` § Structured Pipeline State) means readers MUST tolerate both the new per-task-subdir layout (`$state_dir/{task-id}/pipeline.md`, bare path: `pipeline-state/{task-id}/pipeline.md`) and the legacy flat form (`$state_dir/{task-id}-pipeline.md`). Use the canonical four-glob discovery sequence (encapsulated in `_psp_find_active_pipelines` from `hooks/_lib/pipeline-state-paths.sh`):

```bash
# Resolve primary state root (HARNESS_DATA, new writes land here)
HARNESS_DATA="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
# 1. New layout, root
find "${HARNESS_DATA}/pipeline-state" -maxdepth 2 -mindepth 2 -name "pipeline.md" \
  -not -path "*/workstreams/*" -not -path "*/health-reports/*"
# 2. New layout, workstream
find "${HARNESS_DATA}/pipeline-state/workstreams" -maxdepth 3 -mindepth 3 -name "pipeline.md"
# 3. Legacy layout, root
find "${HARNESS_DATA}/pipeline-state" -maxdepth 1 -name "*-pipeline.md"
# 4. Legacy layout, workstream
find "${HARNESS_DATA}/pipeline-state/workstreams" -maxdepth 2 -name "*-pipeline.md"
# REPO_ROOT/pipeline-state (legacy read-only soak fallback — remove after 90 days from
# merge of relocate-pipeline-state-writes PR: git log --format=%aI -1 <merge-commit>)
find "${REPO_ROOT}/pipeline-state" -maxdepth 2 -mindepth 2 -name "pipeline.md" \
  -not -path "*/workstreams/*" -not -path "*/health-reports/*" 2>/dev/null
find "${REPO_ROOT}/pipeline-state" -maxdepth 1 -name "*-pipeline.md" 2>/dev/null
```

Dedup the union by `task_id` with **workstream-wins precedence**; tie-break by mtime (fresher wins; ties favour the new layout). The shorthand glob `pipeline-state/*/pipeline.md` matches the new-layout root form — combine with the other three for full coverage.

During the 90-day soak the open-coded dual-scan above REPLACES the helper call (`_psp_find_active_pipelines` scans HARNESS_DATA only); at soak-end remove the REPO_ROOT block and revert to calling the helper directly.

Also scan for debug state and discussion files (DUAL_PATH — same dedup
rules as above; same `health-reports/` exclusion):
```bash
# Resolve state root (HARNESS_DATA)
HARNESS_DATA="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
# New layout (root + workstream-nested)
find "${HARNESS_DATA}/pipeline-state" \( -name "debug.md" -o -name "discussion.md" \) \
  -not -path "*/health-reports/*" 2>/dev/null
# Legacy layout
ls "${HARNESS_DATA}/pipeline-state"/*-debug.md 2>/dev/null
ls "${HARNESS_DATA}/pipeline-state"/*-discussion.md 2>/dev/null
ls "${HARNESS_DATA}/pipeline-state"/workstreams/*/*-debug.md 2>/dev/null
ls "${HARNESS_DATA}/pipeline-state"/workstreams/*/*-discussion.md 2>/dev/null
```

Also scan workstream metadata:
```bash
ls "${HARNESS_DATA}/pipeline-state/workstreams"/*/workstream.md 2>/dev/null
```

Display results grouped:
```
Active workstreams:
  auth/ — 1 active pipeline (login-page, phase: review)
  payments/ — 0 active pipelines

Ungrouped pipelines:
  hotfix-nav — phase: build

Active debug sessions:
  task-123 — 3 hypotheses, 2 fix attempts
```

If multiple active pipelines found, list them and ask user which to resume.
If one found, resume automatically.
If none found, report "No active pipelines" and exit.

### Step 2: Validate State File Schema

Read the pipeline state file and verify required frontmatter fields:

```yaml
---
task_id: [required — string]
phase: [required — build|review|verify|test|accept|ship]
verdict: [required — in_progress|completed|failed]
timestamp: [required — ISO 8601]
---
```

Also verify the body contains:
- Pipeline name/description
- Scale classification (micro/small/medium/large)
- Branch name
- Phase status list (which phases completed, which pending)
- Key files list (what was created/modified)

If any required field is missing, warn and ask user to confirm the state is valid or start fresh.

### Step 3: Determine Resume Point

Read the phase status list from the state file:

```
- Build: completed
- Review: completed (both APPROVE)
- Verify: in_progress  ← resume here
- Test: pending
- Accept: pending
- Ship: pending
```

The resume point is the first phase that is `in_progress` or `pending` after all `completed` phases.

### Step 4: Verify Branch and Working Tree

```bash
# Verify we're on the correct branch
git branch --show-current

# Check for uncommitted changes
git status --porcelain

# Verify last commit matches expectations
git log --oneline -3
```

If the branch doesn't match the state file, warn the user.
If there are uncommitted changes, warn before proceeding.

### Step 5: Re-Enter Pipeline

Update the state file to mark the resume:
```yaml
timestamp: [current ISO 8601]
resumed_at: [current ISO 8601]
resumed_from: [phase name]
```

Then invoke `/harness:pipeline` with context:
- Current phase to resume from
- Prior phase verdicts and artifacts
- Key files from previous phases
- Branch name

The pipeline continues from the resume point, skipping completed phases.

## Phase Output

```
Verdict: RESUMED / NO_ACTIVE_PIPELINE / STATE_INVALID
Next: Continue pipeline from [phase name]
Artifacts: [state file path, resume point, prior phase verdicts]
```
$ARGUMENTS
