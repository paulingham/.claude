"""Executor resolver: env override → frontmatter (Wave 5/B6).

Precedence chain at orchestrator spawn time:
  1. CLAUDE_FORCE_OPUS=1 env (operator override) → resolves the `strong` alias → GA Opus via SSOT
  2. prefer_opus: true instinct match — DEFERRED to next learning slice (B6.3)
  3. Frontmatter `executor:` field (default — Sonnet for SE/FE since Wave 5)
"""
from model_alias import resolve_model_alias


def resolve_executor(role, env, frontmatter):
    if env.get("CLAUDE_FORCE_OPUS") == "1":
        return resolve_model_alias("strong")
    return frontmatter.get("executor")
