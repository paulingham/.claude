"""Unit tests for resolve-instincts entry script.

Subprocess end-to-end coverage lives in test_instinct_hook.py. This module
exercises the in-process functions (`_agent_input`, `_handle_agent_spawn`)
to lock in the Path-B contract that the hook ALWAYS writes source='logged'
and never forges 'orchestrator-injected' (which is reserved for the
orchestrator caller after a real prompt splice).
"""
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

_SPEC_PATH = Path(__file__).resolve().parents[1] / "hooks" / "_lib" / "resolve-instincts.py"
_spec = importlib.util.spec_from_file_location("_resolve_instincts", _SPEC_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


class HandleAgentSpawnAlwaysWritesLogged(unittest.TestCase):
    """Path-B contract: hook NEVER writes source='orchestrator-injected'."""

    def test_writes_logged_even_when_kept_is_positive(self):
        payload = {"tool_name": "Agent",
                   "tool_input": {"subagent_type": "software-engineer"}}
        with mock.patch.object(_mod, "load_agent_instinct_categories",
                               return_value=["testing"]), \
             mock.patch.object(_mod, "load_instincts", return_value=[]), \
             mock.patch.object(_mod, "resolve_for_agent",
                               return_value="- [test] always assert\n"), \
             mock.patch.object(_mod, "project_hash", return_value="local"), \
             mock.patch.object(_mod, "write_log") as wl:
            _mod._handle_agent_spawn(payload, "software-engineer")
        self.assertEqual(wl.call_args.args[1], "logged")
        self.assertGreaterEqual(wl.call_args.args[2]["count_kept"], 1)


class AgentInputRejectsNonAgent(unittest.TestCase):
    def test_returns_none_for_bash_tool(self):
        self.assertIsNone(_mod._agent_input({"tool_name": "Bash",
                                             "tool_input": {}}))


if __name__ == "__main__":
    unittest.main()
