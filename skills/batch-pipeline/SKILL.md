---
name: batch-pipeline
description: Lightweight pipeline for pre-planned batch work (production readiness waves, bulk fixes). Preserves critical infrastructure (state, scratchpad, observations) while skipping redundant phases.
triggers:
  - "start wave"
  - "batch build"
  - "run all PRs"
  - "parallel implementation"
---

# Batch Pipeline Skill

## When to use

Use this instead of the full `/pipeline` when:
- Work is **pre-planned** (e.g., a Production Readiness Plan with defined PRs)
- The **Plan phase is already done** (architect output exists as a document)
- Multiple **independent tasks** run in parallel
- Each task is **self-contained** (no cross-task dependencies within the batch)

Do NOT use when:
- Work needs classification (use `/intake` instead)
- The plan hasn't been validated
- Tasks have complex dependencies requiring sequential execution

## Phases

```
State Init → Build (parallel) → Review (parallel) → Fix → Re-review → Ship → Reflect
```

Compared to full pipeline, this **skips**: Plan, Plan Validation, Final Gate (verify/test/accept).
It **preserves**: State tracking, scratchpad, session memory, observations, review.

## Procedure

### Step 1: State Initialisation

Before spawning any agents:

1. **Create pipeline state file**:
   ```
   Write pipeline-state/{batch-id}-pipeline.md with:
   ---
   task_id: {batch-id}
   phase: build
   verdict: pending
   timestamp: {ISO 8601}
   type: batch
   ---
   
   ## Batch: {description}
   
   ## Tasks
   | ID | Description | Phase | Verdict |
   |----|-------------|-------|---------|
   | {task-1} | ... | build | pending |
   | {task-2} | ... | build | pending |
   ```

2. **Create scratchpad directory**:
   ```bash
   mkdir -p pipeline-state/{batch-id}-scratchpad/
   ```

3. **Initialise session memory** (if not exists):
   ```bash
   source "$HOME/.claude/hooks/_lib/project-hash.sh"
   PROJECT_HASH=$(_project_hash)
   NOTES="$HOME/.claude/session-memory/$PROJECT_HASH/notes.md"
   if [[ ! -f "$NOTES" ]]; then
     mkdir -p "$(dirname "$NOTES")"
     cp ~/.claude/session-memory/config/template.md "$NOTES"
   fi
   ```

4. **Load instincts** (if any exist):
   ```bash
   ls ~/.claude/learning/instincts/global/*.md 2>/dev/null
   ls ~/.claude/learning/instincts/$PROJECT_HASH/*.md 2>/dev/null
   ```

### Step 2: Build (Parallel)

Spawn one write-capable agent per task, all in parallel:

- Each agent gets `isolation: "worktree"`
- Each agent prompt includes:
  - Task scope from the plan
  - Session memory content
  - Scratchpad findings from earlier agents (if any)
  - Instincts (if any exist)
  - Instruction to write scratchpad findings before completing
  - Reference to agent definition: "Read `~/.claude/agents/{role}.md`"

Update pipeline state as agents complete:
```
| {task-id} | ... | build | BUILD_COMPLETE |
```

### Step 3: Review (Parallel)

For each completed build, spawn code-reviewer + security-engineer:

- Both receive the **full diff** and **changed file list** in their prompt
- Both review independently, in parallel
- Update pipeline state with verdicts

### Step 4: Fix + Re-review

For tasks with CHANGES_REQUESTED:

1. Consolidate findings from both reviewers
2. Spawn fix agent (worktree isolation) with specific findings
3. After fix, spawn **targeted re-review** — only the raising reviewer, only the specific findings
4. Maximum 2 rounds. Escalate to user if unresolved.

### Step 5: Ship

For each approved task:

1. Merge worktree branch into feature branch
2. Push to remote
3. Create PR with narrative description (problem/why/what-was-done format)
4. Update pipeline state

### Step 6: Reflect

After all tasks shipped:

1. **Capture pipeline observation** to `learning/{project-hash}/observations.jsonl`:
   ```json
   {
     "record_type": "pipeline",
     "timestamp": "ISO 8601",
     "pipeline_id": "{batch-id}",
     "classification": "batch",
     "task_count": N,
     "phases": {
       "build": {"verdict": "BUILD_COMPLETE", "agents": N},
       "review": {"verdict": "APPROVE", "rounds": N, "findings": N}
     },
     "rework": true/false,
     "scratchpad_findings": ["category:summary", ...],
     "complexity_budget": null
   }
   ```

2. **Check auto-learn gate** — 3+ observations since last `/learn`? Invoke `/learn`.

3. **Update session memory** — spawn background agent to capture engineering knowledge.

4. **Clean up**:
   - Delete `pipeline-state/{batch-id}-pipeline.md`
   - Delete `pipeline-state/{batch-id}-scratchpad/`
   - Remove worktree branches

## Orchestrator Boundaries (same as full pipeline)

| ONLY does | NEVER does |
|-----------|------------|
| Create state files, spawn agents | Write source code |
| Run git commands | Run tests or builds |
| Track pipeline state | Make code decisions |
| Create PRs | Skip review phase |
