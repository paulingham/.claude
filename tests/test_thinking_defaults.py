"""Thinking-defaults resolver tests (incremental TDD)."""
import json
import os
import re
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
REPO_ROOT = Path(__file__).resolve().parents[1]


# Env vars the resolver consumes. _run_hook scrubs these from the inherited
# os.environ before applying the test's explicit env overrides, so a test
# running with an ambient `CLAUDE_EFFORT=xhigh` (or similar) cannot leak into
# subprocess invocations and confound deterministic assertions. Tests that
# WANT to set these vars pass them explicitly via the `env` arg.
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


def _write_state(dirpath, task_id, body):
    path = Path(dirpath) / f"{task_id}-pipeline.md"
    path.write_text(body)
    return path


# ---------------- AC1 / AC1b: hardcoded fallback is high ----------------


class DefaultEffortIsHigh(unittest.TestCase):
    def test_default_effort_is_high(self):
        with patch.dict("os.environ", {}, clear=True):
            result = resolve(tool_input={}, env={}, state={})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["display"], "omitted")
        self.assertEqual(result["source"], "default")


class InvalidEnvValueFallsBack(unittest.TestCase):
    def test_invalid_env_value_falls_back(self):
        env = {"CLAUDE_THINKING_EFFORT": "banana"}
        result = resolve(tool_input={}, env=env, state={})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "default")


# ---------------- AC2a–AC2f: explicit role downgrades ----------------


class CodeReviewerHighDefault(unittest.TestCase):
    def test_code_reviewer_high_default(self):
        tool_input = {"subagent_type": "code-reviewer"}
        result = resolve(tool_input=tool_input, env={},
                         state={"critical": True, "budget": 12})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")


class QaEngineerHighDefault(unittest.TestCase):
    def test_qa_engineer_high_default(self):
        tool_input = {"subagent_type": "qa-engineer"}
        result = resolve(tool_input=tool_input, env={},
                         state={"critical": True, "budget": 12})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")


class ProductReviewerHighDefault(unittest.TestCase):
    def test_product_reviewer_high_default(self):
        tool_input = {"subagent_type": "product-reviewer"}
        result = resolve(tool_input=tool_input, env={}, state={})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")


class DatabaseEngineerHighDefault(unittest.TestCase):
    def test_database_engineer_high_default(self):
        tool_input = {"subagent_type": "database-engineer"}
        result = resolve(tool_input=tool_input, env={}, state={})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")


class PatchCriticHighDefault(unittest.TestCase):
    def test_patch_critic_high_default(self):
        tool_input = {"subagent_type": "patch-critic"}
        result = resolve(tool_input=tool_input, env={}, state={})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")


class PlanningAgentLowDefault(unittest.TestCase):
    def test_planning_agent_low_default(self):
        tool_input = {"subagent_type": "planning-agent"}
        result = resolve(tool_input=tool_input, env={}, state={})
        self.assertEqual(result["effort"], "low")
        self.assertEqual(result["source"], "role")


# ---------------- AC2g–AC2i: implementation roles inherit high default ----------------


class SoftwareEngineerExplicitDowngrade(unittest.TestCase):
    def test_software_engineer_neutral_and_elevated_yield_high_role(self):
        tool_input = {"subagent_type": "software-engineer"}
        # Neutral state: explicit role downgrade to high (rule 3b).
        neutral = resolve(tool_input=tool_input, env={}, state={})
        self.assertEqual(neutral["effort"], "high")
        self.assertEqual(neutral["source"], "role")
        # Elevated: not in any promotion set; hits explicit downgrade rule 3b.
        elevated = resolve(tool_input=tool_input, env={},
                           state={"critical": True, "budget": 10})
        self.assertEqual(elevated["effort"], "high")
        self.assertEqual(elevated["source"], "role")


class FrontendEngineerExplicitDowngrade(unittest.TestCase):
    def test_frontend_engineer_neutral_yields_high_role(self):
        tool_input = {"subagent_type": "frontend-engineer"}
        result = resolve(tool_input=tool_input, env={}, state={})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")


