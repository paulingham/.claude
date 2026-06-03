---
name: spec-grounding
description: Ground raw acceptance criteria against codebase evidence and recall. Invoked as Step 2c-ter (Stage 0 of Plan Phase) before the architect runs. Emits EARS-tagged ACs with per-AC citations to pipeline-state/{task-id}/spec-grounding.md.
verdict: GROUNDED|GROUNDING_GAPS
phase: plan
dispatch: subagent
---

# Spec-Grounding

> Python helper: `skills/spec_grounding/_lib/` (underscore, importable); skill contract: this file.
>
> The Python package uses an underscore path (`skills/spec_grounding/`) required for Python importability.
> This SKILL.md uses kebab-case (`skills/spec-grounding/SKILL.md`) required by the verdict audit and skill naming convention.

## When to Invoke

Invoked by the orchestrator as **Step 2c-ter** in `skills/pipeline/SKILL.md`, immediately after Step 2c-bis (plan-cache-lookup) returns `PLAN_CACHE_MISS`. Runs before any architect or recon dispatch.

- **Trigger**: Plan Phase begins and plan-cache returns MISS.
- **Do NOT invoke when**: A `PLAN_CACHE_HIT` was received — the cached plan already contains grounded ACs.

## Inputs

- `pipeline-state/{task-id}/intake.md` — raw acceptance criteria (AC list).
- `repo_root` — absolute path to the repository root for codebase traversal (scoped to relevant subtree when possible to avoid hitting the 5000-file traversal limit).
- `CLAUDE_RECALL_DB_PATH` env var — optional path to recall memory.sqlite; if absent or pointing to a non-existent file, grounding degrades to codebase-only (never raises, never blocks Plan).

## Procedure

### Step 1: Read Raw ACs from intake.md

Read `pipeline-state/{task-id}/intake.md` and extract the acceptance criteria list (lines matching `- [ ] AC…` or numbered AC entries).

### Step 2: Call the Python helper

```python
import sys
from pathlib import Path

repo_root = Path("/path/to/repo")
sys.path.insert(0, str(repo_root / "skills"))

from spec_grounding._lib.grounding import ground_acs

raw_acs = ["WHEN x the system SHALL y", "The system should handle errors"]
grounded = ground_acs(raw_acs, repo_root=repo_root)
```

The helper:
1. Walks the codebase (pathlib, bounded to 5000 files, max 1MB per file) skipping `.git/`, `.claude/worktrees/`, binary files, and files that raise `OSError` or `UnicodeDecodeError`.
2. Calls `recall.search()` if `CLAUDE_RECALL_DB_PATH` is set to a valid path; degrades gracefully (returns `[]`) on missing DB or import failure.
3. Returns one `GroundedAC` per input, never raises.

### Step 3: Write pipeline-state/{task-id}/spec-grounding.md

Write the output file per the Data Model in `pipeline-state/ws-g-spec-grounding/plan.md`:

```markdown
---
task_id: {task-id}
phase: plan
verdict: GROUNDED | GROUNDING_GAPS
timestamp: ISO-8601
ac_forms:
  ears: N
  prose: M
  total: N+M
grounding_gaps: []   # list of AC ids with no resolved citation
---

## Grounded Acceptance Criteria

- [ ] AC1 (form: ears-event): WHEN <trigger> the system SHALL <response> [grounded: path/to/file.py:N-M]
- [ ] AC2 (form: prose): <assertion text> [grounded: gap]

## Grounding Citations

| AC | Citation | Evidence Type |
|----|----------|---------------|
| AC1 | `path/to/file.py:14-28` | pathlib/re match |

## Gaps (GROUNDING_GAPS only)
- AC2: no codebase match or recall hit — architect must supply evidence.
```

### Step 4: Emit verdict line

Emit to stdout: `GROUNDED` or `GROUNDING_GAPS`.

- **GROUNDED**: All ACs have a resolved citation (`resolved=True` for every `GroundedAC`).
- **GROUNDING_GAPS**: One or more ACs have `citation="gap"` (`resolved=False`). The gaps are listed in `spec-grounding.md` § Gaps and flagged in frontmatter `grounding_gaps:` list.

## Output

- **State file**: `pipeline-state/{task-id}/spec-grounding.md` with verdict in frontmatter.
- **Stdout**: one verdict line (`GROUNDED` or `GROUNDING_GAPS`).

## Verdict

The exact set of verdicts this skill emits. Both must appear in `protocols/verdict-catalog.md` with emitter `spec-grounding`.

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `GROUNDED` | All ACs resolved against codebase or recall evidence. | Architect reads `spec-grounding.md` at Pre-Drafting Recon. Plan proceeds normally. |
| `GROUNDING_GAPS` | One or more ACs have no codebase or recall match. Gaps listed in `spec-grounding.md` § Gaps. | **Non-blocking.** Architect proceeds — gap ACs appear with `[grounded: gap]` suffix. Architect must supply evidence for gap ACs in Artifact 2 (Codebase Ground-Truth Citations). |

**User-facing copy (Persona 2):**
- `GROUNDED`: "All acceptance criteria grounded against codebase evidence."
- `GROUNDING_GAPS`: "{N} of {M} acceptance criteria have no codebase match. Gap ACs listed in `pipeline-state/{task-id}/spec-grounding.md` § Gaps. Architect must supply evidence for these ACs."

**Degradation behaviour (recall absent):** When `CLAUDE_RECALL_DB_PATH` is unset or points to a non-existent file, grounding falls back to codebase-only pathlib traversal. The skill still emits `GROUNDED` or `GROUNDING_GAPS` based on codebase evidence alone. This path is identical to the absent-recall path — `recall.search()` degrades to `[]` via `@dispatch.guarded` and the skill continues. Plan is never blocked.

## Anti-Patterns

- **Scoping `repo_root` to the full monorepo root on large repos**: The traversal is bounded to 5000 files. Scope `repo_root` to the relevant subtree (e.g., `skills/`, `protocols/`) when the AC terms are domain-specific. Use the full root only when AC terms cross domains.
- **Treating `GROUNDING_GAPS` as a blocking verdict**: It is non-blocking by design. The architect proceeds with gap ACs marked `[grounded: gap]` and supplies their own citations for those ACs in Artifact 2.
- **Invoking after plan-cache HIT**: If `PLAN_CACHE_HIT` was returned by Step 2c-bis, skip this step — the cached plan already has grounded ACs.
