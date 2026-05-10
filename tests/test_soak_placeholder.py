"""Slice D — DAG schema v2 soak-end placeholder tests.

Asserts the placeholder pipeline file at
`pipeline-state/wave-dag-soak-end/pipeline.md` exists, carries the M4-fix
frontmatter (`not_before`, `parent_pipeline`, `soak_window_days`,
`weekly_resurface`), and that its body documents the cleanup gate, cleanup
actions, and the three operator escape options for gate-red day.

AC4 mocks today's date forward past `not_before` and asserts that the
DUAL_PATH active-pipeline scanner surfaces the placeholder. Today the
scanner returns ALL pipeline.md files unconditionally — `not_before`
filtering is a slice-c-consumer carryforward — so the AC4 assertion is
"path is in the scan result", not "path is *only* surfaced after
not_before".
"""
import datetime
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = ROOT / "pipeline-state" / "wave-dag-soak-end" / "pipeline.md"
HOOKS_LIB = ROOT / "hooks" / "_lib"


def _parse_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            # Strip inline comments after the value
            value = v.split("#", 1)[0].strip()
            fm[k.strip()] = value
    return fm


def _read_placeholder():
    return PLACEHOLDER.read_text(encoding="utf-8")


class SoakPlaceholderFileExistsWithNotBefore(unittest.TestCase):
    """AC1 — frontmatter contract."""

    def test_soak_placeholder_file_exists_with_not_before(self):
        self.assertTrue(
            PLACEHOLDER.is_file(),
            f"missing soak-end placeholder: {PLACEHOLDER}",
        )
        fm = _parse_frontmatter(_read_placeholder())
        self.assertEqual(
            fm.get("not_before"), "2026-08-08T00:00:00Z",
            "frontmatter not_before must be 2026-08-08T00:00:00Z (90d after merge anchor)",
        )
        self.assertEqual(
            fm.get("parent_pipeline"), "architect-plan-dag",
            "frontmatter parent_pipeline must reference the originating pipeline",
        )
        self.assertEqual(
            fm.get("soak_window_days"), "90",
            "frontmatter soak_window_days must be 90",
        )

    def test_soak_placeholder_has_weekly_resurface_flag(self):
        fm = _parse_frontmatter(_read_placeholder())
        self.assertEqual(
            fm.get("weekly_resurface"), "true",
            "M4 fix requires weekly_resurface: true so SessionStart re-prompts the operator",
        )


class SoakPlaceholderBodyDocumentsCleanupContract(unittest.TestCase):
    """AC2 — body cites cleanup gate query + cleanup actions."""

    def test_soak_placeholder_documents_cleanup_gate(self):
        body = _read_placeholder()
        # Gate query: scan plan.md files for ones missing schema_version: 2.
        self.assertIn(
            "schema_version: 2", body,
            "body must cite the v1-detection gate using schema_version: 2",
        )
        self.assertIn(
            "find pipeline-state", body,
            "body must cite the find-based scan that locates v1 plans",
        )
        # Cleanup target locations.
        self.assertIn(
            "hooks/_lib/plan_dag_resolver.py", body,
            "body must name the v1-rejection branch removal target",
        )
        self.assertIn(
            "orchestrator/parallel-dispatch-details.md", body,
            "body must name the legacy multi-slice dispatch removal target",
        )


class SoakPlaceholderDocumentsGateRedOptions(unittest.TestCase):
    """AC3 (M4 fix) — body lists three operator options for gate-red day."""

    def test_soak_placeholder_documents_gate_red_options(self):
        body = _read_placeholder()
        # Three operator options documented.
        self.assertIn(
            "extend", body.lower(),
            "body must document option 1: extend the soak window",
        )
        self.assertIn(
            "abandon", body.lower(),
            "body must document option 2: abandon stale v1 plans",
        )
        self.assertIn(
            "CLAUDE_FORCE_V1_DRAIN=1", body,
            "body must cite the force-merge env hatch CLAUDE_FORCE_V1_DRAIN=1",
        )
        # Weekly resurface mechanism named in body too (cross-references frontmatter).
        self.assertIn(
            "status.md", body,
            "body must reference the status.md sibling file written by the scanner",
        )


class SessionStartResurfacesPlaceholderAfterNotBefore(unittest.TestCase):
    """AC4 — mock-time-forward scan returns the placeholder path.

    Today's `_psp_find_active_pipelines` returns ALL pipeline.md files
    unconditionally (no `not_before` filter). The placeholder therefore
    surfaces on every scan; AC4 verifies the path is *in* the scan
    result. `not_before` filtering is documented as a slice-c-consumer
    carryforward.
    """

    def setUp(self):
        if str(HOOKS_LIB) not in sys.path:
            sys.path.insert(0, str(HOOKS_LIB))

    def test_session_start_resurfaces_placeholder_after_not_before(self):
        from pipeline_state_paths import find_pipeline_files

        state_dir = ROOT / "pipeline-state"
        # Mock time forward past not_before. Even with filtering wired in
        # downstream, the placeholder must surface here.
        future = datetime.datetime(2026, 8, 9, 0, 0, 0)
        with mock.patch("time.time", return_value=future.timestamp()):
            paths = [Path(p).resolve() for p in find_pipeline_files(state_dir)]

        self.assertIn(
            PLACEHOLDER.resolve(), paths,
            "after not_before, _psp_find_active_pipelines must include the soak-end placeholder",
        )


if __name__ == "__main__":
    unittest.main()
