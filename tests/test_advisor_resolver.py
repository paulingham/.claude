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

try:
    from advisor_resolver import resolve_model_conditional, advisor_none_to_python_none
except ImportError:  # not yet implemented — RED phase
    resolve_model_conditional = None
    advisor_none_to_python_none = None

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
        # Test scenario: subagent_type provided but mocked frontmatter lacks
        # executor/advisor pairing — resolver must fall through. infrastructure-
        # engineer chosen as a write-capable role outside the reviewer set.
        tool_input = {"subagent_type": "infrastructure-engineer"}
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
        """B11: updated to index-based 3-line unpack (Slice B)."""
        payload = {"tool_name": "Agent",
                   "tool_input": {"subagent_type": "code-reviewer"}}
        result = _run_resolver(payload, env={"ANTHROPIC_API_KEY": "sk-test"})
        self.assertEqual(result.returncode, 0)
        # Use splitlines() WITHOUT .strip() so an empty 3rd line is preserved.
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 3, f"expected 3 lines, got {len(lines)}: {result.stdout!r}")
        first = lines[0]
        second = lines[1]
        self.assertIn(first, {"LOG", "SKIP"})
        json.loads(second)  # second line is valid JSON
        # Third line is empty string OR valid JSON (binding JSON when rule fires)
        if lines[2]:
            json.loads(lines[2])

    def test_non_agent_emits_skip(self):
        result = _run_resolver({"tool_name": "Bash", "tool_input": {}})
        first = result.stdout.strip().splitlines()[0]
        self.assertEqual(first, "SKIP")


REPO_ROOT = Path(__file__).resolve().parents[1]


