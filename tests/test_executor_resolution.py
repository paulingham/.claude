"""B6-AC8: behavioral test for CLAUDE_FORCE_OPUS=1 env override.

Verifies the executor resolver returns the GA Opus (via resolve_model_alias("strong"))
when the env var is set, regardless of frontmatter, and falls through to the frontmatter
value when the env var is absent.
"""
import unittest

from executor_resolver import resolve_executor
from model_alias import resolve_model_alias


class ForceOpusEnvOverridesFrontmatter(unittest.TestCase):
    def test_claude_force_opus_env_yields_opus_regardless_of_frontmatter(self):
        env = {"CLAUDE_FORCE_OPUS": "1"}
        frontmatter = {"executor": "claude-sonnet-4-6"}
        self.assertEqual(
            resolve_executor("software-engineer", env, frontmatter),
            resolve_model_alias("strong"))

    def test_absent_env_falls_through_to_frontmatter(self):
        env = {}
        frontmatter = {"executor": "claude-sonnet-4-6"}
        self.assertEqual(
            resolve_executor("software-engineer", env, frontmatter),
            "claude-sonnet-4-6")


if __name__ == "__main__":
    unittest.main()
