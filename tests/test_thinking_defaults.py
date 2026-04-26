"""Thinking-defaults resolver tests (incremental TDD)."""
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from pipeline_frontmatter import coerce_state, parse_frontmatter
from pipeline_state import read_active_state
from thinking_resolver import resolve

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "pre-agent-thinking.sh"


def _run_hook(payload, env=None):
    proc_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _write_state(dirpath, task_id, body):
    path = Path(dirpath) / f"{task_id}-pipeline.md"
    path.write_text(body)
    return path


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


class EnvEffortOverridesAll(unittest.TestCase):
    def test_env_effort_overrides_all(self):
        explicit = {"thinking": {"effort": "low"}}
        env = {"CLAUDE_THINKING_EFFORT": "high"}
        result = resolve(tool_input=explicit, env=env, state={})
        self.assertEqual(result["effort"], "high")


class InvalidEnvValueFallsBack(unittest.TestCase):
    def test_invalid_env_value_falls_back(self):
        env = {"CLAUDE_THINKING_EFFORT": "banana"}
        result = resolve(tool_input={}, env=env, state={})
        self.assertEqual(result["effort"], "high")


class PipelineStateDirEnvRedirect(unittest.TestCase):
    def test_pipeline_state_dir_env_redirect(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "redirect-test",
                         "---\ntask_id: redirect-test\nphase: build\ncritical: true\n---\n")
            with patch.dict(os.environ, {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertEqual(state["task_id"], "redirect-test")
            self.assertTrue(state["critical"])


class MissingPipelineStateDirIsSafe(unittest.TestCase):
    def test_missing_pipeline_state_dir_is_safe(self):
        missing = "/tmp/definitely-does-not-exist-nope-zzz"
        with patch.dict(os.environ, {"CLAUDE_PIPELINE_STATE_DIR": missing}, clear=True):
            state = read_active_state()
        self.assertEqual(state["task_id"], "")
        self.assertFalse(state["critical"])


class ArchitectCriticalOrBudget7YieldsXhigh(unittest.TestCase):
    def test_architect_critical_or_budget_7_yields_xhigh(self):
        tool_input = {"subagent_type": "architect"}
        state = {"critical": True, "budget": 5}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "xhigh")


class SecurityEngineerXhighOnCriticalAndBudget(unittest.TestCase):
    def test_security_engineer_xhigh_on_critical_and_budget(self):
        tool_input = {"subagent_type": "security-engineer"}
        state = {"critical": True, "budget": 7}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "xhigh")


class SecurityEngineerHighOnNormal(unittest.TestCase):
    def test_security_engineer_high_on_normal(self):
        tool_input = {"subagent_type": "security-engineer"}
        state = {"critical": False, "budget": 5}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "high")


class CodeReviewerHighDefault(unittest.TestCase):
    def test_code_reviewer_high_default(self):
        tool_input = {"subagent_type": "code-reviewer"}
        result = resolve(tool_input=tool_input, env={}, state={"critical": True, "budget": 12})
        self.assertEqual(result["effort"], "high")


class QaEngineerHighDefault(unittest.TestCase):
    def test_qa_engineer_high_default(self):
        tool_input = {"subagent_type": "qa-engineer"}
        result = resolve(tool_input=tool_input, env={}, state={"critical": True, "budget": 12})
        self.assertEqual(result["effort"], "high")


class CriticalBudget7DoesNotChangeEngineerEffort(unittest.TestCase):
    def test_critical_budget_7_does_not_change_engineer_effort(self):
        tool_input = {"subagent_type": "software-engineer"}
        state = {"critical": True, "budget": 7}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "high")


class NonCriticalBudget10StaysDefault(unittest.TestCase):
    def test_non_critical_budget_10_stays_default(self):
        tool_input = {"subagent_type": "software-engineer"}
        state = {"critical": False, "budget": 10}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "high")


class ArchitectBelowThresholdHigh(unittest.TestCase):
    def test_architect_below_threshold_high(self):
        tool_input = {"subagent_type": "architect"}
        state = {"critical": False, "budget": 6}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "high")


