"""Hook-injection JSONL schema tests (Slice B, AC B.2 + B.4).

B.2 (verify-only): the existing hook emits `resolved.effort` and
`resolved.source` per spawn. B.4 (NEW): `resolved.beta_header` MUST carry
the literal `effort-2025-11-24` when effort is one of `{low, medium, high,
xhigh}` AND the role does not disable effort. `resolved.api_effort` MUST
mirror the resolved effort value. When the role disables effort (e.g.
planning-agent on `low`), `beta_header` SHOULD be absent (field not
present, not null).

Backward compat: tests probe field presence, not exhaustive schema. New
consumers can read these fields; older consumers ignore them.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "pre-agent-thinking.sh"

_RESOLVER_ENV_VARS = (
    "CLAUDE_THINKING_EFFORT",
    "CLAUDE_THINKING_DISPLAY",
    "CLAUDE_EFFORT",
    "CLAUDE_DEBUG_DISPLAY_TTL",
)


_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _run_hook(payload, env=None, plugin_data=None):
    proc_env = {k: v for k, v in os.environ.items()
                if k not in _RESOLVER_ENV_VARS}
    existing_pp = proc_env.get("PYTHONPATH", "")
    proc_env["PYTHONPATH"] = ":".join(filter(None, [_SITE_PP, existing_pp]))
    proc_env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    # GP-P1-01: resolvers short-circuit by default; force the python path so the
    # resolver-jsonl assertions below still exercise it.
    proc_env["CLAUDE_AGENT_INJECTION_FORCE"] = "1"
    if plugin_data is not None:
        proc_env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
        proc_env["HOME"] = str(plugin_data)
    proc_env.update(env or {})
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _cleanup_session(session, base):
    root = base
    log_path = root / "metrics" / session / "hook-injections.jsonl"
    if log_path.exists():
        log_path.unlink()
    parent = log_path.parent
    if parent.exists():
        try:
            parent.rmdir()
        except OSError:
            pass


def _last_entry(session, base):
    root = base
    log_path = root / "metrics" / session / "hook-injections.jsonl"
    return json.loads(log_path.read_text().strip().splitlines()[-1])


class _InjectionTestCase(unittest.TestCase):
    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="injection-test-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def _run(self, payload, extra_env=None):
        return _run_hook(payload, env=extra_env, plugin_data=self.plugin_data)

    def _last(self, session):
        return _last_entry(session, base=self.plugin_data)

    def _cleanup(self, session):
        _cleanup_session(session, base=self.plugin_data)


class HookInjectionsJsonlEmitsEffortField(_InjectionTestCase):
    """B.2 verify-only: the existing JSONL line carries `resolved.effort`."""

    def test_jsonl_emits_effort_field(self):
        session = f"test-{uuid.uuid4()}"
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer"}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 0)
        entry = self._last(session)
        self.assertIn(entry["resolved"]["effort"],
                      {"low", "medium", "high", "xhigh"})
        self.assertNotEqual(entry["resolved"]["source"], "")


class JsonlEmitsBetaHeaderToken(_InjectionTestCase):
    """B.4: beta_header field present for effort-enabled roles."""

    def test_jsonl_emits_beta_header_for_architect(self):
        session = f"test-{uuid.uuid4()}"
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "architect"}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 0)
        entry = self._last(session)
        self.assertEqual(entry["resolved"]["beta_header"], "effort-2025-11-24")
        self.assertIn(entry["resolved"]["api_effort"],
                      {"low", "medium", "high", "xhigh"})


class BetaHeaderOmittedWhenRoleDisablesEffort(_InjectionTestCase):
    """B.4: planning-agent omits beta_header."""

    def test_planning_agent_omits_beta_header(self):
        session = f"test-{uuid.uuid4()}"
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "planning-agent"}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 0)
        entry = self._last(session)
        self.assertNotIn("beta_header", entry["resolved"],
                         "beta_header must be absent for planning-agent")


if __name__ == "__main__":
    unittest.main()
