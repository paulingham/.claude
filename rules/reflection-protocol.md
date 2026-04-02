# Reflection Protocol

## When to Reflect

After EVERY pipeline completion — features, bug fixes, refactors. Reflection is not optional.

- **After rework/bugs**: Focus on what went wrong and how to prevent it
- **After clean pipelines**: Focus on what went well and what patterns to codify

## Reflection Checklist

At pipeline completion, before reporting final status to the user, run through this checklist:

### 1. What Happened?

If the pipeline experienced failures, >2 review rounds, or any recovery loop, consider invoking `/forensics` first. The forensics report reconstructs the timeline from trajectory JSONL and provides evidence-based findings rather than memory-based recollection.

Review the pipeline execution:
- Were there any bugs, rework, or CHANGES_REQUESTED cycles?
- Were there any surprises or unexpected behaviors on device/in production?
- Did any assumptions prove wrong?
- What patterns or approaches worked well?

### 2. Root Cause Analysis (if issues occurred)

For each issue encountered:
- What was the root cause? (missing rule, wrong assumption, untested path, timing issue)
- Was this preventable with existing knowledge?
- What check or rule would have caught it earlier?

### 3. Identify Improvements

Map learnings to concrete actions. Check each category:

| Category | File(s) | Ask |
|----------|---------|-----|
| **Project conventions** | Project `.claude/CLAUDE.md` | Should a new pattern, rule, or limitation be documented? |
| **Global rules** | `~/.claude/rules/*.md` | Should a new or updated rule prevent this class of issue? |
| **Global playbook** | `~/.claude/CLAUDE.md` | Should the pipeline, definition of done, or protocols change? |
| **Agent definitions** | `~/.claude/agents/*.md` | Should agent checklists include new verification steps? |
| **Feedback memory** | Project `memory/feedback_*.md` | Should a lesson be saved for future sessions? |
| **Skills** | `~/.claude/skills/*/SKILL.md` | Should a skill's process or checklist be updated? |
| **README** | `~/.claude/README.md` | Does the README reflect current capabilities, skills, hooks, architecture? |

### 4. Apply Changes

- Source files (`.claude/CLAUDE.md`, rules, agents, skills): delegate to agents
- Memory files: write directly (memory is excluded from orchestrator code ban)
- Update `MEMORY.md` index if new memory files are created
- **README update is mandatory** when any of these change: skills (added/removed), hooks (added/removed), architecture (new directories/systems), agent team (roles changed), or delivery pipeline (phases changed). The README is the external-facing description of the system — it must stay current

### 5. Report

Summarise to the user:
- What was learned (1-3 bullets)
- What was updated (file list)
- Skip if nothing actionable was identified (clean pipeline, no new patterns)

## What Good Reflection Looks Like

**After a feature with bugs:**
> Learned: `display: none` on WebView containers hides dynamic children (menus). Added CSS hiding rule to project CLAUDE.md and feedback memory.

**After a clean feature:**
> Learned: The NavigationBar → AppHeader → WebView composition pattern works well for replacing HTML elements with native components. No changes needed — existing patterns sufficient.

**After a refactor:**
> Learned: Session detection has multiple fallback layers for timing reasons. Added rule: prefer narrowing conditions over removing them.

## 6. Autonomous Intelligence (Mandatory — see `rules/autonomous-intelligence.md`)

After reflection steps 1-5, execute these in order:

### 6a. Capture Pipeline Observation

Append a structured observation to `learning/{project-hash}/observations.jsonl`. Every pipeline produces one observation — successes and failures both. Include: phase verdicts, review rounds, scratchpad findings summary, rework flag, complexity budget. Format in `rules/autonomous-intelligence.md` § Observation Capture.

### 6b. Auto-Learn Gate Check

Check if all conditions are met:
- 3+ observations since last `/learn` run for this project
- No `/learn` run in last 3 pipelines

If gate is met: invoke `/learn` as the final step of reflection. This is automatic — the user should never need to invoke `/learn` manually.

### 6c. Update Session Memory

Spawn a forked agent (background, non-blocking) with the session memory update prompt to capture engineering knowledge from this pipeline. See `rules/autonomous-intelligence.md` § Session Memory.

### 6d. Clean Up Scratchpad

Delete `pipeline-state/{task-id}-scratchpad/` alongside the pipeline state files.

## Anti-Patterns

- **Skipping reflection because the pipeline was clean** — Clean pipelines still produce learnings (validated patterns, confirmed approaches)
- **Writing vague memories** — "Be more careful" is not actionable. Write specific rules with Why and How to Apply
- **Reflecting only on failures** — Also codify what worked well, so future sessions repeat good patterns
- **Over-documenting** — If nothing was surprising or non-obvious, say so and move on. Not every pipeline produces new rules
- **Skipping observation capture** — Every pipeline produces an observation. No exceptions. The learning loop depends on data volume
