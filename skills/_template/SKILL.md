---
name: "skill-name-kebab-case"
description: "One-sentence description of when to invoke this skill. Should answer 'what does this do' and 'when do I use it' in a single sentence. Used by the harness to surface the skill in the directory."
verdict: "VERDICT_NAME"
phase: "intake|plan|plan-validation|build|review|final-gate|ship|deploy|reflect|utility"
dispatch: "skill-tool|subagent|team"

# Optional fields (set when the skill spawns a subagent / teammate):
# context: fork
# agent: software-engineer

# Optional model hint (when the skill itself runs as a one-shot, not when it spawns):
# model: sonnet|opus|haiku

# Optional argument hint shown in skill help:
# argument-hint: "Feature description / story / failing test command"
---

# Skill Name (Title Case)

> Canonical skill template. Copy this directory to `skills/<your-skill>/` and replace placeholders. The `/harness:harness-audit` step `skill-structure-drift` validates every skill against this layout.

## When to Invoke

When this skill should fire. Be specific — if a sibling skill already covers part of the territory, name it and explain the boundary.

- **Trigger 1**: Concrete situation that should route here.
- **Trigger 2**: Another concrete situation.
- **Do NOT use when**: Cases that look similar but belong to a sibling skill (`/sibling-skill`).

## Inputs

What this skill expects to be available before it starts. Include file paths the skill will read, environment vars it reads, prior phase verdicts it depends on.

- **Pipeline state**: e.g. `pipeline-state/{task-id}/build.md` with verdict `BUILD_COMPLETE`
- **External**: e.g. project `CLAUDE.md` Commands section, `.env` for secrets
- **User**: e.g. acceptance criteria, error description, target branch

## Procedure

Numbered, auditable steps. One concrete action per step. The skill body MUST be procedural — readers execute it literally, not philosophically.

### Step 1: <verb-phrase>

Concrete actions. Show the exact commands or tool invocations. If the skill spawns an agent, show the spawn invocation.

```bash
# Example concrete command
git -C "$WORKTREE" diff main...HEAD
```

### Step 2: <verb-phrase>

...

### Step 3 (optional): <verb-phrase>

If this step has a gate, name the gate and the verdict it produces.

## Output

What this skill produces. Be specific about file paths, frontmatter, and downstream consumers.

- **State file**: `pipeline-state/{task-id}/<phase>.md` with the verdict in frontmatter
- **Artifacts**: e.g. test outputs, mutation reports, PR URL, scratchpad findings
- **Scratchpad**: `pipeline-state/{task-id}/scratchpad/<role>-<phase>.md` for findings the next phase needs

### Output File Format

```markdown
---
task_id: {task-id}
phase: <this-skill's-phase>
verdict: <one of the verdicts below>
timestamp: ISO-8601
---

## Summary
1-3 sentence outcome.

## Key Findings
- ...

## Next Phase Input
What the consuming phase needs to know.
```

## Verdict

The exact set of verdicts this skill emits. MUST match `rules/verdict-catalog.md`. Use uppercase snake-case identifiers.

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `VERDICT_NAME` | Success path. | Next phase consumes the state file. |
| `VERDICT_NAME_FAILED` | Failure path with concrete remediation. | Pipeline halts or returns to prior phase. |

The skill MUST emit exactly one verdict per invocation. Multiple verdicts on one run is a structural bug.

## Anti-Patterns

What NOT to do in this skill. Pulled from real incidents — keep this list short and specific to this skill's territory.

- **Anti-pattern 1**: Concrete description + why it fails.
- **Anti-pattern 2**: ...

## Tests

Skill-level tests live in `skills/<your-skill>/tests/`. At minimum:

- One test that asserts the frontmatter parses, the verdict is in `rules/verdict-catalog.md`, and every section heading from this template exists.
- One test per documented verdict that exercises the skill's output contract (golden file or schema check).

See `skills/_template/tests/` for placeholder fixtures.