class BestOfNCandidateXhigh(unittest.TestCase):
    def test_best_of_n_candidate_xhigh(self):
        tool_input = {"subagent_type": "software-engineer", "name": "boN-opus"}
        state = {"critical": True, "budget": 8}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "xhigh")


class BestOfNCandidateLowBudgetHigh(unittest.TestCase):
    def test_best_of_n_candidate_low_budget_high(self):
        tool_input = {"subagent_type": "software-engineer", "name": "boN-opus"}
        state = {"critical": True, "budget": 5}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "high")


class DebugStateFileTriggersTextDisplay(unittest.TestCase):
    def test_debug_state_file_triggers_text_display(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "fix-me",
                         "---\ntask_id: fix-me\nphase: build\n---\n")
            (Path(tmp) / "fix-me-debug.md").write_text("debug notes")
            with patch.dict(os.environ, {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            result = resolve(tool_input={}, env={}, state=state)
        self.assertEqual(result["display"], "text")

    def test_debug_mention_in_prompt_does_not_trigger_text(self):
        result = resolve(
            tool_input={"prompt": "see skills/debug/SKILL.md for context"},
            env={}, state={"debug_active": False})
        self.assertEqual(result["display"], "omitted")


class DebugFrontmatterTriggersTextDisplay(unittest.TestCase):
    def test_debug_frontmatter_triggers_text_display(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "live-debug",
                         "---\ntask_id: live-debug\nphase: debugging\n---\n")
            with patch.dict(os.environ, {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            result = resolve(tool_input={}, env={}, state=state)
        self.assertTrue(state["debug_active"])
        self.assertEqual(result["display"], "text")


class SoftwareEngineerCriticalBudget10YieldsHighNotXhigh(unittest.TestCase):
    def test_software_engineer_critical_budget_10_yields_high_not_xhigh(self):
        tool_input = {"subagent_type": "software-engineer"}
        state = {"critical": True, "budget": 10}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "high")


class MalformedBudgetCoercesToZero(unittest.TestCase):
    def test_non_numeric_budget_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "bad-budget",
                         "---\ntask_id: bad-budget\nphase: build\nbudget: abc\n---\n")
            with patch.dict(os.environ, {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertEqual(state["budget"], 0)


class MultiplePipelineFilesPickNewestByMtime(unittest.TestCase):
    def test_newer_pipeline_file_wins_over_older(self):
        with tempfile.TemporaryDirectory() as tmp:
            older = _write_state(tmp, "aaa-older",
                                 "---\ntask_id: aaa-older\nphase: build\n---\n")
            newer = _write_state(tmp, "zzz-newer",
                                 "---\ntask_id: zzz-newer\nphase: review\n---\n")
            os.utime(older, (1_000_000, 1_000_000))
            os.utime(newer, (2_000_000, 2_000_000))
            with patch.dict(os.environ, {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertEqual(state["task_id"], "zzz-newer")


class SourceFieldReportsWinningLayer(unittest.TestCase):
    def test_env_win_reports_env_source(self):
        env = {"CLAUDE_THINKING_EFFORT": "low"}
        result = resolve(tool_input={}, env=env, state={})
        self.assertEqual(result["source"], "env")

    def test_role_win_reports_role_source(self):
        tool_input = {"subagent_type": "architect"}
        state = {"critical": True, "budget": 5}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["source"], "role")

    def test_explicit_win_reports_explicit_source(self):
        result = resolve(tool_input={"thinking": {"effort": "low"}}, env={}, state={})
        self.assertEqual(result["source"], "explicit")

    def test_default_win_reports_default_source(self):
        result = resolve(tool_input={}, env={}, state={})
        self.assertEqual(result["source"], "default")


RESOLVER_SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "_lib" / "resolve-thinking.py"


def _run_resolver(payload):
    return subprocess.run(
        ["python3", str(RESOLVER_SCRIPT)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10)


class ResolverEmitsDecisionLine(unittest.TestCase):
    def test_agent_without_thinking_emits_log(self):
        result = _run_resolver({"tool_name": "Agent", "tool_input": {}})
        self.assertEqual(result.returncode, 0)
        first, second = result.stdout.strip().splitlines()
        self.assertEqual(first, "LOG")
        json.loads(second)  # second line is valid JSON

    def test_non_agent_emits_skip(self):
        result = _run_resolver({"tool_name": "Bash", "tool_input": {}})
        first = result.stdout.strip().splitlines()[0]
        self.assertEqual(first, "SKIP")

    def test_agent_with_thinking_emits_skip(self):
        payload = {"tool_name": "Agent",
                   "tool_input": {"thinking": {"effort": "high"}}}
        result = _run_resolver(payload)
        first = result.stdout.strip().splitlines()[0]
        self.assertEqual(first, "SKIP")


class HookLogsOnlyDoesNotBlock(unittest.TestCase):
    def test_missing_thinking_exits_zero_no_block_stderr(self):
        result = _run_hook({"tool_name": "Agent", "tool_input": {}})
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("BLOCKED:", result.stderr)

    def test_non_agent_tool_exits_zero(self):
        result = _run_hook({"tool_name": "Bash", "tool_input": {}})
        self.assertEqual(result.returncode, 0)

    def test_missing_thinking_writes_log_line(self):
        session = f"test-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "hook-injections.jsonl"
        try:
            result = _run_hook(
                {"tool_name": "Agent", "tool_input": {"subagent_type": "architect"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            self.assertTrue(log_path.exists(), f"expected log at {log_path}")
            line = log_path.read_text().strip().splitlines()[-1]
            entry = json.loads(line)
            self.assertEqual(entry["agent_role"], "architect")
            self.assertIn("effort", entry["resolved"])
        finally:
            if log_path.exists():
                log_path.unlink()
            log_path.parent.rmdir() if log_path.parent.exists() else None


class CoerceStateTaskClassAndBestofnRoundTrip(unittest.TestCase):
    def test_explicit_feature_and_bestofn_true(self):
        body = "---\ntask_id: t\nphase: build\ntask_class: feature\nbestofn: true\n---\n"
        state = coerce_state(parse_frontmatter(body), False)
        self.assertEqual(state["task_class"], "feature")
        self.assertIs(state["bestofn"], True)

    def test_missing_keys_default_to_empty_and_false(self):
        body = "---\ntask_id: t\nphase: build\n---\n"
        state = coerce_state(parse_frontmatter(body), False)
        self.assertEqual(state["task_class"], "")
        self.assertIs(state["bestofn"], False)

    def test_capital_true_coerces_to_true(self):
        body = "---\ntask_id: t\nbestofn: True\n---\n"
        state = coerce_state(parse_frontmatter(body), False)
        self.assertIs(state["bestofn"], True)

    def test_yes_coerces_to_true(self):
        body = "---\ntask_id: t\nbestofn: yes\n---\n"
        state = coerce_state(parse_frontmatter(body), False)
        self.assertIs(state["bestofn"], True)

    def test_critical_without_bestofn_key_defaults_false(self):
        body = "---\ntask_id: t\ncritical: true\nbudget: 8\n---\n"
        state = coerce_state(parse_frontmatter(body), False)
        self.assertIs(state["bestofn"], False)
        self.assertIs(state["critical"], True)


class ReadActiveStateBestofnRoundTrip(unittest.TestCase):
    def test_pipeline_with_bestofn_true_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "bon-on",
                         "---\ntask_id: bon-on\nphase: build\nbestofn: true\n---\n")
            with patch.dict(os.environ, {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertIs(state["bestofn"], True)

    def test_pipeline_without_bestofn_defaults_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "bon-off",
                         "---\ntask_id: bon-off\nphase: build\n---\n")
            with patch.dict(os.environ, {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertIs(state["bestofn"], False)


if __name__ == "__main__":
    unittest.main()
