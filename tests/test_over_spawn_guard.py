"""Tests for over_spawn_guard.py — AC1-AC3, unit-level.

Tests for phase inference, ceiling formula, counter mechanics,
and slice_count resolution. Hermetic and fast.
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

# conftest.py adds hooks/_lib to sys.path; this guard covers direct pytest runs
_HOOKS_LIB = str(Path(__file__).resolve().parents[1] / "hooks" / "_lib")
if _HOOKS_LIB not in sys.path:
    sys.path.insert(0, _HOOKS_LIB)


class TestCeilingFormula(unittest.TestCase):
    """AC1/AC2: ceiling_for returns correct values per phase + slice_count."""

    def test_ceiling_final_gate_1slice_warns(self):
        """AC1: 1-slice task → final-gate ceiling == 1, so 4 agents exceed it."""
        from over_spawn_guard import ceiling_for
        self.assertEqual(ceiling_for("final-gate", 1), 1)

    def test_ceiling_build_n_on_n_silent(self):
        """AC2: N build agents on N-slice task → ceiling == N (never false-warns)."""
        from over_spawn_guard import ceiling_for
        self.assertEqual(ceiling_for("build", 4), 4)

    def test_ceiling_final_gate_8slice_proportionate(self):
        """AC1: 8-slice task → final-gate ceiling == ceil(8/2) == 4, not floor(4)."""
        from over_spawn_guard import ceiling_for
        self.assertEqual(ceiling_for("final-gate", 8), 4)

    def test_ceiling_uses_math_ceil_not_floor(self):
        """AC1: 3-slice task → final-gate ceiling == ceil(3/2) == 2, not floor(1)."""
        from over_spawn_guard import ceiling_for
        self.assertEqual(ceiling_for("final-gate", 3), 2)

    def test_ceiling_review_1slice(self):
        """Review ceiling == max(2, ceil(slice_count/2)) == 2 for 1 slice."""
        from over_spawn_guard import ceiling_for
        self.assertEqual(ceiling_for("review", 1), 2)

    def test_ceiling_review_8slice(self):
        """Review ceiling == max(2, ceil(8/2)) == 4 for 8 slices."""
        from over_spawn_guard import ceiling_for
        self.assertEqual(ceiling_for("review", 8), 4)

    def test_ceiling_unknown_phase_returns_inf(self):
        """Unknown phase → math.inf (never warns)."""
        from over_spawn_guard import ceiling_for
        self.assertEqual(ceiling_for("unknown-phase", 1), math.inf)

    def test_ceiling_build_1slice(self):
        """Build ceiling == max(slice_count, 1) == 1 for 1 slice."""
        from over_spawn_guard import ceiling_for
        self.assertEqual(ceiling_for("build", 1), 1)

    def test_ceiling_build_zero_slice_count_floors_to_1(self):
        """Adversarial: slice_count=0 → build ceiling min is 1 (max guard)."""
        from over_spawn_guard import ceiling_for
        self.assertGreaterEqual(ceiling_for("build", 0), 1)

    def test_ceiling_final_gate_zero_slice_count_floors_to_1(self):
        """Adversarial: slice_count=0 → final-gate ceiling min is 1 (max guard)."""
        from over_spawn_guard import ceiling_for
        self.assertGreaterEqual(ceiling_for("final-gate", 0), 1)


class TestInferPhase(unittest.TestCase):
    """AC1: infer_phase extracts phase from spawn prompt role marker."""

    def test_infer_phase_from_prompt_role_marker_patch_critic(self):
        """AC1: patch-critic role in prompt → final-gate phase."""
        from over_spawn_guard import infer_phase
        prompt = "Read ~/.claude/agents/patch-critic.md for your full role definition"
        self.assertEqual(infer_phase(prompt), "final-gate")

    def test_infer_phase_spec_blind_validator_final_gate(self):
        """AC1: spec-blind-validator → final-gate."""
        from over_spawn_guard import infer_phase
        prompt = "Read ~/.claude/agents/spec-blind-validator.md for your role"
        self.assertEqual(infer_phase(prompt), "final-gate")

    def test_infer_phase_product_reviewer_final_gate(self):
        """AC1: product-reviewer → final-gate."""
        from over_spawn_guard import infer_phase
        prompt = "Read ~/.claude/agents/product-reviewer.md for your role"
        self.assertEqual(infer_phase(prompt), "final-gate")

    def test_infer_phase_qa_engineer_final_gate(self):
        """AC1: qa-engineer → final-gate."""
        from over_spawn_guard import infer_phase
        prompt = "Read ~/.claude/agents/qa-engineer.md for your role"
        self.assertEqual(infer_phase(prompt), "final-gate")

    def test_infer_phase_code_reviewer_review(self):
        """AC1: code-reviewer → review phase."""
        from over_spawn_guard import infer_phase
        prompt = "Read ~/.claude/agents/code-reviewer.md for your role"
        self.assertEqual(infer_phase(prompt), "review")

    def test_infer_phase_security_engineer_review(self):
        """AC1: security-engineer → review phase."""
        from over_spawn_guard import infer_phase
        prompt = "Read ~/.claude/agents/security-engineer.md for your role"
        self.assertEqual(infer_phase(prompt), "review")

    def test_infer_phase_software_engineer_build(self):
        """AC1: software-engineer → build phase."""
        from over_spawn_guard import infer_phase
        prompt = "Read ~/.claude/agents/software-engineer.md for your role"
        self.assertEqual(infer_phase(prompt), "build")

    def test_infer_phase_unknown_role_returns_none(self):
        """AC2: no recognisable role marker → None (silent)."""
        from over_spawn_guard import infer_phase
        self.assertIsNone(infer_phase("some unrelated spawn prompt"))

    def test_infer_phase_subagent_type_fallback(self):
        """infer_phase uses subagent_type as fallback when prompt has no marker."""
        from over_spawn_guard import infer_phase
        # subagent_type fallback for patch-critic role
        self.assertEqual(infer_phase("", "patch-critic"), "final-gate")

    def test_infer_phase_empty_inputs_returns_none(self):
        """Empty prompt and empty subagent_type → None."""
        from over_spawn_guard import infer_phase
        self.assertIsNone(infer_phase("", ""))

    def test_infer_phase_frontend_engineer_build(self):
        """AC1: frontend-engineer → build phase."""
        from over_spawn_guard import infer_phase
        prompt = "Read ~/.claude/agents/frontend-engineer.md for your role"
        self.assertEqual(infer_phase(prompt), "build")


class TestBumpCounter(unittest.TestCase):
    """AC3: bump_counter is monotonic per file."""

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_bump_counter_monotonic(self):
        """AC3: 3 sequential bumps on same path → 1, 2, 3."""
        from over_spawn_guard import bump_counter
        path = os.path.join(self._tmpdir, "test.count")
        self.assertEqual(bump_counter(path), 1)
        self.assertEqual(bump_counter(path), 2)
        self.assertEqual(bump_counter(path), 3)

    def test_bump_counter_starts_at_1_for_new_file(self):
        """AC3: new counter file starts at 1."""
        from over_spawn_guard import bump_counter
        path = os.path.join(self._tmpdir, "new.count")
        self.assertEqual(bump_counter(path), 1)

    def test_bump_counter_creates_parent_dirs(self):
        """AC3: bump_counter creates parent directories if missing."""
        from over_spawn_guard import bump_counter
        path = os.path.join(self._tmpdir, "sub", "dir", "test.count")
        result = bump_counter(path)
        self.assertEqual(result, 1)
        self.assertTrue(os.path.exists(path))


class TestResolveSliceCount(unittest.TestCase):
    """AC3: resolve_slice_count returns (None, None) when no active pipeline."""

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_resolve_slice_count_no_pipeline_returns_none(self):
        """AC3: empty state dir → (None, None)."""
        from over_spawn_guard import resolve_slice_count
        result = resolve_slice_count(self._tmpdir)
        self.assertEqual(result, (None, None))

    def test_resolve_slice_count_v1_plan_returns_1(self):
        """AC3: v1/non-DAG plan → slice_count=1 (default for single-slice)."""
        from over_spawn_guard import resolve_slice_count
        task_dir = os.path.join(self._tmpdir, "my-task")
        os.makedirs(task_dir)
        # Write a minimal plan.md that is NOT v2 (no schema_version: 2)
        plan_path = os.path.join(task_dir, "plan.md")
        Path(plan_path).write_text(
            "---\ntask_id: my-task\nphase: plan\nverdict: in_progress\n---\n\n# Plan\n"
        )
        result = resolve_slice_count(self._tmpdir)
        self.assertEqual(result, ("my-task", 1))

    def test_resolve_slice_count_v2_plan_returns_slice_count(self):
        """AC3: v2 DAG plan with 4 slices → slice_count=4."""
        from over_spawn_guard import resolve_slice_count
        task_dir = os.path.join(self._tmpdir, "dag-task")
        os.makedirs(task_dir)
        plan_path = os.path.join(task_dir, "plan.md")
        Path(plan_path).write_text(
            "---\ntask_id: dag-task\nschema_version: 2\nphase: plan\nverdict: in_progress\n---\n\n"
            "# Plan\n\n## Slices\n\n```yaml\nslices:\n"
            "  - id: slice-a\n    depends-on: []\n    description: First\n"
            "  - id: slice-b\n    depends-on: [slice-a]\n    description: Second\n"
            "  - id: slice-c\n    depends-on: [slice-b]\n    description: Third\n"
            "  - id: slice-d\n    depends-on: [slice-c]\n    description: Fourth\n"
            "```\n"
        )
        result = resolve_slice_count(self._tmpdir)
        self.assertEqual(result, ("dag-task", 4))


class TestCounterPath(unittest.TestCase):
    """AC3: counter_path produces expected keyed path."""

    def test_counter_path_structure(self):
        """counter_path encodes session_id + task_id + phase in the filename."""
        from over_spawn_guard import counter_path
        path = counter_path("/metrics", "sess-1", "my-task", "final-gate")
        self.assertEqual(path, "/metrics/sess-1/over-spawn/my-task--final-gate.count")

    def test_counter_path_different_tasks_differ(self):
        """Different task_ids produce different counter paths (no cross-pipeline bleed)."""
        from over_spawn_guard import counter_path
        p1 = counter_path("/m", "s", "task-a", "build")
        p2 = counter_path("/m", "s", "task-b", "build")
        self.assertNotEqual(p1, p2)

    def test_counter_path_different_phases_differ(self):
        """Different phases produce different counter paths."""
        from over_spawn_guard import counter_path
        p1 = counter_path("/m", "s", "t", "build")
        p2 = counter_path("/m", "s", "t", "final-gate")
        self.assertNotEqual(p1, p2)


class TestSafeComponent(unittest.TestCase):
    """Security: _safe_component strips path-traversal characters."""

    def test_safe_component_strips_dots_and_slashes(self):
        """../../../etc/passwd → '' (all unsafe chars removed, mirrors session-id.sh)."""
        from over_spawn_guard import _safe_component
        self.assertEqual(_safe_component("../../etc/passwd"), "etcpasswd")

    def test_safe_component_keeps_alphanum_underscore_hyphen(self):
        """[A-Za-z0-9_-] characters are preserved unchanged."""
        from over_spawn_guard import _safe_component
        self.assertEqual(_safe_component("abc-123_XYZ"), "abc-123_XYZ")

    def test_safe_component_none_returns_empty(self):
        """None input returns empty string (no crash)."""
        from over_spawn_guard import _safe_component
        self.assertEqual(_safe_component(None), "")

    def test_counter_path_traversal_stays_inside_metrics_dir(self):
        """Crafted session_id with ../ cannot escape the metrics base dir."""
        import over_spawn_guard
        metrics_dir = "/metrics"
        crafted_session = "../../../tmp/evil"
        crafted_task = "task-x"
        path = over_spawn_guard.counter_path(
            metrics_dir,
            over_spawn_guard._safe_component(crafted_session),
            over_spawn_guard._safe_component(crafted_task),
            "build",
        )
        self.assertTrue(
            path.startswith(metrics_dir),
            f"Path '{path}' escapes metrics dir '{metrics_dir}'",
        )


class TestActivePipelineDeterminism(unittest.TestCase):
    """FINDING 2: _active_task_id returns sorted(lines)[0] for determinism."""

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_plan(self, task_id: str) -> None:
        task_dir = os.path.join(self._tmpdir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        Path(os.path.join(task_dir, "plan.md")).write_text(
            f"---\ntask_id: {task_id}\nphase: plan\nverdict: in_progress\n---\n\n# Plan\n"
        )

    def test_deterministic_with_multiple_in_progress_pipelines(self):
        """Hardened: 3-task fixture (middle written first) always returns sorted-first.

        Write order: mmm-task, aaa-task, zzz-task.  The middle-sorted task is
        written first so that on any filesystem ordering grep might return
        mmm-task or zzz-task first.  The correct implementation (sorted(lines)[0])
        must return aaa-task regardless of grep output order.  The mutant
        (lines[0]) would return whichever path grep happens to emit first —
        which is NEVER aaa-task when grep returns mmm-task or zzz-task first,
        so the test deterministically kills the mutant.
        """
        from over_spawn_guard import resolve_slice_count
        self._write_plan("mmm-task")   # written first (middle-sorted)
        self._write_plan("aaa-task")   # written second (sorted-first)
        self._write_plan("zzz-task")   # written last (sorted-last)
        task_id, _ = resolve_slice_count(self._tmpdir)
        self.assertEqual(task_id, "aaa-task",
                         "Expected sorted-first task; got non-deterministic result")

    def test_sorted_first_kills_lines0_mutant(self):
        """Directly proves sorted(lines)[0] != lines[0] for non-sorted grep output.

        Patches subprocess.run to return paths in mmm/zzz/aaa order (i.e. the
        grep-first entry is NOT the alphabetically-first task).  With the real
        implementation (sorted(lines)[0]) the result is aaa-task.  With the
        mutant (lines[0]) the result would be mmm-task.  This test is immune to
        filesystem ordering because grep output is fully controlled by the mock.
        """
        import unittest.mock as mock
        self._write_plan("mmm-task")
        self._write_plan("aaa-task")
        self._write_plan("zzz-task")

        mmm_path = os.path.join(self._tmpdir, "mmm-task", "plan.md")
        zzz_path = os.path.join(self._tmpdir, "zzz-task", "plan.md")
        aaa_path = os.path.join(self._tmpdir, "aaa-task", "plan.md")
        # grep output: mmm first, then zzz, then aaa — intentionally NOT sorted
        fake_stdout = "\n".join([mmm_path, zzz_path, aaa_path]) + "\n"

        fake_result = mock.MagicMock()
        fake_result.stdout = fake_stdout

        import over_spawn_guard
        with mock.patch("subprocess.run", return_value=fake_result):
            task_id = over_spawn_guard._active_task_id(self._tmpdir)

        self.assertEqual(
            task_id, "aaa-task",
            "sorted(lines)[0] must return aaa-task regardless of grep output order; "
            "lines[0] would have returned mmm-task (mutant survival proof)"
        )

    def test_deterministic_ordering_stable_across_calls(self):
        """Repeated calls with same state dir yield the same task_id."""
        from over_spawn_guard import resolve_slice_count
        self._write_plan("beta-task")
        self._write_plan("alpha-task")
        result1, _ = resolve_slice_count(self._tmpdir)
        result2, _ = resolve_slice_count(self._tmpdir)
        self.assertEqual(result1, result2, "resolve_slice_count must be deterministic")


if __name__ == "__main__":
    unittest.main()