class InfrastructureEngineerInheritsHigh(unittest.TestCase):
    def test_infrastructure_engineer_inherits_high_default(self):
        tool_input = {"subagent_type": "infrastructure-engineer"}
        result = resolve(tool_input=tool_input, env={}, state={})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "default")


# ---------------- AC3a / AC3a-bis / AC3b: architect promotion + below-threshold ----------------


class ArchitectCriticalOrBudget7YieldsXhigh(unittest.TestCase):
    def test_architect_critical_or_budget_7_yields_xhigh(self):
        tool_input = {"subagent_type": "architect"}
        state = {"critical": True, "budget": 5}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "xhigh")
        self.assertEqual(result["source"], "role")


class ArchitectNonCriticalBudget7YieldsXhigh(unittest.TestCase):
    """Locks OR semantics in `_is_xhigh`'s architect branch.

    Defends against a mutation flipping `or` to `and`. Under the mutated form,
    architect with critical=False, budget=7 falls through to default xhigh,
    yielding the same `effort` value but `source="default"` — only the source
    assertion catches the mutation.
    """

    def test_architect_non_critical_budget_7_yields_xhigh(self):
        tool_input = {"subagent_type": "architect"}
        state = {"critical": False, "budget": 7}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "xhigh")
        self.assertEqual(result["source"], "role")


class ArchitectBelowThresholdInheritsHigh(unittest.TestCase):
    def test_architect_below_threshold_inherits_high(self):
        tool_input = {"subagent_type": "architect"}
        state = {"critical": False, "budget": 6}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "default")


# ---------------- AC3c–AC3d: security-engineer promotion + downgrade ----------------


class SecurityEngineerXhighOnCriticalAndBudget(unittest.TestCase):
    def test_security_engineer_xhigh_on_critical_and_budget(self):
        tool_input = {"subagent_type": "security-engineer"}
        state = {"critical": True, "budget": 7}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "xhigh")
        self.assertEqual(result["source"], "role")


class SecurityEngineerHighOnNormal(unittest.TestCase):
    def test_security_engineer_high_on_normal(self):
        tool_input = {"subagent_type": "security-engineer"}
        state = {"critical": False, "budget": 5}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")


# ---------------- AC3e–AC3f: best-of-N candidate ----------------


class BestOfNCandidateXhigh(unittest.TestCase):
    def test_best_of_n_candidate_xhigh(self):
        tool_input = {"subagent_type": "software-engineer", "name": "boN-opus"}
        state = {"critical": True, "budget": 8}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "xhigh")
        self.assertEqual(result["source"], "role")


class BestOfNCandidateLowBudgetDowngrades(unittest.TestCase):
    def test_best_of_n_low_budget_software_engineer_downgrades_to_role(self):
        tool_input = {"subagent_type": "software-engineer", "name": "boN-opus"}
        state = {"critical": True, "budget": 5}
        result = resolve(tool_input=tool_input, env={}, state=state)
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")


# ---------------- AC4 / AC4b: env override ----------------


class EnvEffortOverridesAll(unittest.TestCase):
    def test_env_effort_overrides_all(self):
        explicit = {"thinking": {"effort": "low"}}
        env = {"CLAUDE_THINKING_EFFORT": "high"}
        result = resolve(tool_input=explicit, env=env, state={})
        self.assertEqual(result["effort"], "high")


class EnvForcesLowOnImplementationRole(unittest.TestCase):
    def test_env_forces_low_overrides_high_default(self):
        tool_input = {"subagent_type": "software-engineer"}
        env = {"CLAUDE_THINKING_EFFORT": "low"}
        result = resolve(tool_input=tool_input, env=env, state={})
        self.assertEqual(result["effort"], "low")
        self.assertEqual(result["source"], "env")


# ---------------- AC5 / AC5b / AC5c: explicit thinking field ----------------


class ExplicitInputWinsOverDefault(unittest.TestCase):
    def test_explicit_input_wins_over_default(self):
        explicit = {"thinking": {"effort": "low"}}
        result = resolve(tool_input=explicit, env={}, state={})
        self.assertEqual(result["effort"], "low")


