"""B6-AC8: behavioral test for CLAUDE_FORCE_OPUS=1 env override.

Verifies the executor resolver returns claude-opus-4-5-20251101 when the env
var is set, regardless of frontmatter, and falls through to the frontmatter
value when the env var is absent. Slice-A migration target.
"""
import unittest

from executor_resolver import resolve_executor


class ForceOpusEnvOverridesFrontmatter(unittest.TestCase):
    def test_claude_force_opus_env_yields_opus_regardless_of_frontmatter(self):
        env = {"CLAUDE_FORCE_OPUS": "1"}
        frontmatter = {"executor": "claude-sonnet-4-6"}
        self.assertEqual(
            resolve_executor("software-engineer", env, frontmatter),
            "claude-opus-4-5-20251101")

    def test_absent_env_falls_through_to_frontmatter(self):
        env = {}
        frontmatter = {"executor": "claude-sonnet-4-6"}
        self.assertEqual(
            resolve_executor("software-engineer", env, frontmatter),
            "claude-sonnet-4-6")

    def test_fallback_returns_opus_4_5(self):
        """Slice-A AC.2 — CLAUDE_FORCE_OPUS escape hatch returns the migrated 4.5 id."""
        env = {"CLAUDE_FORCE_OPUS": "1"}
        frontmatter = {"executor": "claude-haiku-4-5"}
        self.assertEqual(
            resolve_executor("planning-agent", env, frontmatter),
            "claude-opus-4-5-20251101")


if __name__ == "__main__":
    unittest.main()