class SettingsRegistersAdvisorHook(unittest.TestCase):
    def test_settings_registers_advisor_hook(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        agent_groups = [g for g in settings["hooks"]["PreToolUse"]
                        if g.get("matcher") == "Agent"]
        self.assertEqual(len(agent_groups), 1, "expected exactly one PreToolUse Agent group")
        commands = [h["command"] for h in agent_groups[0]["hooks"]]
        self._assert_existing_hooks_unchanged(commands)
        self._assert_advisor_hook_registered_after_thinking(commands)

    def _assert_existing_hooks_unchanged(self, commands):
        self.assertIn("bash ~/.claude/hooks/pipeline-state-guard.sh", commands)
        self.assertIn("bash ~/.claude/hooks/agent-skill-reminder.sh", commands)
        self.assertIn("bash ~/.claude/hooks/pre-agent-thinking.sh", commands)

    def _assert_advisor_hook_registered_after_thinking(self, commands):
        advisor_cmd = "bash ~/.claude/hooks/pre-agent-advisor.sh"
        self.assertIn(advisor_cmd, commands)
        thinking_idx = commands.index("bash ~/.claude/hooks/pre-agent-thinking.sh")
        advisor_idx = commands.index(advisor_cmd)
        self.assertGreater(advisor_idx, thinking_idx,
                           "advisor hook must be registered AFTER thinking hook")


def _read_agent_frontmatter(name):
    import re
    import yaml
    text = (REPO_ROOT / "agents" / f"{name}.md").read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(match.group(1)) if match else {}


class CodeReviewerHasAdvisorPairing(unittest.TestCase):
    def test_code_reviewer_has_advisor_pairing(self):
        fm = _read_agent_frontmatter("code-reviewer")
        self.assertEqual(fm["executor"], "claude-sonnet-4-6")
        self.assertEqual(fm["advisor"], "claude-opus-4-7")
        self.assertEqual(fm["model"], "opus", "model: opus must be UNCHANGED")


class SecurityEngineerHasAdvisorPairing(unittest.TestCase):
    def test_security_engineer_has_advisor_pairing(self):
        fm = _read_agent_frontmatter("security-engineer")
        self.assertEqual(fm["executor"], "claude-sonnet-4-6")
        self.assertEqual(fm["advisor"], "claude-opus-4-7")
        self.assertEqual(fm["model"], "opus", "model: opus must be UNCHANGED")


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


class ResolverRejectsTraversalSubagentType(unittest.TestCase):
    """HIGH regression — security-engineer review round 1.
    A traversal subagent_type must NOT load attacker-controlled frontmatter
    from outside ~/.claude/agents/."""

    def test_traversal_subagent_type_returns_no_pairing_frontmatter(self):
        """B12: updated to index-based unpack (Slice B)."""
        evil_dir = Path("/tmp/sec-poc-test-advisor-frontmatter")
        evil_file = evil_dir / "evil.md"
        evil_dir.mkdir(parents=True, exist_ok=True)
        evil_file.write_text(
            "---\nexecutor: ATTACKER-CONTROLLED-EXECUTOR\n"
            "advisor: ATTACKER-CONTROLLED-ADVISOR\n---\n")
        try:
            payload = {"tool_name": "Agent",
                       "tool_input": {"subagent_type":
                                      "../../../../tmp/sec-poc-test-advisor-frontmatter/evil"}}
            result = _run_resolver(payload, env={"ANTHROPIC_API_KEY": "sk-test"})
            self.assertEqual(result.returncode, 0)
            lines = result.stdout.splitlines()
            _decision = lines[0]
            resolved_json = lines[1]
            resolved = json.loads(resolved_json)
            self.assertNotEqual(resolved.get("executor"), "ATTACKER-CONTROLLED-EXECUTOR")
            self.assertNotEqual(resolved.get("advisor"), "ATTACKER-CONTROLLED-ADVISOR")
            self.assertEqual(resolved.get("source"), "no-pairing-frontmatter")
        finally:
            if evil_file.exists():
                evil_file.unlink()
            if evil_dir.exists():
                evil_dir.rmdir()


class NonReviewerWithNoApiKeyReturnsNoPairingFrontmatter(unittest.TestCase):
    """LOW regression — security-engineer review round 1.
    Precedence must short-circuit non-reviewer agents to no-pairing-frontmatter
    BEFORE the env/api-key check fires. Otherwise audit logs misattribute every
    non-reviewer spawn under a missing API key as 'no-api-key'."""

    def test_non_reviewer_with_no_api_key_returns_no_pairing_frontmatter(self):
        result = resolve(
            tool_input={"subagent_type": "software-engineer"},
            env={},  # ANTHROPIC_API_KEY absent
            frontmatter={"model": "opus"})  # no executor/advisor
        self.assertEqual(result["fallback_reason"], "no-pairing-frontmatter")
        self.assertEqual(result["source"], "no-pairing-frontmatter")


class AdvisorFrontmatterReexportsFromPipelineFrontmatter(unittest.TestCase):
    """MEDIUM regression — code-reviewer review round 1.
    advisor_frontmatter.parse_frontmatter must be the same function object
    as pipeline_frontmatter.parse_frontmatter (no parallel implementation)."""

    def test_advisor_frontmatter_reexports_pipeline_parser(self):
        import advisor_frontmatter
        import pipeline_frontmatter
        self.assertIs(advisor_frontmatter.parse_frontmatter,
                      pipeline_frontmatter.parse_frontmatter)


class HookCapsAgentRoleLength(unittest.TestCase):
    """MEDIUM regression — security-engineer review round 1.
    A 1MB subagent_type must NOT produce an unbounded log line."""

    def test_million_char_subagent_type_produces_capped_log_line(self):
        session = f"test-cap-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "advisor-dispatch.jsonl"
        try:
            payload = {"tool_name": "Agent",
                       "tool_input": {"subagent_type": "A" * 1_000_000}}
            result = _run_hook(
                payload,
                env={"CLAUDE_SESSION_ID": session, "ANTHROPIC_API_KEY": "sk-test"})
            self.assertEqual(result.returncode, 0)
            self.assertTrue(log_path.exists())
            line = log_path.read_text().strip().splitlines()[-1]
            self.assertLessEqual(len(line), 1024,
                                 f"log line not capped: {len(line)} bytes")
            self.assertEqual(json.loads(line)["agent_role"], "A" * 64)
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                log_path.parent.rmdir()


class HookSanitisesSessionIdAgainstTraversal(unittest.TestCase):
    """CRITICAL regression — security-engineer review round 1.
    A traversal CLAUDE_SESSION_ID must NOT escape ~/.claude/metrics/."""

    def test_traversal_session_id_does_not_escape_metrics_dir(self):
        traversal_target = Path("/tmp/sec-poc-test-advisor/PWNED")
        # Pre-clean any prior PoC artefacts so the assertion is meaningful.
        if traversal_target.exists():
            for child in traversal_target.iterdir():
                child.unlink()
            traversal_target.rmdir()
        if traversal_target.parent.exists():
            try:
                traversal_target.parent.rmdir()
            except OSError:
                pass
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer"}},
                env={"CLAUDE_SESSION_ID": "../../../../tmp/sec-poc-test-advisor/PWNED",
                     "ANTHROPIC_API_KEY": "sk-test"})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(traversal_target.exists(),
                             "traversal escaped: file created at /tmp/...")
        finally:
            if traversal_target.exists():
                for child in traversal_target.iterdir():
                    child.unlink()
                traversal_target.rmdir()
            if traversal_target.parent.exists():
                try:
                    traversal_target.parent.rmdir()
                except OSError:
                    pass


