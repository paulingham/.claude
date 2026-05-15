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
import subprocess
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


def _run_hook(payload, env=None):
    proc_env = {k: v for k, v in os.environ.items()
                if k not in _RESOLVER_ENV_VARS}
    proc_env.update(env or {})
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _cleanup_session(session):
    log_path = (Path.home() / ".claude" / "metrics" / session
                / "hook-injections.jsonl")
    if log_path.exists():
        log_path.unlink()
    parent = log_path.parent
    if parent.exists():
        try:
            parent.rmdir()
        except OSError:
            pass


def _last_entry(session):
    log_path = (Path.home() / ".claude" / "metrics" / session
                / "hook-injections.jsonl")
    return json.loads(log_path.read_text().strip().splitlines()[-1])


class HookInjectionsJsonlEmitsEffortField(unittest.TestCase):
    """B.2 verify-only: the existing JSONL line carries `resolved.effort`
    drawn from `{low, medium, high, xhigh}` AND a non-empty
    `resolved.source` token.
    """

    def test_jsonl_emits_effort_field(self):
        session = f"test-{uuid.uuid4()}"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            entry = _last_entry(session)
            self.assertIn(entry["resolved"]["effort"],
                          {"low", "medium", "high", "xhigh"})
            self.assertNotEqual(entry["resolved"]["source"], "")
        finally:
            _cleanup_session(session)


class JsonlEmitsBetaHeaderToken(unittest.TestCase):
    """B.4: when effort is in `{medium, high, xhigh}` (or `low` for an
    effort-enabled role), `resolved.beta_header == "effort-2025-11-24"`
    AND `resolved.api_effort` is set to the resolved effort.

    Effort `low` resolved via the role layer for planning-agent IS treated
    as "role disables effort" — see the sibling
    `BetaHeaderOmittedWhenRoleDisablesEffort` test. For other roles low
    via env-override remains effort-enabled — the beta header still ships
    so the API has the necessary capability.
    """

    def test_jsonl_emits_beta_header_for_architect(self):
        session = f"test-{uuid.uuid4()}"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "architect"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            entry = _last_entry(session)
            self.assertEqual(entry["resolved"]["beta_header"],
                             "effort-2025-11-24")
            self.assertIn(entry["resolved"]["api_effort"],
                          {"low", "medium", "high", "xhigh"})
        finally:
            _cleanup_session(session)


class BetaHeaderOmittedWhenRoleDisablesEffort(unittest.TestCase):
    """B.4: planning-agent resolves to `effort=low` via role layer rule 3b
    — the role disables effort. `resolved.beta_header` is ABSENT (field
    not present at all, not null) in the JSONL line for this spawn.

    The semantic: a `low` floor from the role-disable downgrade signals
    that the role does not want extended-thinking budget at all; emitting
    the beta header would request capability the role explicitly opts out
    of.
    """

    def test_planning_agent_omits_beta_header(self):
        session = f"test-{uuid.uuid4()}"
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "planning-agent"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            entry = _last_entry(session)
            self.assertNotIn("beta_header", entry["resolved"],
                             "beta_header must be absent for low-effort "
                             "role-disable spawns (planning-agent)")
        finally:
            _cleanup_session(session)


if __name__ == "__main__":
    unittest.main()
