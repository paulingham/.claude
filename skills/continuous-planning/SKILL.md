---
name: continuous-planning
description: Long-lived planning agent that watches pipeline scratchpad findings during multi-slice Build and refines the active plan when findings contradict it. Spawned when slice_count >= 2.
context: persistent
agent: planning-agent
argument-hint: "task_id=<id> plan_path=<path> scratchpad_dir=<dir> team_roster=<name1,name2,...> [poll_seconds=60]"
---

# Continuous Planning

## What This Skill Does

Drives a long-lived advisory `planning-agent` that polls the pipeline scratchpad
during multi-slice Build, compares each new finding against the active plan, and
**refines the plan** when a finding contradicts a stated assumption. The skill is
read by the planning-agent on spawn; it is the agent's operating manual.

The planning-agent is **advisory**: it never blocks Build engineers, never owns
the build queue, never writes implementation code. It only edits the plan file.

## When Invoked

Spawned when `should_spawn_planning_agent(slice_count, dispatch_mode, phase)`
returns True. The function returns True iff:

- `slice_count >= 2`, AND
- `dispatch_mode != "best-of-n"`, AND
- `phase != "fix"`

Never spawned on single-slice, Best-of-N, or fix-phase Builds. Single-slice has
no inter-slice feedback to refine. Best-of-N candidates compete against the same
plan and refining mid-competition would invalidate the comparison. Fix-engineer
addresses review findings on a frozen diff — the plan is no longer the source
of truth.

## Spawn Parameters

The orchestrator injects the following into the planning-agent's prompt header:

```
TaskId: {task-id}
PlanPath: pipeline-state/{task-id}-plan.md
ScratchpadDir: pipeline-state/{task-id}-scratchpad/
TeamRoster: name1,name2,name3
PollSeconds: 60   # default; overridable via CLAUDE_PLANNING_POLL_SECONDS
```

`PollSeconds` defaults to 60. The orchestrator may override via
`CLAUDE_PLANNING_POLL_SECONDS` env var (passed through the spawn shell).

## Contradiction Rubric (MANDATORY)

These are the **only** trigger categories. Do not flag contradictions
speculatively. Append a Plan Update only when the rubric is unambiguously
satisfied.

| Category | Triggers? | Condition |
|---|---|---|
| fragility | Yes | Names a file/function the plan calls safe to modify |
| warning | Yes | Identifies a hazard adjacent to a planned change |
| decision | Yes | Contradicts an explicit plan directive |
| discovery | Conditional | Only if it invalidates a stated plan precondition |
| pattern | No | Patterns are validations, never contradictions |

**Read literally**: a finding that says "the auth module is fragile" only
contradicts the plan if the plan asserts the auth module is safe to modify.
A general observation is not a contradiction.

## Poll Loop Procedure

1. Read spawn parameters from the prompt header.
2. Initialize the cursor file at `pipeline-state/{task-id}-planning-cursor.json`
   (a JSON list of `{filename, content_hash}`). The cursor persists across
   poll cycles and survives context compaction.
3. Loop until `shutdown_request` SendMessage received:
   1. Call `hooks/_lib/scratchpad_diff.py::peek_new_findings(scratchpad_dir, cursor_path)`
      to get findings whose `(filename, content_hash)` pair is not yet in the
      cursor. **`peek` does NOT advance the cursor** — if this poll cycle
      crashes before the plan Edit completes, the findings are re-surfaced on
      the next poll.
   2. For each new finding, apply the Contradiction Rubric.
   3. On contradiction: append a `## Plan Update — {ISO 8601 timestamp}`
      section to `pipeline-state/{task-id}-plan.md` (Edit tool only — the
      `planning-agent-edit-scope.sh` PreToolUse hook enforces this scope).
   4. Broadcast a `plan_update` SendMessage to every teammate in TeamRoster.
   5. **Only after** the Edit and broadcast succeed, call
      `commit_findings(findings, cursor_path)` to mark them seen. This
      ordering guarantees no finding is silently lost.
   6. Wait `PollSeconds` seconds, OR act immediately if a `plan_update_request`
      SendMessage is received from a teammate.
4. On `shutdown_request`: complete the current poll cycle (do not abandon a
   mid-cycle scan), then emit the final verdict.

## Plan Update Format

Append-only to the plan file. Never edit prior sections.

```markdown
## Plan Update — {ISO 8601 timestamp}
**Source:** {scratchpad finding filename}
**Category:** {fragility|warning|decision|discovery}
**Invalidated assumption:** {one-line excerpt from plan body that is now wrong or risky}
**Updated guidance:** {1-3 sentences}
**Affected slices:** {comma-separated slice names}
```

## Broadcast Format

`SendMessage` to each teammate in TeamRoster:

```json
{
  "type": "plan_update",
  "task_id": "{task-id}",
  "plan_path": "pipeline-state/{task-id}-plan.md",
  "update_section_anchor": "Plan Update — {ISO timestamp}",
  "ts": "{ISO timestamp}"
}
```

## Termination Semantics

- On `shutdown_request`: finish the current poll cycle, then emit verdict.
- Verdict: **`PLAN_REFINED`** if at least one Plan Update was appended;
  **`PLAN_UNCHANGED`** if zero.
- Always emit one of the two verdicts before exiting.

## Failure Modes

All acceptable — the planning-agent is advisory. None of these halt Build.

| Failure | Behavior |
|---|---|
| Turn budget (200 turns) exhausted mid-Build | Planning silently stops. Build continues from last plan state. |
| Scratchpad directory missing or deleted | `scratchpad_diff` returns []; log and continue polling. |
| `plan_update` SendMessage to a teammate fails | Log; continue. The pull-model fallback (teammates re-read the plan at slice start) ensures visibility. |
| Edit tool blocked by `planning-agent-edit-scope.sh` | Means the planning-agent attempted to edit a non-plan file (a bug). Log, continue without editing. |

## Idempotency

Each finding is tracked by `(filename, content_hash)`. The same finding is
never processed twice, even if the file's mtime changes. The cursor
persists across poll cycles via the cursor file.

## Never Blocks Build

Build engineers proceed regardless of this agent's state. The orchestrator
never gates Build progress on a planning-agent verdict. If the planning-agent
errors or hits its turn limit, downstream slices simply read the last-known
plan state and continue.
