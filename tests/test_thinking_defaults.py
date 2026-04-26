"""Thinking-defaults resolver tests (incremental TDD)."""
import unittest
from unittest.mock import patch

from thinking_resolver import resolve


class DefaultEffortIsHigh(unittest.TestCase):
    def test_default_effort_is_high(self):
        with patch.dict("os.environ", {}, clear=True):
            result = resolve(tool_input={}, env={}, state={})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["display"], "omitted")


class ExplicitInputWinsOverDefault(unittest.TestCase):
    def test_explicit_input_wins_over_default(self):
        explicit = {"thinking": {"effort": "low"}}
        result = resolve(tool_input=explicit, env={}, state={})
        self.assertEqual(result["effort"], "low")


class EnvDisplayOverridesAll(unittest.TestCase):
    def test_env_display_overrides_all(self):
        explicit = {"thinking": {"display": "omitted"}}
        env = {"CLAUDE_THINKING_DISPLAY": "text"}
        result = resolve(tool_input=explicit, env=env, state={})
        self.assertEqual(result["display"], "text")


if __name__ == "__main__":
    unittest.main()