_SKILL_FILES = [
    REPO_ROOT / "skills" / "code-review" / "SKILL.md",
    REPO_ROOT / "skills" / "security-review" / "SKILL.md",
]


class SkillDocsUseIntendedDefaultFraming(unittest.TestCase):
    def test_skill_docs_use_intended_default_framing(self):
        for path in _SKILL_FILES:
            text = path.read_text()
            self.assertIn("intended default", text, f"{path.name}: missing 'intended default'")
            self.assertIn("currently advisory", text, f"{path.name}: missing 'currently advisory'")
            self.assertNotIn("Path B -- advisory", text, f"{path.name}: standalone Path B framing leaked")


_DOC_TOUCHPOINTS = [
    REPO_ROOT / "skills" / "code-review" / "SKILL.md",
    REPO_ROOT / "skills" / "security-review" / "SKILL.md",
    REPO_ROOT / "protocols" / "parallel-dispatch-protocol.md",
    REPO_ROOT / "CLAUDE.md",
]


class ProvisionalMarkingPresentAtEveryDocTouchpoint(unittest.TestCase):
    def test_provisional_marking_present_at_every_doc_touchpoint(self):
        import re as _re
        # Advisor-mode cost figures only: explicit percentages or savings claims.
        # Bare "cheaper" appears in unrelated Best-of-N tie-breaker text.
        pattern = _re.compile(r"(\b40\s?%|\b60\s?%|\bsavings\b)", _re.IGNORECASE)
        for path in _DOC_TOUCHPOINTS:
            lines = path.read_text().splitlines()
            self._assert_at_least_one_cost_figure(path, lines, pattern)
            self._assert_each_cost_figure_marked(path, lines, pattern)

    def _assert_at_least_one_cost_figure(self, path, lines, pattern):
        if not any(pattern.search(line) for line in lines):
            self.fail(f"{path.name}: no advisor-mode cost figure found — must mention pairing cost")

    def _assert_each_cost_figure_marked(self, path, lines, pattern):
        for idx, line in enumerate(lines):
            if not pattern.search(line):
                continue
            window = "\n".join(lines[max(0, idx - 3):idx + 4])
            self.assertIn("PROVISIONAL", window,
                          f"{path.name}:{idx+1}: cost figure missing PROVISIONAL within 3 lines")
            wider = "\n".join(lines[max(0, idx - 10):idx + 11])
            self.assertIn("advisor-baseline", wider,
                          f"{path.name}:{idx+1}: cost figure missing advisor-baseline reference within 10 lines")


class TestModelConditionalSchemaDoc(unittest.TestCase):
    """Slice A AC-A1: advisor-mode.md documents the model_conditional schema."""

    def test_model_conditional_schema_section_in_advisor_mode_md(self):
        path = Path(__file__).resolve().parents[1] / "protocols" / "advisor-mode.md"
        body = path.read_text()
        self.assertIn("## model_conditional Schema", body,
                      "advisor-mode.md missing '## model_conditional Schema' heading")
        # 5 frontmatter field names
        for field in ("default", "rules", "when", "budget_lt", "status"):
            self.assertIn(field, body,
                          f"advisor-mode.md schema section missing field: {field}")
        # 4-source resolver enum
        for src in ("no-conditional", "no-budget", "rule-match:budget_lt:", "default-arm"):
            self.assertIn(src, body,
                          f"advisor-mode.md missing resolver source: {src}")
        # Reference to resolver function
        self.assertIn("resolve_model_conditional", body,
                      "advisor-mode.md missing reference to resolve_model_conditional")
        self.assertIn("hooks/_lib/advisor_resolver.py", body,
                      "advisor-mode.md missing resolver file path reference")


_TOP_LEVEL_TRIPLE_ONLY = {
    "model": "opus",
    "executor": "claude-sonnet-4-6",
    "advisor": "claude-opus-4-7",
}

