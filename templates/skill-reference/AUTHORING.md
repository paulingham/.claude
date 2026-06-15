# Authoring a Reference Skill

A reference (clean-code) skill is the simplest contributor surface.
It documents a reusable technique or guide without wiring into the pipeline phases.

## Frontmatter Contract

Reference skills use ONLY two fields:

```yaml
---
name: "your-skill-name-kebab-case"
description: "One sentence explaining when to use it."
---
```

Do NOT add `verdict`, `phase`, or `dispatch`. Those fields are for pipeline skills
maintained by the harness team. Adding them will cause CI to expect a new row in
`verdict-catalog.md` and break the build.

## File Placement

Skills live under `skills/<your-skill-name>/SKILL.md`. The scaffolding script
handles this for you:

```bash
bash scripts/new-skill.sh my-naming-tips
```

This copies `templates/skill-reference/SKILL.md` into the right location,
bumps the README skill count, and stages the specific files.

## README Count

The `## Skills (N)` heading in README.md must match the filesystem count.
Running `new-skill.sh` keeps this in sync. If you create the file manually,
bump the heading yourself and run the scoped pytest to verify:

```bash
pytest -k "counts_match or readme" -q
```

## Before Opening a PR

Run both of the following from the repo root:

```bash
bash tests/shell/run.sh
pytest -k "readme or verdict or catalog or inventory or stop_hook or counts_match or agent_table or registration"
```

See CONTRIBUTING.md for the full contributor workflow.
