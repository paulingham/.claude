"""Advisor-mode reviews resolver tests (incremental TDD).

Mirrors `tests/test_thinking_defaults.py` shape: precedence-by-precedence
RED-GREEN cycle, then stdin-script smoke, then bash-wrapper smoke. The
resolver itself is pure (no I/O) — see `hooks/_lib/advisor_resolver.py`.
"""
import inspect
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

import advisor_resolver
from advisor_resolver import parse_frontmatter, resolve

RESOLVER_SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "_lib" / "resolve-advisor.py"
HOOK = Path(__file__).resolve().parents[1] / "hooks" / "pre-agent-advisor.sh"


def _run_resolver(payload, env=None):
    proc_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["python3", str(RESOLVER_SCRIPT)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _run_hook(payload, env=None):
    proc_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


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


class ResolverDocumentsRuntimeUnavailabilityFutureState(unittest.TestCase):
    """Slice 7 guard — the future-state runtime-advisor-unavailable contract
    must survive refactors. Asserts the docstring marker is present AND no
    code path today returns that fallback_reason."""

    def test_resolver_docstring_contains_runtime_marker(self):
        self.assertIn("runtime-advisor-unavailable", resolve.__doc__)

    def test_no_code_path_returns_runtime_unavailable_today(self):
        source = inspect.getsource(advisor_resolver)
        # The marker may appear in the docstring; assert it does NOT appear in
        # any return-statement string literal (no live code path returns it).
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("return") or stripped.startswith("_solo("):
                self.assertNotIn("runtime-advisor-unavailable", stripped)


class ResolverIgnoresNonReviewerAgents(unittest.TestCase):
    def test_resolver_ignores_non_reviewer_agents(self):
        # software-engineer frontmatter only has model: opus, no executor/advisor
        tool_input = {"subagent_type": "software-engineer"}
        env = {"ANTHROPIC_API_KEY": "sk-test"}
        frontmatter = {"model": "opus"}
        result = resolve(tool_input=tool_input, env=env, frontmatter=frontmatter)
        # Falls through to no-pairing-frontmatter (NOT env-disabled, NOT no-api-key)
        self.assertIsNone(result["executor"])
        self.assertEqual(result["fallback_reason"], "no-pairing-frontmatter")
        self.assertEqual(result["source"], "no-pairing-frontmatter")


class ResolverRespectsMissingApiKey(unittest.TestCase):
    def test_resolver_respects_missing_api_key(self):
        tool_input = {"subagent_type": "code-reviewer"}
        env = {}  # ANTHROPIC_API_KEY absent
        frontmatter = {
            "model": "opus",
            "executor": "claude-sonnet-4-6",
            "advisor": "claude-opus-4-7",
        }
        result = resolve(tool_input=tool_input, env=env, frontmatter=frontmatter)
        self.assertIsNone(result["executor"])
        self.assertIsNone(result["advisor"])
        self.assertEqual(result["fallback_reason"], "no-api-key")
        self.assertEqual(result["source"], "no-api-key")


class ResolverRespectsEnvDisabled(unittest.TestCase):
    def test_resolver_respects_env_disabled(self):
        tool_input = {"subagent_type": "code-reviewer"}
        env = {"ANTHROPIC_API_KEY": "sk-test", "CLAUDE_REVIEW_ADVISOR_DISABLED": "1"}
        frontmatter = {
            "model": "opus",
            "executor": "claude-sonnet-4-6",
            "advisor": "claude-opus-4-7",
        }
        result = resolve(tool_input=tool_input, env=env, frontmatter=frontmatter)
        self.assertIsNone(result["executor"])
        self.assertIsNone(result["advisor"])
        self.assertEqual(result["fallback_reason"], "env-disabled")
        self.assertEqual(result["source"], "env-disabled")


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


class StdinScriptEmitsDecisionAndResolved(unittest.TestCase):
    def test_stdin_script_emits_decision_and_resolved(self):
        payload = {"tool_name": "Agent",
                   "tool_input": {"subagent_type": "code-reviewer"}}
        result = _run_resolver(payload, env={"ANTHROPIC_API_KEY": "sk-test"})
        self.assertEqual(result.returncode, 0)
        first, second = result.stdout.strip().splitlines()
        self.assertIn(first, {"LOG", "SKIP"})
        json.loads(second)  # second line is valid JSON

    def test_non_agent_emits_skip(self):
        result = _run_resolver({"tool_name": "Bash", "tool_input": {}})
        first = result.stdout.strip().splitlines()[0]
        self.assertEqual(first, "SKIP")


class HookLogsToJsonlOnReviewerSpawn(unittest.TestCase):
    def test_hook_logs_to_jsonl_on_reviewer_spawn(self):
        session = f"test-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "advisor-dispatch.jsonl"
        try:
            result = _run_hook(
                {"tool_name": "Agent", "tool_input": {"subagent_type": "code-reviewer"}},
                env={"CLAUDE_SESSION_ID": session, "ANTHROPIC_API_KEY": "sk-test"})
            self.assertEqual(result.returncode, 0)
            self.assertTrue(log_path.exists(), f"expected log at {log_path}")
            line = log_path.read_text().strip().splitlines()[-1]
            entry = json.loads(line)
            self.assertEqual(entry["agent_role"], "code-reviewer")
            self.assertIn("source", entry)
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()

    def test_hook_exits_zero_on_non_agent(self):
        result = _run_hook({"tool_name": "Bash", "tool_input": {}})
        self.assertEqual(result.returncode, 0)

    def test_hook_never_blocks_even_when_advisor_disabled(self):
        result = _run_hook(
            {"tool_name": "Agent", "tool_input": {"subagent_type": "code-reviewer"}},
            env={"CLAUDE_REVIEW_ADVISOR_DISABLED": "1"})
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