_FRONTMATTER_WITH_CONDITIONAL = {
    "model": "opus",
    "executor": "claude-sonnet-4-6",
    "advisor": "claude-opus-4-7",
    "model_conditional": {
        "default": {
            "model": "opus",
            "executor": "claude-sonnet-4-6",
            "advisor": "claude-opus-4-7",
        },
        "rules": [
            {
                "when": {"budget_lt": 6},
                "model": "sonnet",
                "executor": "claude-sonnet-4-6",
                "advisor": "none",
            },
        ],
        "status": "advisory",
    },
}


class ResolveModelConditionalReturnsTopLevelWhenNoBlock(unittest.TestCase):
    def test_resolve_model_conditional_returns_top_level_when_no_block(self):
        result = resolve_model_conditional(_TOP_LEVEL_TRIPLE_ONLY, budget=5)
        self.assertEqual(result["source"], "no-conditional")
        self.assertEqual(result["model"], "opus")
        self.assertEqual(result["executor"], "claude-sonnet-4-6")
        self.assertEqual(result["advisor"], "claude-opus-4-7")


class ResolveModelConditionalBudget5ReturnsSonnetSolo(unittest.TestCase):
    def test_resolve_model_conditional_budget_5_returns_sonnet_solo(self):
        result = resolve_model_conditional(_FRONTMATTER_WITH_CONDITIONAL, budget=5)
        self.assertEqual(result["source"], "rule-match:budget_lt:6")
        self.assertEqual(result["model"], "sonnet")
        self.assertEqual(result["executor"], "claude-sonnet-4-6")
        self.assertEqual(result["advisor"], "none")


class ResolveModelConditionalBudget6ReturnsDefaultArm(unittest.TestCase):
    def test_resolve_model_conditional_budget_6_returns_default_arm(self):
        """CB=6 must NOT match budget_lt:6 (strictly-less semantics).
        Kills the budget < budget_lt -> budget <= budget_lt mutation
        flagged by verify Tier 3 at advisor_resolver.py:64."""
        result = resolve_model_conditional(_FRONTMATTER_WITH_CONDITIONAL, budget=6)
        self.assertEqual(result["source"], "default-arm")
        self.assertEqual(result["model"], "opus")
        self.assertEqual(result["executor"], "claude-sonnet-4-6")
        self.assertEqual(result["advisor"], "claude-opus-4-7")


class ResolveModelConditionalBudget8ReturnsDefaultArm(unittest.TestCase):
    def test_resolve_model_conditional_budget_8_returns_default_arm(self):
        result = resolve_model_conditional(_FRONTMATTER_WITH_CONDITIONAL, budget=8)
        self.assertEqual(result["source"], "default-arm")
        self.assertEqual(result["model"], "opus")
        self.assertEqual(result["executor"], "claude-sonnet-4-6")
        self.assertEqual(result["advisor"], "claude-opus-4-7")


class ResolveModelConditionalNoBudgetReturnsDefaultArm(unittest.TestCase):
    def test_resolve_model_conditional_no_budget_returns_default_arm(self):
        result = resolve_model_conditional(_FRONTMATTER_WITH_CONDITIONAL, budget=None)
        self.assertEqual(result["source"], "no-budget")
        self.assertEqual(result["model"], "opus")
        self.assertEqual(result["executor"], "claude-sonnet-4-6")
        self.assertEqual(result["advisor"], "claude-opus-4-7")


