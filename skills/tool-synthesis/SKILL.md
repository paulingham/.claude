---
name: "tool-synthesis"
description: "Use when standard tools are insufficient and the agent would benefit from a one-shot scratch tool (codebase-specific code-search, AST analyzer, repo-specific linter). Engineer authors a small executable inside the worktree, registers it, invokes it, and tears it down at merge. Inspired by Live-SWE-agent (arXiv 2511.13646)."
context: fork
agent: software-engineer
argument-hint: "Description of the gap a scratch tool would fill"
---

# Tool Synthesis

## What This Skill Does

Lets a build engineer (software-engineer or frontend-engineer) write a tiny custom tool inside its own worktree, register it, and call it from subsequent Bash invocations — without polluting the main branch or the global agent toolset.

The synthesised tool lives at `${WORKTREE}/.claude-scratch-tools/<name>` and is invoked via `Bash("${WORKTREE}/.claude-scratch-tools/<name> <args>")`. The directory is `.gitignore`d at both the harness root and (per the skill's procedure) the target repo's root, so scratch tools NEVER reach `main`.

## When to Invoke

Triggers (any one is sufficient):

- The same lookup or transformation is performed manually **3+ times** in the current task.
- No extant tool covers the operation (no `rg` pattern, no `ast-grep` rule, no project-shipped script does it cleanly).
- A repo-specific concern (custom DSL, generated file, codebase convention) makes off-the-shelf tools wrong.

If a built-in tool (Grep, Glob, Read, Bash one-liner) covers it, USE IT — do not synthesise.

## Scope Boundary

Scratch tools are:

- **Worktree-scoped**: live under `${WORKTREE}/.claude-scratch-tools/`, never copied elsewhere
- **Ephemeral**: deleted on merge / before completion via `register.sh --cleanup`
- **Auditable**: every registration is recorded in `registry.json` for the reviewer
- **Read-only by default**: prefer tools that report (grep, count, parse) over tools that mutate

Scratch tools MUST NOT:

- Modify code outside the worktree
- Hit the network without explicit user authorisation
- Persist beyond the current pipeline run
- Be promoted to a "real" tool without going through `/skill-builder` and full review

## Procedure

### Step 1: Justify the Tool

Write a one-line justification in the pipeline scratchpad before registering:

```
pipeline-state/{task-id}-scratchpad/tool-synthesis.md
---
category: decision
---
Synthesised `<tool-name>` because <trigger>. Replaces N manual <operation> calls.
```

If you cannot articulate the trigger in one sentence, the tool is probably unnecessary.

### Step 2: Author the Tool

Write the tool as a single executable file inside the worktree (typically `bash`, `python3`, or `node` — match the project's existing scripting language):

```bash
cat > /tmp/<tool-name>.sh <<'EOF'
#!/usr/bin/env bash
# One-line purpose comment.
set -euo pipefail
# implementation
EOF
```

Keep the tool small (≤ 50 lines). Larger logic belongs in a real module behind TDD.

### Step 3: Register the Tool

```bash
~/.claude/skills/tool-synthesis/lib/register.sh \
  <tool-name> \
  /tmp/<tool-name>.sh \
  "<one-sentence description>"
```

This:

1. Copies the tool into `${WORKTREE}/.claude-scratch-tools/<tool-name>`
2. Marks it executable (`chmod +x`)
3. Adds it to `${WORKTREE}/.claude-scratch-tools/registry.json`
4. Creates `${WORKTREE}/.claude-scratch-tools/.gitignore` (self-protecting)

The tool now appears as an entry on the **per-worktree allowed-tools surface**: subsequent Bash calls in this worktree can invoke it directly via its absolute path. Other worktrees cannot see it (per-worktree isolation).

### Step 3b: Ensure Repo-Root .gitignore Excludes the Directory

If the target repo's `.gitignore` does not already exclude `.claude-scratch-tools/`, append it:

```bash
grep -q '^\.claude-scratch-tools/$' .gitignore 2>/dev/null \
  || echo '.claude-scratch-tools/' >> .gitignore
```

Commit this change once, in its own commit: `chore: gitignore worktree scratch tools`. Subsequent pipelines reuse it.

### Step 4: Use the Tool

```bash
${WORKTREE}/.claude-scratch-tools/<tool-name> <args>
```

The tool is just an executable on disk — the Bash tool already covers it. No special permission grant needed.

### Step 5: Cleanup Before Merge

Before signalling BUILD_COMPLETE:

```bash
~/.claude/skills/tool-synthesis/lib/register.sh --cleanup ${WORKTREE}
```

This removes the entire `.claude-scratch-tools/` directory. If the tool proved generally useful, propose it through `/skill-builder` as a real, reviewed addition — do not smuggle scratch tools into `main`.

The `.gitignore` rule is the safety net: even if cleanup is skipped, `git status` shows nothing under `.claude-scratch-tools/` and the merge cannot carry the directory.

## Verdict

- **TOOL_SYNTHESISED**: tool registered, used, and either (a) cleaned up or (b) flagged for promotion via `/skill-builder`.
- **TOOL_UNNECESSARY**: built-in tools cover the operation; no synthesis performed.

## Phase Output

```
Verdict: TOOL_SYNTHESISED / TOOL_UNNECESSARY
Tool: <name>
Justification: <one line>
Cleanup: confirmed / promoted-via-skill-builder
```

## Anti-Patterns

- Synthesising a tool to avoid writing a proper test → BLOCKED. TDD still applies to feature code.
- Synthesising a tool that modifies source files → BLOCKED. Use Edit/Write directly so the diff is visible to the reviewer.
- Skipping the justification step → BLOCKED. Reviewers need to see why the tool existed.
- Leaving the tool in the worktree at merge → BLOCKED. The pipeline cleanup step is mandatory.
- Reaching for synthesis on the first manual lookup → BLOCKED. Trigger threshold is 3+.

## Inspiration

Live-SWE-agent (arXiv 2511.13646) reports a +10pt SWE-Verified lift when agents can author runtime tools tailored to the repo under test. This skill packages that capability in a way that keeps `main` clean and review trails intact.
$ARGUMENTS
