"""Tier 0 contract: `thinking_resolver.resolve()` `source` enum
exhaustiveness.

The set of values `resolve()` returns in `source` must be exactly the
documented five-value enum:

    {"claude-effort-env", "env", "explicit", "role", "default"}

Any drift in either direction is a contract break — observation records
written by `pre-agent-thinking.sh` are routed by the `source` field, and
downstream consumers (`/forensics`, observation-capture in Reflect,
`/eval-model-effectiveness`) interpret it as a closed enum even when no
strict validator is in place today.

This contract is exercised by exhaustive parametrised inputs that drive
each source layer in turn.
"""
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_LIB = REPO_ROOT / "hooks" / "_lib"
if str(HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(HOOKS_LIB))

from thinking_resolver import resolve  # noqa: E402

EXPECTED_SOURCES = {
    "claude-effort-env",
    "env",
    "explicit",
    "role",
    "default",
}


class SourceEnumIncludesClaudeEffortEnvAndPreservesExisting(unittest.TestCase):
    def test_source_enum_includes_claude_effort_env_and_preserves_existing(
        self,
    ):
        observed = set()

        # Layer "default": no env, no explicit, no role rule fires.
        observed.add(resolve(tool_input={}, env={}, state={})["source"])

        # Layer "role": planning-agent downgrade to low.
        observed.add(
            resolve(
                tool_input={"subagent_type": "planning-agent"},
                env={},
                state={},
            )["source"]
        )

        # Layer "explicit": tool_input.thinking.effort.
        observed.add(
            resolve(
                tool_input={"thinking": {"effort": "low"}},
                env={},
                state={},
            )["source"]
        )

        # Layer "env": CLAUDE_THINKING_EFFORT.
        observed.add(
            resolve(
                tool_input={},
                env={"CLAUDE_THINKING_EFFORT": "high"},
                state={},
            )["source"]
        )

        # Layer "claude-effort-env": CLAUDE_EFFORT (rule 2a, the new tier).
        observed.add(
            resolve(
                tool_input={},
                env={"CLAUDE_EFFORT": "low"},
                state={},
            )["source"]
        )

        self.assertEqual(
            observed,
            EXPECTED_SOURCES,
            (
                "thinking_resolver.resolve() source enum drift.\n"
                f"  expected: {sorted(EXPECTED_SOURCES)}\n"
                f"  observed: {sorted(observed)}\n"
                "If the enum genuinely needs to change, update this "
                "contract test AND rules/_detail/thinking-defaults.md "
                "Forensic / Source-Field Integration Note in the same PR."
            ),
        )


if __name__ == "__main__":
    unittest.main()