class ResolveModelConditionalIsPure(unittest.TestCase):
    def test_resolve_model_conditional_is_pure(self):
        source = inspect.getsource(resolve_model_conditional)
        self.assertNotIn("open(", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.environ", source)


class AdvisorNoneLiteralTranslatesToPythonNone(unittest.TestCase):
    def test_advisor_none_literal_translates_to_python_none(self):
        self.assertIsNone(advisor_none_to_python_none("none"))
        self.assertEqual(
            advisor_none_to_python_none("claude-opus-4-7"), "claude-opus-4-7")
        self.assertIsNone(advisor_none_to_python_none(None))


class TestCodeReviewerFrontmatterModelConditional(unittest.TestCase):
    """Slice B AC-B1/B2/B3: code-reviewer.md gets model_conditional block,
    existing top-level triple preserved, status flag is structural."""

    def _fm(self):
        return _read_agent_frontmatter("code-reviewer")

    def test_existing_triple_preserved_and_model_conditional_present(self):
        fm = self._fm()
        self.assertEqual(fm["model"], "opus")
        self.assertEqual(fm["executor"], "claude-sonnet-4-6")
        self.assertEqual(fm["advisor"], "claude-opus-4-7")
        self.assertIn("model_conditional", fm,
                      "code-reviewer.md missing model_conditional block")

    def test_code_reviewer_model_conditional_resolves_cb_5_to_sonnet_solo(self):
        result = resolve_model_conditional(self._fm(), budget=5)
        self.assertEqual(result["model"], "sonnet")
        self.assertEqual(result["advisor"], "none")
        self.assertEqual(result["source"], "rule-match:budget_lt:6")

    def test_code_reviewer_model_conditional_resolves_cb_8_to_default(self):
        result = resolve_model_conditional(self._fm(), budget=8)
        self.assertEqual(result["model"], "opus")
        self.assertEqual(result["advisor"], "claude-opus-4-7")
        self.assertEqual(result["source"], "default-arm")

    def test_code_reviewer_status_flag_is_advisory_structural(self):
        fm = self._fm()
        self.assertEqual(fm["model_conditional"]["status"], "advisory")


# ---------------------------------------------------------------------------
# Slice B — Model binding wire tests (B1-B10)
# ---------------------------------------------------------------------------

_REVIEWER_PAYLOAD_BUDGET4 = {
    "tool_name": "Agent",
    "tool_input": {"subagent_type": "code-reviewer"},
}

_SE_PAYLOAD = {
    "tool_name": "Agent",
    "tool_input": {"subagent_type": "software-engineer"},
}

# qa-engineer has no model_conditional block — used for "no binding" assertions.
_QA_PAYLOAD = {
    "tool_name": "Agent",
    "tool_input": {"subagent_type": "qa-engineer"},
}

_NON_AGENT_PAYLOAD = {
    "tool_name": "Bash",
    "tool_input": {},
}


def _run_resolver_with_budget(payload, budget, env=None):
    """Run resolve-advisor.py with a fake pipeline-state that has the given budget."""
    proc_env = {
        **os.environ, **(env or {}),
        "ANTHROPIC_API_KEY": "sk-test",
        # Point to worktree agents dir so model_conditional frontmatter is visible
        "CLAUDE_AGENTS_DIR": str(REPO_ROOT / "agents"),
    }
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "test-pipeline.md"
        state_file.write_text(
            f"---\ntask_id: test\nphase: build\nbudget: {budget}\n---\n")
        proc_env["CLAUDE_PIPELINE_STATE_DIR"] = tmp
        return subprocess.run(
            ["python3", str(RESOLVER_SCRIPT)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=10, env=proc_env)


def _run_hook_with_budget(payload, budget, env=None):
    """Run pre-agent-advisor.sh with a fake pipeline-state that has the given budget."""
    proc_env = {
        **os.environ, **(env or {}),
        "ANTHROPIC_API_KEY": "sk-test",
        "CLAUDE_AGENTS_DIR": str(REPO_ROOT / "agents"),
    }
    with tempfile.TemporaryDirectory() as tmp:
        state_file = Path(tmp) / "test-pipeline.md"
        state_file.write_text(
            f"---\ntask_id: test\nphase: build\nbudget: {budget}\n---\n")
        proc_env["CLAUDE_PIPELINE_STATE_DIR"] = tmp
        return subprocess.run(
            ["bash", str(HOOK)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=10, env=proc_env)


class ResolverEmitsThreeLinesForReviewerWithConditional(unittest.TestCase):
    """B1: code-reviewer + budget=4 → line 3 is hookSpecificOutput JSON."""

    def test_third_line_is_hook_output_json(self):
        result = _run_resolver_with_budget(_REVIEWER_PAYLOAD_BUDGET4, budget=4)
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertGreaterEqual(len(lines), 3)
        self.assertEqual(lines[0], "LOG")
        third = lines[2]
        self.assertTrue(third, "line 3 should be non-empty for budget=4 code-reviewer")
        parsed = json.loads(third)
        self.assertEqual(
            parsed["hookSpecificOutput"]["updatedInput"]["model"], "sonnet")


class ResolverThirdLineIsEmptyWhenNoModelConditional(unittest.TestCase):
    """B2: qa-engineer (no model_conditional) → line 3 is empty."""

    def test_software_engineer_third_line_empty(self):
        # qa-engineer has no model_conditional block; should_emit_model returns False.
        result = _run_resolver_with_budget(_QA_PAYLOAD, budget=4)
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertGreaterEqual(len(lines), 3)
        self.assertEqual(lines[2], "",
                         "line 3 must be empty for qa-engineer (no model_conditional)")


class ResolverThirdLineEmptyForNonAgentSkip(unittest.TestCase):
    """B3: non-Agent payload → SKIP decision → line 3 empty."""

    def test_skip_decision_third_line_empty(self):
        result = _run_resolver(_NON_AGENT_PAYLOAD,
                               env={"ANTHROPIC_API_KEY": "sk-test"})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertGreaterEqual(len(lines), 3)
        self.assertEqual(lines[0], "SKIP")
        self.assertEqual(lines[2], "",
                         "line 3 must be empty for SKIP decision")


class HookEmitsModelBindingToStdoutWhenResolved(unittest.TestCase):
    """B4: hook subprocess stdout contains hookSpecificOutput for reviewer, budget=4."""

    def test_hook_stdout_contains_hook_specific_output(self):
        result = _run_hook_with_budget(_REVIEWER_PAYLOAD_BUDGET4, budget=4)
        self.assertEqual(result.returncode, 0)
        self.assertIn("hookSpecificOutput", result.stdout,
                      "hook stdout must contain hookSpecificOutput JSON")
        # Parse the hookSpecificOutput line from stdout
        for line in result.stdout.splitlines():
            if "hookSpecificOutput" in line:
                parsed = json.loads(line)
                self.assertEqual(
                    parsed["hookSpecificOutput"]["updatedInput"]["model"], "sonnet")
                break


class HookStaysStdoutSilentForNonReviewer(unittest.TestCase):
    """B5: qa-engineer (no model_conditional) → hook stdout empty."""

    def test_hook_stdout_empty_for_software_engineer(self):
        # qa-engineer has no model_conditional block; binding does not fire.
        result = _run_hook_with_budget(_QA_PAYLOAD, budget=4)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "",
                         "hook stdout must be empty for qa-engineer (no model_conditional binding)")


class DisableGateShortCircuitsBeforeModelBinding(unittest.TestCase):
    """B6: CLAUDE_DISABLE_ADVISOR_GATE=1 → hook exits before resolver; stdout empty."""

    def test_disable_gate_hook_stdout_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_hook(
                _REVIEWER_PAYLOAD_BUDGET4,
                env={"CLAUDE_DISABLE_ADVISOR_GATE": "1",
                     "ANTHROPIC_API_KEY": "sk-test",
                     "CLAUDE_PIPELINE_STATE_DIR": tmp})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "",
                         "CLAUDE_DISABLE_ADVISOR_GATE=1 must suppress all stdout")


class ExistingJsonlLoggingPreservedAlongsideBinding(unittest.TestCase):
    """B7: JSONL written AND stdout binding emitted for same spawn."""

    def test_jsonl_and_stdout_both_emitted(self):
        session = f"test-b7-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "advisor-dispatch.jsonl"
        try:
            result = _run_hook_with_budget(
                _REVIEWER_PAYLOAD_BUDGET4, budget=4,
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            self.assertTrue(log_path.exists(), f"JSONL not written at {log_path}")
            self.assertIn("hookSpecificOutput", result.stdout,
                          "hook stdout must emit binding when JSONL is written")
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                try:
                    log_path.parent.rmdir()
                except OSError:
                    pass


class HookExitsZeroOnResolverCrash(unittest.TestCase):
    """B8: broken python path → hook exits 0 (never-block invariant)."""

    def test_never_block_on_bad_python_path(self):
        import shutil
        bash_path = shutil.which("bash") or "/bin/bash"
        bash_dir = str(Path(bash_path).parent)
        # Keep bash (and jq, etc.) accessible but break python3 lookup.
        broken_python_bin = tempfile.mkdtemp()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    ["bash", str(HOOK)],
                    input=json.dumps(_REVIEWER_PAYLOAD_BUDGET4),
                    capture_output=True, text=True, timeout=10,
                    env={
                        **os.environ,
                        # PATH has bash + broken dir; python3 in broken_python_bin
                        # does not exist so python3 lookup fails at hook line 26.
                        "PATH": f"{bash_dir}:/usr/bin:{broken_python_bin}",
                        "ANTHROPIC_API_KEY": "sk-test",
                        "CLAUDE_PIPELINE_STATE_DIR": tmp,
                    })
            self.assertEqual(result.returncode, 0,
                             "hook must exit 0 even when resolver crashes")
        finally:
            shutil.rmtree(broken_python_bin, ignore_errors=True)


THINKING_HOOK = Path(__file__).resolve().parents[1] / "hooks" / "pre-agent-thinking.sh"


class ThinkingHookProducesNoStdoutForAgentPayload(unittest.TestCase):
    """B9: pre-agent-thinking.sh stdout is empty for an Agent payload."""

    def test_thinking_hook_stdout_empty(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["bash", str(THINKING_HOOK)],
                input=json.dumps({"tool_name": "Agent",
                                  "tool_input": {"subagent_type": "code-reviewer"}}),
                capture_output=True, text=True, timeout=10,
                env={**os.environ,
                     "ANTHROPIC_API_KEY": "sk-test",
                     "CLAUDE_PIPELINE_STATE_DIR": tmp})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "",
                         "pre-agent-thinking.sh must produce no stdout (log-only)")


