---
name: "harness-audit"
description: "Use when user wants to Audit the health of the ~/.claude/ config: orphan hooks, missing skills, stale agents, JSON validity, hook executability. Reports HEALTHY / WARNINGS / CRITICAL."
argument-hint: "Optional: focus area (hooks|skills|agents|all)"
---

# Harness Audit

## What This Skill Does

Inspects the `~/.claude/` orchestration layer for configuration health issues — orphan hooks, missing references, invalid JSON, non-executable scripts, and stale agent definitions. Produces a scored health report.

## Process

### 1. Hook Health

**a. Registered hooks exist as files:**
For every hook command in `settings.json` (`PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `UserPromptSubmit`, `SessionStart`, `SessionEnd`, `PreCompact`, `PostCompact`):
- Extract the script path from `"command": "bash ~/.claude/hooks/foo.sh"`
- Check the file exists: `ls ~/.claude/hooks/foo.sh`
- Check it is executable: `test -x ~/.claude/hooks/foo.sh`

**b. Orphan hooks (files not registered):**
- List all `~/.claude/hooks/*.sh` files
- Check each is referenced in `settings.json`
- Flag any that exist but aren't registered (potential dead code)

**c. Hook shared libraries sourced correctly:**
- Verify `hook-profile.sh` and `loop-guard.sh` exist (they're sourced by other hooks)

### 2. Skills Health

**a. Skills referenced in CLAUDE.md exist:**
- Read `~/.claude/CLAUDE.md` and extract all `/skill-name` references
- Check `~/.claude/skills/{skill-name}/SKILL.md` exists for each
- Flag missing skill files

**b. Skill frontmatter validity:**
- Each `skills/*/SKILL.md` and `skills/_deferred/*/SKILL.md` (excluding `_template/`) must have: `name`, `description` fields in YAML frontmatter
- Flag any missing required fields
- Deferred skills (under `skills/_deferred/`) remain invokable via forcing-function or channel-gated routing, so they are subject to the same frontmatter checks as top-level skills

**c. Skill structure drift (canonical template = `skills/_template/SKILL.md`):**
For every `skills/*/SKILL.md` and `skills/_deferred/*/SKILL.md` (excluding `_template/`), validate against the canonical template. Deferred skills remain subject to the same frontmatter, section, and verdict checks because they are still invokable via the routing paths described in CLAUDE.md.

- **Required frontmatter fields**: `name`, `description`, `verdict`, `phase`, `dispatch`. Flag any skill missing one or more.
- **Phase enum**: `phase` MUST be one of: `intake`, `plan`, `plan-validation`, `build`, `review`, `final-gate`, `ship`, `deploy`, `reflect`, `utility`. Flag any skill with a value outside this list.
- **Dispatch enum**: `dispatch` MUST be one of: `skill-tool`, `subagent`, `team`. Flag any skill with a value outside this list.
- **Required sections**: every skill body MUST contain `## When to Invoke`, `## Procedure`, `## Output`, `## Verdict`. Flag any skill missing one or more headings (case-sensitive match on `^## `).
- **Tests directory**: every skill SHOULD have `skills/{name}/tests/` (a directory or at minimum a `.gitkeep`). Skills without a `tests/` directory are flagged at WARNING severity (not CRITICAL — older skills may lack tests). New skills created from `_template/` automatically inherit it.

Verdict for this step: `STRUCTURE_OK` if every skill conforms; otherwise list the drift findings (one bullet per skill, naming the missing fields/headings).

**d. Verdict consistency (canonical catalog = `rules/verdict-catalog.md`):**
Cross-reference `skills/*/SKILL.md` and `skills/_deferred/*/SKILL.md` (excluding `_template/`) verdict declarations against the catalog in both directions. Without including `_deferred/`, the reverse-direction check would falsely flag verdicts emitted only by deferred skills (e.g. `VOICE_SCAFFOLDED`, `BFF_SCAFFOLDED`, `SERVICE_EXTRACTED`, `SERVICE_SCAFFOLDED`, `CROSS_SERVICE_VERIFIED`, `CROSS_SERVICE_BLOCKED`, `EXTRACTION_BLOCKED`, `WRONG_SKILL`) as orphan catalog rows.

- **Forward direction**: every `verdict` value declared in any skill's frontmatter (or in any `Verdict: X / Y` line in the body for legacy skills) MUST appear in `rules/verdict-catalog.md`. Flag any skill emitting a verdict the catalog does not list.
- **Reverse direction**: every entry in `rules/verdict-catalog.md` MUST be emitted by at least one skill. Flag catalog rows whose `Emitter skill` column resolves to a non-existent `skills/<name>/SKILL.md`, or whose listed emitter does not actually emit that verdict.
- **Polarity column**: every catalog row MUST have a `Polarity` value of `success`, `failure`, or `info`. Flag rows with missing or invalid polarity.
- **Catalog absent**: if `rules/verdict-catalog.md` is missing entirely, this step reports `VERDICTS_NO_CATALOG` and no findings — running the audit before C3 lands is acceptable.

Verdict for this step: `VERDICTS_CONSISTENT` if both directions match; otherwise list drift findings (catalog entries with no emitter, skills with verdicts not in catalog, polarity violations).

### 3. Agent Definitions Health

**a. Required frontmatter fields:**
Each `agents/*.md` (excluding `dynamic/` and `archive/`) must have:
- `name` — matches filename
- `description` — non-empty
- `tools` — at least one tool listed
- `model` — one of: opus, sonnet, haiku
- `maxTurns` — positive integer
- `disallowedTools` — present (may be empty list)

Flag any agent missing required fields.

**b. Read-only agents have write tools disallowed:**
Agents whose descriptions include "read-only", "reviewer", "auditor":
- `code-reviewer`, `security-engineer`, `product-reviewer`, `architect`
- Must have `Write`, `Edit`, `MultiEdit` in `disallowedTools`

### 4. settings.json Validity

```bash
cat ~/.claude/settings.json | jq . > /dev/null 2>&1 && echo "VALID" || echo "INVALID JSON"
```

Also check:
- All hook `type` values are valid: `command`, `agent`
- All `matcher` values reference real tool names
- `env` section has `CLAUDE_HOOK_PROFILE` defined

### 4b. Configuration Linting (if agnix available)

```bash
npx agnix ~/.claude/ 2>/dev/null
```

If agnix is installed, run it and incorporate findings into the audit report. Flag:
- Skills with invalid frontmatter (missing `name` or `description`)
- Rules with `paths:` globs that don't match real files
- Agent definitions missing required fields
- Hook scripts that reference non-existent paths
- Skill files not following Claude Code's expected structure

### 5. Knowledge Library Health

- List all `~/.claude/knowledge/*.md` files
- Check each is referenced in at least one `agents/*.md` (Knowledge References section)
- Flag unreferenced knowledge files (dead documentation)

### 6. Pipeline State Cleanup

- List all `~/.claude/pipeline-state/*.md` and `*.jsonl` files (excluding README.md and .gitkeep)
- Flag any that are more than 7 days old (stale state from abandoned pipelines)
- Report count of active vs stale state files

## Scoring

| Category | Issues Found | Score |
|----------|-------------|-------|
| Hooks | None | ✅ |
| Hooks | Warnings only | ⚠️ |
| Hooks | Missing/non-executable hooks | ❌ |
| Skills | None | ✅ |
| Skills | Missing skill files | ❌ |
| Skill Structure | All skills match `_template/SKILL.md` (frontmatter + sections) | ✅ |
| Skill Structure | Frontmatter or required-section drift on one or more skills | ⚠️ |
| Verdict Catalog | Catalog and skill verdicts agree both directions | ✅ |
| Verdict Catalog | Forward or reverse drift, or invalid polarity | ⚠️ |
| Verdict Catalog | Catalog file absent | ⚠️ |
| Agents | None | ✅ |
| Agents | Missing frontmatter | ⚠️ |
| Agents | Write tools not disallowed on read-only agents | ❌ |
| JSON | Valid | ✅ |
| JSON | Invalid | ❌ |
| Knowledge | All referenced | ✅ |
| Knowledge | Orphan files | ⚠️ |

## Output Format

```
## Harness Audit Report
Date: [timestamp]

### Verdict: HEALTHY / WARNINGS / CRITICAL

### Hooks (N/N passing)
- ✅ quality-gate.sh — registered, executable
- ❌ missing-hook.sh — registered in settings.json but file not found
- ⚠️ orphan-hook.sh — file exists but not registered in settings.json

### Skills (N/N passing)
- ✅ /pipeline — SKILL.md found
- ❌ /missing-skill — SKILL.md not found

### Skill Structure (N/N matching template)
- ✅ /verify — frontmatter + required sections present
- ⚠️ /old-skill — missing `verdict` frontmatter field, missing `## When to Invoke` heading
- ⚠️ /another-skill — no `tests/` directory

### Verdict Catalog (N/N consistent both directions)
- ✅ /code-review — emits APPROVE/CHANGES_REQUESTED, both in catalog
- ⚠️ /custom-skill — emits CUSTOM_VERDICT, not in `rules/verdict-catalog.md`
- ⚠️ catalog row `LEGACY_VERDICT` has no emitter (dead entry)
- ⚠️ catalog row `BUILD_COMPLETE` has invalid polarity `done` (must be success/failure/info)

### Agent Definitions (N/N passing)
- ✅ software-engineer — all frontmatter present
- ⚠️ some-agent — missing maxTurns field
- ❌ code-reviewer — Write not in disallowedTools

### settings.json
- ✅ Valid JSON
- ✅ CLAUDE_HOOK_PROFILE defined

### Knowledge Library (N/N referenced)
- ✅ database-patterns.md — referenced by database-engineer
- ⚠️ orphan-patterns.md — not referenced by any agent

### Pipeline State
- N active state files
- N stale files (>7 days old) — recommend cleanup

### Summary
[Total: N critical, N warnings, N passing]
```

## Phase Output

```
Verdict: HEALTHY / WARNINGS / CRITICAL
Next: Fix flagged issues, re-run /harness-audit to confirm
Artifacts: [health report with itemised findings]
```
$ARGUMENTS