class ExplicitWinsOverImplementationRoleXhigh(unittest.TestCase):
    def test_explicit_low_overrides_software_engineer_high_default(self):
        tool_input = {
            "subagent_type": "software-engineer",
            "thinking": {"effort": "low"},
        }
        result = resolve(tool_input=tool_input, env={}, state={})
        self.assertEqual(result["effort"], "low")
        self.assertEqual(result["source"], "explicit")


class ExplicitWinsOverDowngrade(unittest.TestCase):
    def test_explicit_xhigh_overrides_code_reviewer_high(self):
        tool_input = {
            "subagent_type": "code-reviewer",
            "thinking": {"effort": "xhigh"},
        }
        result = resolve(tool_input=tool_input, env={}, state={})
        self.assertEqual(result["effort"], "xhigh")
        self.assertEqual(result["source"], "explicit")


# ---------------- AC6 / AC6b / AC6c: hook end-to-end + source field ----------------


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
        result = resolve(tool_input={"thinking": {"effort": "low"}},
                         env={}, state={})
        self.assertEqual(result["source"], "explicit")

    def test_default_win_reports_default_source(self):
        result = resolve(tool_input={}, env={}, state={})
        self.assertEqual(result["source"], "default")


# ---------------- AC7: snapshot test for downgrade-list / agent frontmatter ----------------


class DowngradeListMatchesAgentFrontmatter(unittest.TestCase):
    """Pins `_DOWNGRADE_TO_HIGH ∪ _DOWNGRADE_TO_LOW` to exactly the nine
    Sonnet-executor agent files. Drift in either direction fails CI: a missing
    entry would silently waste capability; an extra entry for an Opus-promoted
    agent would silently downgrade it.
    """

    EXPECTED_ROLES = {
        "code-reviewer", "qa-engineer", "product-reviewer",
        "patch-critic", "database-engineer", "security-engineer",
        "planning-agent", "software-engineer", "frontend-engineer",
    }

    def _frontmatter(self, role):
        path = REPO_ROOT / "agents" / f"{role}.md"
        text = path.read_text()
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        return match.group(1) if match else ""

    def _is_sonnet_executor(self, role):
        body = self._frontmatter(role)
        executor = re.search(r"^executor:\s*(\S+)", body, re.MULTILINE)
        if executor:
            return "sonnet" in executor.group(1).lower()
        model = re.search(r"^model:\s*(\S+)", body, re.MULTILINE)
        return bool(model) and "sonnet" in model.group(1).lower()

    def test_every_role_has_sonnet_executor(self):
        for role in self.EXPECTED_ROLES:
            self.assertTrue(
                self._is_sonnet_executor(role),
                f"{role}: expected Sonnet executor (model or executor field)")

    def test_downgrade_list_matches_sonnet_executor_agents(self):
        from thinking_role import _DOWNGRADE_TO_HIGH, _DOWNGRADE_TO_LOW
        actual = set(_DOWNGRADE_TO_HIGH) | set(_DOWNGRADE_TO_LOW)
        self.assertEqual(actual, self.EXPECTED_ROLES,
                         "Downgrade set drift vs agent frontmatter")


# ---------------- Pipeline-state / debug-display regression tests ----------------


class EnvDisplayOverridesAll(unittest.TestCase):
    def test_env_display_overrides_all(self):
        explicit = {"thinking": {"display": "omitted"}}
        env = {"CLAUDE_THINKING_DISPLAY": "text"}
        result = resolve(tool_input=explicit, env=env, state={})
        self.assertEqual(result["display"], "text")


