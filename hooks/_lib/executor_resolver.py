"""Executor resolver: env override → frontmatter (Wave 5/B6).

Precedence chain at orchestrator spawn time:
  1. CLAUDE_FORCE_OPUS=1 env (operator override, session-scoped)
  2. prefer_opus: true instinct match — DEFERRED to next learning slice (B6.3)
  3. Frontmatter `executor:` field (default — Sonnet for SE/FE since Wave 5)
"""


def resolve_executor(role, env, frontmatter):
    if env.get("CLAUDE_FORCE_OPUS") == "1":
        return "claude-opus-4-5-20251101"
    return frontmatter.get("executor")
