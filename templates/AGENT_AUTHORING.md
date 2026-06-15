# Authoring an Agent

Adding a new agent is a GATED path — it requires maintainer review because agents
affect the CLAUDE.md Agent-Team table and the README agent count, both of which
are CI-pinned. Use the scaffolding script to handle the wiring:

```bash
bash scripts/new-agent.sh my-new-agent
```

## Frontmatter Contract

Required fields (see `templates/agent-template.md`):

| Field | Type | Example |
|---|---|---|
| `name` | string | `my-new-agent` |
| `description` | string | one sentence, when to spawn |
| `tools` | list | `[Read, Grep, Write]` |
| `model` | string | `sonnet` or `opus` |
| `maxTurns` | integer | `60` |

Optional fields: `instinct_categories`, `disallowedTools`, `executor`, `advisor`.

## Multi-File Wiring

Every agent addition requires THREE coordinated changes:

1. `agents/<your-agent>.md` — the agent definition file
2. `CLAUDE.md` `### Agent Team` table — a new 5-column row
3. `README.md` — bump the agent count in the `# N specialized agent` comment

Running `scripts/new-agent.sh` proposes and applies all three changes after
a dry-run preview and confirmation.

## CI Guards

The following tests pin the agent count and table shape:

- `tests/test_claude_md_agent_table.py` — agent-table rows == agent files; 5-col shape
- `tests/test_thinking_defaults.py` — README count matches filesystem

Run before pushing:

```bash
pytest -k "agent_table or counts_match" -q
bash tests/shell/run.sh
```

## Model Selection

- `sonnet` — standard build/review work
- `opus` — plan, security, infrastructure (expensive — justify in a comment)

See `CLAUDE.md § Agent Team` for the full roster and the `[1]` footnote on
advisor-mode pairing.