class PipelineStateDirEnvRedirect(unittest.TestCase):
    def test_pipeline_state_dir_env_redirect(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "redirect-test",
                         "---\ntask_id: redirect-test\nphase: build\n"
                         "critical: true\n---\n")
            with patch.dict(os.environ,
                            {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertEqual(state["task_id"], "redirect-test")
            self.assertTrue(state["critical"])


class MissingPipelineStateDirIsSafe(unittest.TestCase):
    def test_missing_pipeline_state_dir_is_safe(self):
        missing = "/tmp/definitely-does-not-exist-nope-zzz"
        with patch.dict(os.environ,
                        {"CLAUDE_PIPELINE_STATE_DIR": missing}, clear=True):
            state = read_active_state()
        self.assertEqual(state["task_id"], "")
        self.assertFalse(state["critical"])


class DebugStateFileTriggersTextDisplay(unittest.TestCase):
    def test_debug_state_file_triggers_text_display(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "fix-me",
                         "---\ntask_id: fix-me\nphase: build\n---\n")
            (Path(tmp) / "fix-me-debug.md").write_text("debug notes")
            with patch.dict(os.environ,
                            {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
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
            with patch.dict(os.environ,
                            {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            result = resolve(tool_input={}, env={}, state=state)
        self.assertTrue(state["debug_active"])
        self.assertEqual(result["display"], "text")


class MalformedBudgetCoercesToZero(unittest.TestCase):
    def test_non_numeric_budget_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "bad-budget",
                         "---\ntask_id: bad-budget\nphase: build\n"
                         "budget: abc\n---\n")
            with patch.dict(os.environ,
                            {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertEqual(state["budget"], 0)


class MultiplePipelineFilesPickNewestByMtime(unittest.TestCase):
    def test_newer_pipeline_file_wins_over_older(self):
        with tempfile.TemporaryDirectory() as tmp:
            older = _write_state(tmp, "aaa-older",
                                 "---\ntask_id: aaa-older\nphase: build\n"
                                 "---\n")
            newer = _write_state(tmp, "zzz-newer",
                                 "---\ntask_id: zzz-newer\nphase: review\n"
                                 "---\n")
            os.utime(older, (1_000_000, 1_000_000))
            os.utime(newer, (2_000_000, 2_000_000))
            with patch.dict(os.environ,
                            {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertEqual(state["task_id"], "zzz-newer")


# ---------------- Resolver script + hook integration ----------------


RESOLVER_SCRIPT = REPO_ROOT / "hooks" / "_lib" / "resolve-thinking.py"


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


def _cleanup_metric_session(session):
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
        log_path = (Path.home() / ".claude" / "metrics" / session
                    / "hook-injections.jsonl")
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "architect"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            self.assertTrue(log_path.exists(),
                            f"expected log at {log_path}")
            line = log_path.read_text().strip().splitlines()[-1]
            entry = json.loads(line)
            self.assertEqual(entry["agent_role"], "architect")
            self.assertEqual(entry["resolved"]["effort"], "high")
        finally:
            _cleanup_metric_session(session)


class HookLogsDowngradeRole(unittest.TestCase):
    def test_missing_thinking_with_code_reviewer_logs_high(self):
        session = f"test-{uuid.uuid4()}"
        log_path = (Path.home() / ".claude" / "metrics" / session
                    / "hook-injections.jsonl")
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            self.assertTrue(log_path.exists(),
                            f"expected log at {log_path}")
            line = log_path.read_text().strip().splitlines()[-1]
            entry = json.loads(line)
            self.assertEqual(entry["resolved"]["effort"], "high")
            self.assertEqual(entry["resolved"]["source"], "role")
        finally:
            _cleanup_metric_session(session)


# ---------------- Coerce-state / debug-mtime regression tests ----------------


class CoerceStateTaskClassAndBestofnRoundTrip(unittest.TestCase):
    def test_explicit_feature_and_bestofn_true(self):
        body = ("---\ntask_id: t\nphase: build\ntask_class: feature\n"
                "bestofn: true\n---\n")
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
                         "---\ntask_id: bon-on\nphase: build\n"
                         "bestofn: true\n---\n")
            with patch.dict(os.environ,
                            {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertIs(state["bestofn"], True)

    def test_pipeline_without_bestofn_defaults_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "bon-off",
                         "---\ntask_id: bon-off\nphase: build\n---\n")
            with patch.dict(os.environ,
                            {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertIs(state["bestofn"], False)


class DebugMtimeFieldNoneWhenNoDebugFile(unittest.TestCase):
    def test_debug_mtime_is_none_when_no_debug_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "no-debug",
                         "---\ntask_id: no-debug\nphase: build\n---\n")
            with patch.dict(os.environ,
                            {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertIsNone(state["debug_mtime"])


class DebugMtimeFieldFloatWhenDebugFileExists(unittest.TestCase):
    def test_debug_mtime_is_float_epoch_when_debug_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_state(tmp, "with-debug",
                         "---\ntask_id: with-debug\nphase: build\n---\n")
            debug_file = Path(tmp) / "with-debug-debug.md"
            debug_file.write_text("notes")
            os.utime(debug_file, (1_500_000_000.0, 1_500_000_000.0))
            with patch.dict(os.environ,
                            {"CLAUDE_PIPELINE_STATE_DIR": tmp}, clear=True):
                state = read_active_state()
            self.assertEqual(state["debug_mtime"], 1_500_000_000.0)


class FreshDebugFileWithinTtlYieldsTextDisplay(unittest.TestCase):
    def test_fresh_debug_file_within_ttl_yields_text(self):
        now = 1_500_000_000.0
        state = {"debug_active": True, "debug_mtime": now - 120}
        result = resolve(tool_input={}, env={}, state=state, now=now)
        self.assertEqual(result["display"], "text")


class StaleDebugFileBeyondTtlYieldsOmittedDisplay(unittest.TestCase):
    def test_old_debug_file_beyond_ttl_yields_omitted(self):
        now = 1_500_000_000.0
        state = {"debug_active": True, "debug_mtime": now - 2400}
        result = resolve(tool_input={}, env={}, state=state, now=now)
        self.assertEqual(result["display"], "omitted")


class EnvDisplayWinsOverStaleDebugTtl(unittest.TestCase):
    def test_env_display_text_overrides_old_debug_omitted(self):
        now = 1_500_000_000.0
        state = {"debug_active": True, "debug_mtime": now - 2400}
        env = {"CLAUDE_THINKING_DISPLAY": "text"}
        result = resolve(tool_input={}, env=env, state=state, now=now)
        self.assertEqual(result["display"], "text")


class NoDebugFileYieldsOmittedDisplay(unittest.TestCase):
    def test_no_debug_active_yields_omitted(self):
        now = 1_500_000_000.0
        state = {"debug_active": False, "debug_mtime": None}
        result = resolve(tool_input={}, env={}, state=state, now=now)
        self.assertEqual(result["display"], "omitted")


class CustomTtlEnvOverridesDefault(unittest.TestCase):
    def test_custom_short_ttl_truncates_window(self):
        now = 1_500_000_000.0
        state = {"debug_active": True, "debug_mtime": now - 120}
        env = {"CLAUDE_DEBUG_DISPLAY_TTL": "60"}
        result = resolve(tool_input={}, env=env, state=state, now=now)
        self.assertEqual(result["display"], "omitted")


# ---------------- C-AC1..C-AC8: $CLAUDE_EFFORT precedence tier 2a ----------------


class ClaudeEffortEnvLowWinsWhenNoHigherTier(unittest.TestCase):
    """C-AC1: bare CLAUDE_EFFORT=low resolves to effort=low when no rule 1 / 2
    fires."""

    def test_claude_effort_env_low_wins_when_no_higher_tier(self):
        result = resolve(tool_input={}, env={"CLAUDE_EFFORT": "low"}, state={})
        self.assertEqual(result["effort"], "low")
        self.assertEqual(result["source"], "claude-effort-env")


class ClaudeEffortEnvInvalidValueFallsThroughToRole(unittest.TestCase):
    """C-AC1: invalid CLAUDE_EFFORT value MUST be rejected by `_valid_env`,
    falling through to rule 3 (role rules). Mutation-kill coverage on the
    validation path: a mutant skipping `_valid_env` would yield
    source='claude-effort-env' instead of 'role'."""

    def test_claude_effort_env_invalid_value_falls_through_to_role(self):
        result = resolve(
            tool_input={"subagent_type": "code-reviewer"},
            env={"CLAUDE_EFFORT": "banana"},
            state={},
        )
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")


class ClaudeEffortEnvXhighAcceptedForHarnessConsistency(unittest.TestCase):
    """C-AC1: harness `_EFFORTS` set includes `xhigh`; the new tier reuses the
    same enum, so `CLAUDE_EFFORT=xhigh` is accepted. Documents the
    harness-vs-Anthropic enum divergence (Anthropic API exposes
    low|medium|high; harness adds xhigh for stakes-bearing promotions)."""

    def test_claude_effort_env_xhigh_accepted_for_harness_consistency(self):
        result = resolve(
            tool_input={}, env={"CLAUDE_EFFORT": "xhigh"}, state={})
        self.assertEqual(result["effort"], "xhigh")
        self.assertEqual(result["source"], "claude-effort-env")


class ClaudeEffortEnvReportsDistinctSource(unittest.TestCase):
    """C-AC2: source field value MUST be `claude-effort-env` (NOT `env`).
    The existing `env` token is reserved for `CLAUDE_THINKING_EFFORT` (rule 1)
    so prior observations remain interpretable."""

    def test_claude_effort_env_reports_distinct_source(self):
        result = resolve(tool_input={}, env={"CLAUDE_EFFORT": "low"}, state={})
        self.assertEqual(result["source"], "claude-effort-env")
        self.assertNotEqual(result["source"], "env")


class DocCarriesNamingRationaleClause(unittest.TestCase):
    """C-AC2: the doc note carries a naming-rationale clause explaining why
    the new tier uses `claude-effort-env` rather than reusing `env`. The clause
    must mention that the existing `env` source name predates Claude Code's
    session-level env var, AND that `claude-effort-env` is name-prefixed to
    disambiguate. Location is unconstrained (precedence rule 2a OR forensic
    block OR Slice-B subsection); test pins substring presence anywhere in the
    file."""

    def test_doc_carries_naming_rationale_clause(self):
        path = (REPO_ROOT / "rules" / "_detail" / "thinking-defaults.md")
        body = path.read_text()
        self.assertRegex(
            body,
            r"existing\s+`?env`?\s+source\s+name.*predates",
            "Naming-rationale clause: 'existing env source name ... predates' "
            "phrase missing from rules/_detail/thinking-defaults.md",
        )
        self.assertRegex(
            body,
            r"`?claude-effort-env`?.*name-prefixed.*disambiguate",
            "Naming-rationale clause: 'claude-effort-env ... name-prefixed "
            "... disambiguate' phrase missing",
        )


class ClaudeThinkingEffortOverridesClaudeEffortEnv(unittest.TestCase):
    """C-AC3: `CLAUDE_THINKING_EFFORT` (rule 1) wins over `CLAUDE_EFFORT`
    (rule 2a). Source reports `env`, not `claude-effort-env`."""

    def test_claude_thinking_effort_overrides_claude_effort_env(self):
        env = {"CLAUDE_THINKING_EFFORT": "xhigh", "CLAUDE_EFFORT": "low"}
        result = resolve(tool_input={}, env=env, state={})
        self.assertEqual(result["effort"], "xhigh")
        self.assertEqual(result["source"], "env")


class ExplicitThinkingFieldOverridesClaudeEffortEnv(unittest.TestCase):
    """C-AC4: explicit `thinking.effort` field on `tool_input` (rule 2) wins
    over `CLAUDE_EFFORT` (rule 2a). Source reports `explicit`."""

    def test_explicit_thinking_field_overrides_claude_effort_env(self):
        result = resolve(
            tool_input={"thinking": {"effort": "low"}},
            env={"CLAUDE_EFFORT": "high"},
            state={},
        )
        self.assertEqual(result["effort"], "low")
        self.assertEqual(result["source"], "explicit")


class ClaudeEffortEnvSuppressesArchitectXhighPromotion(unittest.TestCase):
    """C-AC5: when `CLAUDE_EFFORT=high` is set, an `architect` spawn that
    would otherwise promote to xhigh via rule 3a is suppressed. Operator
    override wins over role auto-promotion. Source reports
    `claude-effort-env`."""

    def test_claude_effort_env_suppresses_architect_xhigh_promotion(self):
        result = resolve(
            tool_input={"subagent_type": "architect"},
            env={"CLAUDE_EFFORT": "high"},
            state={"critical": True, "budget": 12},
        )
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "claude-effort-env")


class ThinkingDefaultsDocListsRule2aClaudeEffortEnv(unittest.TestCase):
    """C-AC6: `## Precedence` numbered list contains rule 2a entry naming
    `CLAUDE_EFFORT` env override AND the `CLAUDE_HOOK_PROFILE=minimal`
    interaction note. The new tier slots between current rule 2 and current
    rule 3; subsequent rules do NOT renumber (still 3, 4)."""

    def test_thinking_defaults_doc_lists_rule_2a_claude_effort_env(self):
        path = (REPO_ROOT / "rules" / "_detail" / "thinking-defaults.md")
        body = path.read_text()
        # Rule 2a entry header. List items in markdown begin at column 0
        # (no leading whitespace).
        self.assertRegex(
            body,
            r"(?m)^2a\.\s+\*\*Claude Code effort env override\*\*",
            "Precedence list missing rule 2a header "
            "'2a. **Claude Code effort env override**'",
        )
        # CLAUDE_HOOK_PROFILE=minimal interaction note must appear in the
        # same rule-2a entry. We assert both substrings are present in the
        # doc body and that the rule-2a header appears before the note.
        rule_2a_idx = re.search(
            r"(?m)^2a\.\s+\*\*Claude Code effort env override\*\*",
            body,
        )
        rule_3_idx = re.search(
            r"(?m)^3\.\s+\*\*Role-based rules\*\*",
            body,
        )
        self.assertIsNotNone(rule_2a_idx, "rule-2a header not found")
        self.assertIsNotNone(rule_3_idx, "rule-3 header not found")
        rule_2a_block = body[rule_2a_idx.start():rule_3_idx.start()]
        self.assertIn(
            "CLAUDE_HOOK_PROFILE=minimal",
            rule_2a_block,
            "Rule 2a entry missing CLAUDE_HOOK_PROFILE=minimal interaction "
            "note",
        )


class ForensicCatalogIncludesClaudeEffortEnvBullet(unittest.TestCase):
    """C-AC7: `### Forensic / Source-Field Integration Note` subsection
    contains a bullet matching `source=="claude-effort-env"`. The bullet
    documents that the new value indicates rule 2a fired."""

    def test_forensic_catalog_includes_claude_effort_env_bullet(self):
        path = (REPO_ROOT / "rules" / "_detail" / "thinking-defaults.md")
        body = path.read_text()
        # Locate the forensic subsection.
        section_match = re.search(
            r"### Forensic / Source-Field Integration Note(.*?)(?=\n## |\Z)",
            body,
            re.DOTALL,
        )
        self.assertIsNotNone(
            section_match,
            "Forensic / Source-Field Integration Note subsection missing",
        )
        section = section_match.group(1)
        self.assertRegex(
            section,
            r'source=="claude-effort-env"',
            "Forensic subsection missing claude-effort-env bullet",
        )


class HookLogsClaudeEffortEnvSourceToJsonl(unittest.TestCase):
    """C-AC8: end-to-end hook test. Following precedent at
    HookLogsOnlyDoesNotBlock.test_missing_thinking_writes_log_line, we use
    `_run_hook(payload, env={...})`, generate the session ID via
    `f"test-{uuid.uuid4()}"`, and clean up via `_cleanup_metric_session` in
    `try/finally`. Asserts the JSONL record's `resolved.source ==
    'claude-effort-env'` AND `resolved.effort == 'low'`."""

    def test_hook_logs_claude_effort_env_source_to_jsonl(self):
        session = f"test-{uuid.uuid4()}"
        log_path = (Path.home() / ".claude" / "metrics" / session
                    / "hook-injections.jsonl")
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "architect"}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_EFFORT": "low"},
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(log_path.exists(),
                            f"expected log at {log_path}")
            line = log_path.read_text().strip().splitlines()[-1]
            entry = json.loads(line)
            self.assertEqual(entry["resolved"]["source"], "claude-effort-env")
            self.assertEqual(entry["resolved"]["effort"], "low")
        finally:
            _cleanup_metric_session(session)


if __name__ == "__main__":
    unittest.main()
