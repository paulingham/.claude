"""Advisor-mode reviews resolver tests (incremental TDD).

Mirrors `tests/test_thinking_defaults.py` shape: precedence-by-precedence
RED-GREEN cycle, then stdin-script smoke, then bash-wrapper smoke. The
resolver itself is pure (no I/O) — see `hooks/_lib/advisor_resolver.py`.
"""
import unittest

from advisor_resolver import parse_frontmatter, resolve


_INLINE_REVIEWER_FRONTMATTER = """---
name: code-reviewer
description: example
tools:
  - Read
model: opus
executor: claude-sonnet-4-6
advisor: claude-opus-4-7
---

# Code Reviewer
Body here.
"""


class ParsesFrontmatterWithExecutorAndAdvisor(unittest.TestCase):
    def test_parses_frontmatter_with_executor_and_advisor(self):
        result = parse_frontmatter(_INLINE_REVIEWER_FRONTMATTER)
        self.assertEqual(result["executor"], "claude-sonnet-4-6")
        self.assertEqual(result["advisor"], "claude-opus-4-7")
        self.assertEqual(result["model"], "opus")


class ResolverReturnsSoloWhenNoPairingInFrontmatter(unittest.TestCase):
    def test_resolver_returns_solo_when_no_pairing_in_frontmatter(self):
        tool_input = {"subagent_type": "code-reviewer"}
        env = {"ANTHROPIC_API_KEY": "sk-test"}
        frontmatter = {"model": "opus"}  # no executor, no advisor
        result = resolve(tool_input=tool_input, env=env, frontmatter=frontmatter)
        self.assertIsNone(result["executor"])
        self.assertIsNone(result["advisor"])
        self.assertEqual(result["fallback_reason"], "no-pairing-frontmatter")
        self.assertEqual(result["source"], "no-pairing-frontmatter")


class ResolverReturnsFrontmatterPairingWhenBothPresent(unittest.TestCase):
    def test_resolver_returns_frontmatter_pairing_when_both_present(self):
        tool_input = {"subagent_type": "code-reviewer"}
        env = {"ANTHROPIC_API_KEY": "sk-test"}
        frontmatter = {
            "model": "opus",
            "executor": "claude-sonnet-4-6",
            "advisor": "claude-opus-4-7",
        }
        result = resolve(tool_input=tool_input, env=env, frontmatter=frontmatter)
        self.assertEqual(result["executor"], "claude-sonnet-4-6")
        self.assertEqual(result["advisor"], "claude-opus-4-7")
        self.assertEqual(result["fallback_reason"], "")
        self.assertEqual(result["source"], "frontmatter-pairing")


if __name__ == "__main__":
    unittest.main()
