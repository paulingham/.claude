---
name: "harness-config"
description: "Modify the Claude Code harness itself: hooks (.sh), settings.json, agent definitions, and skill infrastructure. Delegates non-.md file changes to an infrastructure-engineer agent with worktree isolation. Use when adding/modifying hooks, settings, or any non-markdown config in ~/.claude/."
---

# Harness Configuration

## What This Skill Does

Manages changes to the Claude Code harness — the hooks, settings, agent definitions, and skill infrastructure that control how the orchestrator and agents operate.

**Why this skill exists:** The orchestrator may edit `.md` files in `.claude/` directly (config exception in `protocols/agent-protocol.md`). But `.sh` hooks, `.json` settings, and other non-markdown files are NOT covered by that exception. They must be delegated to an agent -- just like source code.

## When to Invoke

- Adding or modifying hook scripts (`.sh` files in `~/.claude/hooks/`)
- Changing `settings.json` or `settings.local.json`
- Creating or modifying agent definition files that contain non-trivial logic
- Any change to `~/.claude/` that is NOT a `.md` file

## What the Orchestrator CAN Do Directly

- Create/edit `.md` files: `skills/*/SKILL.md`, `rules/*.md`, `agents/*.md`, `CLAUDE.md`, `memory/*.md`
- These are documentation and configuration prose — no TDD applies

## What MUST Be Delegated

| File Type | Example | Delegate To |
|-----------|---------|-------------|
| Shell scripts | `hooks/*.sh` | infrastructure-engineer (worktree) |
| JSON config | `settings.json` | infrastructure-engineer (worktree) |
| YAML config | Any `.yaml`/`.yml` | infrastructure-engineer (worktree) |

## Process

### 1. Describe the Change

Write a clear specification of what the hook/setting should do:
- **Purpose**: What behavior does this enforce or enable?
- **Trigger**: When does it fire? (PreToolUse/PostToolUse matcher, tool name)
- **Logic**: What should it check or do?
- **Exit behavior**: Exit 0 (allow), exit 1 (warn), exit 2 (block)?
- **File path**: Where should it be created/modified?

### 2. Spawn Infrastructure Engineer

```
Agent({
  subagent_type: "infrastructure-engineer",
  isolation: "worktree",
  prompt: "Create/modify Claude Code harness config:
    [specification from Step 1]

    File: [path]
    Test: Run the hook manually with sample inputs to verify behavior.
    Make the file executable (chmod +x) if it's a shell script.

    If modifying settings.json: validate JSON syntax before committing."
})
```

### 3. Verify

After the agent completes:
- For hooks: test with a sample file to verify correct behavior
- For settings.json: validate JSON syntax (`python3 -m json.tool < settings.json`)
- For both: verify the change is registered (hooks appear in settings.json matchers)

### 4. Register in Settings (if new hook)

If a new hook was created, the orchestrator describes the settings.json change and spawns a SECOND infrastructure-engineer to update settings.json — or includes both in the original prompt.

## Anti-Patterns

- **Orchestrator directly writing .sh files**: Violates orchestrator discipline. The `.md` exception does NOT cover shell scripts.
- **Orchestrator directly editing settings.json**: Violates orchestrator discipline. JSON is not markdown.
- **"It's just a small config change"**: Still delegate. The cost of spawning an agent is low. The cost of breaking discipline is high.
- **The Bash bypass**: Running `python3 -c "open(...'w')"`, `sed -i`, `jq > file.json`, or any other shell command that writes a protected file is the **same violation** as using the Write/Edit tools directly — it just routes around the tool-level guard. The `orchestrator-discipline.sh` hook catches Write/Edit; the intent covers ALL write paths. If the Edit tool is blocked, the correct response is to invoke `/harness:harness-config`, not to find a Bash equivalent.
- **Hardcoded absolute paths in config**: Never write `/Users/<name>/` or `/home/<name>/` into `settings.json` args or hook commands. Use `$HOME` (shell-expanded at runtime via `bash -c`) or `~/.claude/` (in hook `command` strings, which are shell-executed). The MCP `args` array is NOT shell-expanded — use `bash -c` wrapper for those entries.

## Phase Output

```
Verdict: CONFIG_APPLIED (informational — no pipeline gate)
Next: Verify the change works. No further pipeline phases needed for harness config.
Artifacts: [list of files created/modified]
```
