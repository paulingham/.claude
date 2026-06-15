# Contributing to the Claude Code Harness

Welcome. This guide explains how to extend the harness safely.
The harness has CI guards that catch count drift, registration gaps, and test-fixture
issues. The scaffolding scripts handle the brittle wiring for you.

## Two Paths: EASY vs GATED

### EASY Path — Reference / Clean-Code Skill

Add a skill that shares a technique or pattern (no pipeline wiring required):

```bash
bash scripts/new-skill.sh my-naming-tips
```

The script copies `templates/skill-reference/SKILL.md` into `skills/my-naming-tips/SKILL.md`,
fills in the `name` field, and proposes a README bump. Confirm to apply.

Frontmatter is `name` + `description` **only**. No `verdict`, `phase`, or `dispatch`.
See `templates/skill-reference/AUTHORING.md` for guidance.

### GATED Path — Pipeline Skills, Agents, Hooks

These surfaces require maintainer review because they wire into the pipeline,
update pinned CI tests, or affect enforcement gates.

**Adding a pipeline skill:** requires adding a `verdict:` to `verdict-catalog.md`
and wiring into `protocols/skill-directory.md`. Open a discussion issue first.

**Adding an agent:**

```bash
bash scripts/new-agent.sh my-new-agent
```

Updates `agents/`, the `### Agent Team` table in `CLAUDE.md`, and the README agent count.
See `templates/AGENT_AUTHORING.md` for the frontmatter contract.

**Adding a hook:**

```bash
bash scripts/new-hook.sh my-guard PostToolUse
```

Auto-wires BOTH `hooks/hooks.json` AND `settings.json` (the dual registration required
for hooks to fire in all contexts). Prints a diff for review before writing.
If you decline the prompt: the `.sh` file will exist in `hooks/` but NEITHER registry
will be updated. The script will print a loud warning and exit non-zero.
See `templates/HOOK_AUTHORING.md` for the 12-AC invariant.

## Template Files

All templates live under `templates/` (never under `skills/`, `agents/`, or `hooks/` —
those dirs are globbed by CI tests and picking up a template would break the count):

| Surface | Template | Authoring guide |
|---|---|---|
| Reference skill | `templates/skill-reference/SKILL.md` | `templates/skill-reference/AUTHORING.md` |
| Agent | `templates/agent-template.md` | `templates/AGENT_AUTHORING.md` |
| Hook | `templates/hook-template.sh` | `templates/HOOK_AUTHORING.md` |

## Must-Run Before Every Push

Run BOTH from the repo root:

```bash
bash tests/shell/run.sh
```

```bash
pytest -k "readme or verdict or catalog or inventory or stop_hook or counts_match or agent_table or registration"
```

The first runs the full bats shell test suite (hook registration, invariants, CI guards).
The second runs the Python tests that pin the README counts, agent table shape,
and skill/agent registration invariants.

Do NOT run `pytest tests/` (the full suite is slow and has known pre-existing failures
unrelated to your change).

## Hook Registration Details

Every hook must be present in BOTH registries:

- `hooks/hooks.json` — governs hooks when running from the install directory
- `settings.json` — governs hooks when running from any other directory

Use `scripts/new-hook.sh` — it writes the canonical idiom into both files,
validates JSON after writing, and re-runs the 12-AC invariant.
