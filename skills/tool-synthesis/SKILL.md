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
- **Repeated grep over the same large directory tree (>3 times in a phase)** — when the same `rg`/`grep` invocation against the same root is issued more than three times in a single pipeline phase, a scratch tool that pre-indexes or pre-filters the tree pays for itself.
- **Recurring AST-shape question** — the agent is using regex to answer a question that is fundamentally syntactic (function-with-decorator-X, class-extending-Y, call-to-Z-with-N-args). A scratch `ast-grep`/Tree-sitter wrapper makes the question deterministic.
- **Project-specific lint check the agent re-implements** — the agent is hand-rolling the same convention check (forbidden import, naming rule, structural invariant) inside multiple Edits. A scratch linter expresses the rule once and runs it everywhere.
- No extant tool covers the operation (no `rg` pattern, no `ast-grep` rule, no project-shipped script does it cleanly).
- A repo-specific concern (custom DSL, generated file, codebase convention) makes off-the-shelf tools wrong.

If a built-in tool (Grep, Glob, Read, Bash one-liner) covers it, USE IT — do not synthesise.

### Promotability Gate

If the synthesised tool's signature (name + one-line description + invocation pattern) would be **reusable across pipelines** (not just this task's accidental shape), record that explicitly in the scratchpad with `promotable: true`. The `/harness:learn` skill scans observations for this marker; when the same tool signature appears in ≥3 pipelines it generates a permanent skill scaffold for human review (see `skills/learn/SKILL.md`). Use the verdict `TOOL_SYNTHESISED_PROMOTABLE` instead of `TOOL_SYNTHESISED` when this is the case.

Promotability heuristics (each "yes" raises the score):

- Tool answers a question that any pipeline in this codebase would reasonably ask.
- Tool wraps a public API (LSP, CST, project config) rather than a one-shot pattern.
- Tool's invocation does not encode task-specific paths, branches, or magic numbers.

If you cannot articulate why the tool is reusable beyond this pipeline, mark it `TOOL_SYNTHESISED` (one-shot) and let it be cleaned up.

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
- Be promoted to a "real" tool without going through `/harness:skill-builder` and full review

## Procedure

### Step 1: Justify the Tool

Write a one-line justification in the pipeline scratchpad before registering:

```
pipeline-state/{task-id}/scratchpad/tool-synthesis.md
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

This removes the entire `.claude-scratch-tools/` directory. If the tool proved generally useful, propose it through `/harness:skill-builder` as a real, reviewed addition — do not smuggle scratch tools into `main`.

The `.gitignore` rule is the safety net: even if cleanup is skipped, `git status` shows nothing under `.claude-scratch-tools/` and the merge cannot carry the directory.

## Verdict

- **TOOL_SYNTHESISED**: tool registered, used, and either (a) cleaned up or (b) flagged for promotion via `/harness:skill-builder`.
- **TOOL_SYNTHESISED_PROMOTABLE**: same as `TOOL_SYNTHESISED` plus the tool's signature is reusable across pipelines. The `/harness:learn` skill picks this up and counts cross-pipeline recurrences; on the third occurrence it scaffolds a permanent skill at `skills/<tool-name>/SKILL.md` (from `skills/_template/`) and surfaces it for human review. The scratch tool is still cleaned up from the worktree — the permanent scaffold is the path forward, not a smuggled scratch tool.
- **TOOL_UNNECESSARY**: built-in tools cover the operation; no synthesis performed.

## Phase Output

```
Verdict: TOOL_SYNTHESISED / TOOL_SYNTHESISED_PROMOTABLE / TOOL_UNNECESSARY
Tool: <name>
Justification: <one line>
Promotable: true | false (set when verdict == TOOL_SYNTHESISED_PROMOTABLE)
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

## Why This Works

The Live-SWE-agent paper (Cui et al., arXiv:2511.13646) reports an empirical **77.4% pass rate on SWE-bench-Verified** by allowing the agent to author scratch tools at inference time and reuse them within the run. The lift over a fixed-toolset baseline is concentrated in repository-specific tasks where off-the-shelf tools lack the right granularity:

- **Codebase-specific search** (e.g., "find every place a stale config key is read") becomes a one-shot script instead of N grep iterations.
- **AST-shape questions** become deterministic queries instead of regex approximations.
- **Convention checks** become re-runnable linters instead of hand-rolled per-edit verifications.

The empirical lift is conditional on three properties this skill enforces:

1. **Per-worktree isolation** — scratch tools never leak to `main` (`.gitignore` + cleanup gate).
2. **Auditability** — `registry.json` records every synthesis decision so reviewers can challenge the tool's existence.
3. **Promotion path** — useful tools graduate via `/harness:skill-builder` and `/harness:learn` (the TOOL_SYNTHESISED_PROMOTABLE → permanent-skill scaffold), so reusable patterns harden into the harness instead of disappearing with the worktree.

Without those three guards, scratch-tool synthesis becomes a way to smuggle untested code into production. With them, it is a controlled inference-time capability that has an empirical track record.
$ARGUMENTS
