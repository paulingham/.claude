---
name: No Explore or general-purpose agents
description: Never use Explore or general-purpose agents — always use specialized agent types that match the task domain
type: feedback
---

Never use Explore or general-purpose agents for any task. Always use the specialized agent type that matches the task domain.

**Why:** The user explicitly corrected this on 2026-03-19. Explore agents lack domain context and engineering rules. The orchestrator should coordinate, not research. Every task has a specialized agent type better suited.

**How to apply:** For research/analysis tasks, use architect (for design/analysis), code-reviewer (for code quality analysis), or claude-code-guide (for Claude Code feature research). For codebase exploration that feeds into a decision, delegate to the agent who will act on the findings. Never default to Explore or general-purpose.