class DisableModelBindingKeepsJsonlButSilencesStdout(unittest.TestCase):
    """B10: CLAUDE_DISABLE_MODEL_BINDING=1 → stdout empty; JSONL still written."""

    def test_disable_binding_env_var(self):
        session = f"test-b10-{uuid.uuid4()}"
        log_path = Path.home() / ".claude" / "metrics" / session / "advisor-dispatch.jsonl"
        try:
            result = _run_hook_with_budget(
                _REVIEWER_PAYLOAD_BUDGET4, budget=4,
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_DISABLE_MODEL_BINDING": "1"})
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "",
                             "CLAUDE_DISABLE_MODEL_BINDING=1 must silence stdout binding")
            self.assertTrue(log_path.exists(),
                            f"JSONL must still be written: {log_path}")
        finally:
            if log_path.exists():
                log_path.unlink()
            if log_path.parent.exists():
                try:
                    log_path.parent.rmdir()
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Slice C — Doc honesty tests (C3-C8 in test_advisor_resolver.py)
# ---------------------------------------------------------------------------

_ADVISOR_MODE_PATH = REPO_ROOT / "protocols" / "advisor-mode.md"


class AdvisorModeDocDoesNotClaimEnforced(unittest.TestCase):
    """C3: advisor-mode.md does not contain 'enforced default'."""

    def test_no_enforced_default_phrase_in_advisor_mode_md(self):
        body = _ADVISOR_MODE_PATH.read_text()
        self.assertNotIn("enforced default", body,
                         "advisor-mode.md must not claim 'enforced default'")


