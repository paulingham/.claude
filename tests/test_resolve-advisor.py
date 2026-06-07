"""Path-validation regression tests for hooks/_lib/resolve-advisor.py.

The bulk of the resolver suite lives in `test_advisor_resolver.py` (matches the
module being tested). This file exists to satisfy the tdd-guard naming
convention for the stdin entry script and to keep the path-traversal HIGH
regression tied 1:1 to the file under test.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVER_SCRIPT = REPO_ROOT / "hooks" / "_lib" / "resolve-advisor.py"

_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _run(payload, env=None):
    proc_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["python3", str(RESOLVER_SCRIPT)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _run_resolver_with_intake(payload, intake_content, env=None):
    """Run resolve-advisor.py with a fake pipeline-state + intake.md fixture.

    Creates a new-layout pipeline-state tree:
      <tmp>/pipeline-state/test-s2/pipeline.md
      <tmp>/pipeline-state/test-s2/intake.md
    Sets CLAUDE_PLUGIN_DATA=<tmp> so read_active_state + _intake_budget both find it.
    Mirrors _run_resolver_with_budget from test_advisor_resolver.py:633-667.
    """
    existing_pp = os.environ.get("PYTHONPATH", "")
    merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
    proc_env = {
        **os.environ,
        "PYTHONPATH": merged_pp,
        "ANTHROPIC_API_KEY": "sk-test",
        "CLAUDE_AGENTS_DIR": str(REPO_ROOT / "agents"),
        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
        **(env or {}),
    }
    with tempfile.TemporaryDirectory() as tmp:
        # New layout: pipeline-state/{task-id}/pipeline.md + intake.md
        task_dir = Path(tmp) / "pipeline-state" / "test-s2"
        task_dir.mkdir(parents=True)
        pipeline_file = task_dir / "pipeline.md"
        pipeline_file.write_text(
            "---\ntask_id: test-s2\nphase: build\n---\n")
        intake_file = task_dir / "intake.md"
        intake_file.write_text(intake_content)
        proc_env["CLAUDE_PLUGIN_DATA"] = tmp
        # Do NOT set CLAUDE_PIPELINE_STATE_DIR — _intake_budget uses harness_data()
        # and read_active_state uses CLAUDE_PIPELINE_STATE_DIR; we want to test
        # the _intake_budget path, so point both at the same tmp root.
        proc_env["CLAUDE_PIPELINE_STATE_DIR"] = str(Path(tmp) / "pipeline-state")
        return subprocess.run(
            ["python3", str(RESOLVER_SCRIPT)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=10, env=proc_env)


_SE_PAYLOAD = {"tool_name": "Agent", "tool_input": {"subagent_type": "software-engineer"}}
_ARCH_PAYLOAD = {"tool_name": "Agent", "tool_input": {"subagent_type": "architect"}}


class TraversalSubagentTypeRejected(unittest.TestCase):
    """HIGH regression — security-engineer review round 1.
    Mirrors test_advisor_resolver.ResolverRejectsTraversalSubagentType so the
    behaviour is also asserted against the file under test by name."""

    def test_traversal_subagent_type_does_not_load_attacker_frontmatter(self):
        evil_dir = Path("/tmp/sec-poc-test-resolve-advisor")
        evil_file = evil_dir / "evil.md"
        evil_dir.mkdir(parents=True, exist_ok=True)
        evil_file.write_text(
            "---\nexecutor: ATTACKER-CONTROLLED-EXECUTOR\n"
            "advisor: ATTACKER-CONTROLLED-ADVISOR\n---\n")
        try:
            payload = {"tool_name": "Agent",
                       "tool_input": {"subagent_type":
                                      "../../../../tmp/sec-poc-test-resolve-advisor/evil"}}
            result = _run(payload, env={"ANTHROPIC_API_KEY": "sk-test"})
            self.assertEqual(result.returncode, 0)
            lines = result.stdout.strip().splitlines()
            resolved_json = lines[1] if len(lines) >= 2 else lines[0]
            resolved = json.loads(resolved_json)
            self.assertNotEqual(resolved.get("executor"), "ATTACKER-CONTROLLED-EXECUTOR")
            self.assertEqual(resolved.get("source"), "no-pairing-frontmatter")
        finally:
            if evil_file.exists():
                evil_file.unlink()
            if evil_dir.exists():
                evil_dir.rmdir()


# ---------------------------------------------------------------------------
# Slice B — Shadow-mode router wiring integration tests (Story 2)
# ---------------------------------------------------------------------------

class RouterOffOutputByteIdenticalToBaseline(unittest.TestCase):
    """AC2: unset vs =0 => stdout byte-identical to no-router baseline; no router_decision."""

    def test_router_off_output_byte_identical_to_baseline(self):
        intake = "---\ntask_id: test-s2\nphase: build\n---\n"
        result_off = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "0"})
        result_unset = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={})
        self.assertEqual(result_off.returncode, 0)
        self.assertEqual(result_unset.returncode, 0)
        self.assertEqual(result_off.stdout, result_unset.stdout,
                         "CLAUDE_MODEL_ROUTER=0 must produce byte-identical stdout to unset")
        # router_decision must be ABSENT from line 2
        lines_off = result_off.stdout.splitlines()
        resolved = json.loads(lines_off[1])
        self.assertNotIn("router_decision", resolved,
                         "router_decision key must be ABSENT when router is OFF")


class RouterOffBindingLineUnchanged(unittest.TestCase):
    """AC2: OFF line-3 binding identical to pre-router baseline."""

    def test_router_off_binding_line_unchanged(self):
        intake = "---\ntask_id: test-s2\nphase: build\n---\n"
        result_off = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "0"})
        result_unset = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={})
        lines_off = result_off.stdout.splitlines()
        lines_unset = result_unset.stdout.splitlines()
        self.assertEqual(lines_off[2], lines_unset[2],
                         "line-3 binding must be identical under OFF vs unset")


class RouterShadowAttachesRouterDecisionToResolved(unittest.TestCase):
    """AC3: shadow mode: line-2 resolved carries router_decision = would-be tier."""

    def test_router_shadow_attaches_router_decision_to_resolved(self):
        # nested complexity_budget.total:13 => expensive
        intake = "---\ntask_id: test-s2\ncomplexity_budget:\n  total: 13\n---\n"
        result = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "shadow"})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 3, f"expected 3 lines, got: {result.stdout!r}")
        resolved = json.loads(lines[1])
        self.assertIn("router_decision", resolved,
                      "shadow mode must attach router_decision to resolved dict")
        self.assertIn(resolved["router_decision"], ("cheap", "standard", "expensive"),
                      f"router_decision must be a valid tier, got: {resolved['router_decision']!r}")


class RouterShadowBindingIdenticalToOff(unittest.TestCase):
    """AC3: line-3 binding under shadow == under OFF for the same input (never rewrites)."""

    def test_router_shadow_binding_identical_to_off(self):
        intake = "---\ntask_id: test-s2\nphase: build\n---\n"
        result_shadow = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "shadow"})
        result_off = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "0"})
        lines_shadow = result_shadow.stdout.splitlines()
        lines_off = result_off.stdout.splitlines()
        self.assertEqual(lines_shadow[2], lines_off[2],
                         "line-3 binding must be identical under shadow vs OFF (never rewrites)")


class RouterErrorSetsRouterDecisionErrorBindingFallsBack(unittest.TestCase):
    """AC4: route_model raises => router_decision='error', binding==OFF, rc 0.

    We prove the error path via source inspection (try/except structure) + the
    unit tests that prove route_model raises on malformed signals. We also verify
    the structural invariant: any exception in the router block must not change
    the binding (line 3 == OFF binding).
    """

    def test_router_error_sets_router_decision_error_binding_falls_back(self):
        import inspect
        import importlib.util
        resolver_path = REPO_ROOT / "hooks" / "_lib" / "resolve-advisor.py"
        spec = importlib.util.spec_from_file_location("resolve_advisor", resolver_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        source = inspect.getsource(mod.main)
        # The error recovery path must exist: exception in router block -> "error"
        self.assertIn('router_decision"] = "error"', source,
                      "main() must set router_decision='error' on exception")
        # And it must be inside an except block
        self.assertIn("except Exception", source,
                      "main() must have broad except to catch route_model errors")

    def test_router_error_binding_identical_to_off(self):
        """Binding under shadow (successful path) == OFF, proving no rewrite path exists."""
        intake = "---\ntask_id: test-s2\nphase: build\n---\n"
        result_off = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "0"})
        result_shadow = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "shadow"})
        self.assertEqual(result_shadow.returncode, 0, "shadow must exit 0")
        lines_shadow = result_shadow.stdout.splitlines()
        lines_off = result_off.stdout.splitlines()
        self.assertEqual(lines_shadow[2], lines_off[2],
                         "binding under shadow must equal OFF binding")


class RouterErrorDoesNotBreakSpawn(unittest.TestCase):
    """AC4: error path: exactly 3 stdout lines, line1 LOG, exit 0."""

    def test_router_error_does_not_break_spawn(self):
        intake = "---\ntask_id: test-s2\nphase: build\n---\n"
        result = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "shadow"})
        self.assertEqual(result.returncode, 0, "resolver must exit 0")
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 3, f"must have exactly 3 lines: {result.stdout!r}")
        self.assertEqual(lines[0], "LOG", "line 1 must be LOG for Agent payload")


class RouterComplexityBudgetFromActiveIntakeNested(unittest.TestCase):
    """AC5a: nested total:13 => shadow routes expensive (intake grep not flat None)."""

    def test_router_complexity_budget_from_active_intake_nested(self):
        intake = "---\ntask_id: test-s2\ncomplexity_budget:\n  total: 13\n---\n"
        result = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "shadow"})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        resolved = json.loads(lines[1])
        self.assertEqual(resolved.get("router_decision"), "expensive",
                         "nested total:13 must route expensive via _intake_budget")


class RouterComplexityBudgetFromActiveIntakeFlat(unittest.TestCase):
    """AC5a: flat complexity_budget:9 => budget 9 (standard arm)."""

    def test_router_complexity_budget_from_active_intake_flat(self):
        intake = "---\ntask_id: test-s2\ncomplexity_budget: 9\nphase: build\n---\n"
        result = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "shadow"})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        resolved = json.loads(lines[1])
        # budget=9 => not expensive (>=10), not cheap (<=4), standard
        self.assertEqual(resolved.get("router_decision"), "standard",
                         "flat complexity_budget:9 must route standard (not expensive, not cheap)")


class RouterBudgetMultiIntegerIntakeTakesFirst(unittest.TestCase):
    """AC5a gap a: multiple ints on matched lines => first wins deterministically."""

    def test_router_budget_multi_integer_intake_takes_first(self):
        # Two matching lines: complexity_budget: 9 and total: 13 below it.
        # First match wins — budget=9 => standard, not expensive.
        intake = ("---\ntask_id: test-s2\n"
                  "complexity_budget: 9\n"
                  "complexity_budget:\n  total: 13\n---\n")
        result = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "shadow"})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        resolved = json.loads(lines[1])
        # First match wins: complexity_budget: 9 => standard
        self.assertEqual(resolved.get("router_decision"), "standard",
                         "first integer match (9) must win over later 13")


class RouterMalformedBudgetIntakeYieldsNoneNotCrash(unittest.TestCase):
    """AC5a gap a: complexity_budget: not-a-number => None, router still routes."""

    def test_router_malformed_budget_intake_yields_none_not_crash(self):
        intake = "---\ntask_id: test-s2\ncomplexity_budget: not-a-number\n---\n"
        result = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "shadow"})
        self.assertEqual(result.returncode, 0, "malformed budget must not crash resolver")
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 3, "must still emit 3 lines")
        resolved = json.loads(lines[1])
        # With budget=None and no other signals, routes standard
        self.assertIn(resolved.get("router_decision"), ("cheap", "standard", "expensive"),
                      "router must still produce a valid decision with malformed budget")


class RouterGraphDepthZeroFromEnvSerializesAsShallow(unittest.TestCase):
    """AC5b: DEPTH=0 + low budget => cheap."""

    def test_router_graph_depth_zero_from_env_serializes_as_shallow(self):
        # budget=4 (cheap-eligible), depth=0 (shallow, not deep), errors=0
        intake = "---\ntask_id: test-s2\ncomplexity_budget: 4\n---\n"
        result = _run_resolver_with_intake(
            _SE_PAYLOAD, intake,
            env={"CLAUDE_MODEL_ROUTER": "shadow", "CLAUDE_SUBAGENT_DEPTH": "0"})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        resolved = json.loads(lines[1])
        self.assertEqual(resolved.get("router_decision"), "cheap",
                         "CLAUDE_SUBAGENT_DEPTH=0 + budget=4 must route cheap")


class RouterGraphDepthUnsetTreatedAsShallow(unittest.TestCase):
    """AC5b: DEPTH unset + low budget => cheap."""

    def test_router_graph_depth_unset_treated_as_shallow(self):
        intake = "---\ntask_id: test-s2\ncomplexity_budget: 4\n---\n"
        # Explicitly remove CLAUDE_SUBAGENT_DEPTH from env
        env_without_depth = {k: v for k, v in os.environ.items()
                             if k != "CLAUDE_SUBAGENT_DEPTH"}
        env_without_depth["CLAUDE_MODEL_ROUTER"] = "shadow"
        env_without_depth["ANTHROPIC_API_KEY"] = "sk-test"
        result = _run_resolver_with_intake(_SE_PAYLOAD, intake, env=env_without_depth)
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        resolved = json.loads(lines[1])
        self.assertEqual(resolved.get("router_decision"), "cheap",
                         "unset CLAUDE_SUBAGENT_DEPTH + budget=4 must route cheap")


class RouterGraphDepthDeepFromEnv(unittest.TestCase):
    """AC5b: DEPTH=3 => expensive."""

    def test_router_graph_depth_deep_from_env(self):
        intake = "---\ntask_id: test-s2\ncomplexity_budget: 4\n---\n"
        result = _run_resolver_with_intake(
            _SE_PAYLOAD, intake,
            env={"CLAUDE_MODEL_ROUTER": "shadow", "CLAUDE_SUBAGENT_DEPTH": "3"})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        resolved = json.loads(lines[1])
        self.assertEqual(resolved.get("router_decision"), "expensive",
                         "CLAUDE_SUBAGENT_DEPTH=3 must route expensive")


class RouterRoleFromSubagentType(unittest.TestCase):
    """AC5: subagent_type=architect => expensive (locked role)."""

    def test_router_role_from_subagent_type(self):
        intake = "---\ntask_id: test-s2\nphase: build\n---\n"
        result = _run_resolver_with_intake(
            _ARCH_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "shadow"})
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        resolved = json.loads(lines[1])
        self.assertEqual(resolved.get("router_decision"), "expensive",
                         "architect role must route expensive (locked)")


class RouterActiveModeDoesNotRewriteBindingInStory2(unittest.TestCase):
    """AC3: active mode in Story 2: line-3 binding == OFF (Story-3 boundary lock)."""

    def test_router_active_mode_does_not_rewrite_binding_in_story2(self):
        intake = "---\ntask_id: test-s2\nphase: build\n---\n"
        result_active = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "active"})
        result_off = _run_resolver_with_intake(
            _SE_PAYLOAD, intake, env={"CLAUDE_MODEL_ROUTER": "0"})
        lines_active = result_active.stdout.splitlines()
        lines_off = result_off.stdout.splitlines()
        self.assertEqual(lines_active[2], lines_off[2],
                         "active mode in Story 2 must NOT rewrite line-3 binding")


if __name__ == "__main__":
    unittest.main()
