---
name: your-agent-name
description: "One sentence: role + when the orchestrator spawns this agent."
tools:
  - Read
  - Grep
  - Glob
model: sonnet
maxTurns: 60
# Optional fields — uncomment as needed:
# instinct_categories:
#   - software-engineer
# disallowedTools:
#   - Agent
#   - Write
---

# Your Agent Name

Brief description of the agent's role and responsibilities.

## Responsibilities

- First responsibility
- Second responsibility
- Third responsibility

## Standards

- Key standard this agent enforces
- Another key standard

## Output Format

Describe what this agent produces: a file, a verdict, a recommendation.

---
# WHY: CLAUDE.md Agent-Team table and README agent count must stay in sync.
# Running `scripts/new-agent.sh` keeps both in sync automatically.
# If you add this file manually, also:
#   1. Add a row to the ### Agent Team table in CLAUDE.md (5 columns: Agent|Phase|Worktree|Default Model|Tunable)
#   2. Update the agent count in README.md line that reads "# N specialized agent"
# Then run: pytest -k "agent_table or counts_match" -q