class AdvisorModeDocDocumentsModelBindingWithCaveat(unittest.TestCase):
    """C4: advisor-mode.md § Status contains 'updatedInput' + 'iff CC honors'."""

    def test_model_binding_caveat_in_status_section(self):
        body = _ADVISOR_MODE_PATH.read_text()
        self.assertIn("updatedInput", body)
        self.assertIn("iff CC honors", body)


class AdvisorModeDocNoteAdvisorFieldStillLogOnly(unittest.TestCase):
    """C5: advisor-mode.md states advisor: field is still not yet schema-exposed."""

    def test_advisor_not_schema_exposed_clause(self):
        body = _ADVISOR_MODE_PATH.read_text()
        self.assertIn("not yet schema-exposed", body)


class AdvisorModeDocNoStaleFollowUpReference(unittest.TestCase):
    """C6: advisor-mode.md does not contain stale 'named follow-up' phrase."""

    def test_no_named_follow_up_phrase(self):
        body = _ADVISOR_MODE_PATH.read_text()
        self.assertNotIn("named follow-up", body,
                         "advisor-mode.md must not contain stale 'named follow-up'")


class AdvisorModeDocOperatorControlsHasDisableModelBinding(unittest.TestCase):
    """C7: advisor-mode.md § Operator Controls contains CLAUDE_DISABLE_MODEL_BINDING."""

    def test_disable_model_binding_in_operator_controls(self):
        body = _ADVISOR_MODE_PATH.read_text()
        self.assertIn("CLAUDE_DISABLE_MODEL_BINDING", body)


if __name__ == "__main__":
    unittest.main()
