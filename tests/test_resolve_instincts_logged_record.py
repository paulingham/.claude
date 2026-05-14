"""Tests for the JSONL logged record (slice-b AC6, AC6c).

_resolved() must compute and report the effective floor via the shared
helper, threaded with the subagent_type. The empty-categories early-return
path still reports the effective floor (count_kept == 0).
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import patch

_HOOKS_LIB = Path(__file__).resolve().parents[1] / "hooks" / "_lib"
sys.path.insert(0, str(_HOOKS_LIB))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "_ri_logged", _HOOKS_LIB / "resolve-instincts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_agent(tmp, name, body):
    (Path(tmp) / f"{name}.md").write_text(f"---\n{body}---\nbody")


class LoggedRecordReflectsEffectiveFloor(unittest.TestCase):
    def test_logged_record_reflects_effective_floor_for_review_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_agent(tmp, "code-reviewer",
                         "name: code-reviewer\n"
                         "instinct_categories: [testing]\n"
                         "min_confidence: 0.5\n")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp},
                            clear=False):
                ri = _load_module()
                payload = {"tool_name": "Agent",
                           "tool_input": {"subagent_type": "code-reviewer"}}
                with mock.patch.object(ri, "load_instincts", return_value=[]), \
                     mock.patch.object(ri, "project_hash", return_value="x"), \
                     mock.patch.object(ri, "write_log") as wl:
                    ri._handle_agent_spawn(payload, "code-reviewer")
        resolved = wl.call_args.args[2]
        self.assertEqual(resolved["min_confidence"], 0.5)


class EmptyCategoriesStillReportsFloor(unittest.TestCase):
    def test_empty_categories_review_role_still_reports_effective_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_agent(tmp, "code-reviewer",
                         "name: code-reviewer\n"
                         "instinct_categories: []\n"
                         "min_confidence: 0.5\n")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp},
                            clear=False):
                ri = _load_module()
                payload = {"tool_name": "Agent",
                           "tool_input": {"subagent_type": "code-reviewer"}}
                with mock.patch.object(ri, "load_instincts", return_value=[]), \
                     mock.patch.object(ri, "project_hash", return_value="x"), \
                     mock.patch.object(ri, "write_log") as wl:
                    ri._handle_agent_spawn(payload, "code-reviewer")
        resolved = wl.call_args.args[2]
        self.assertEqual(resolved["min_confidence"], 0.5)
        self.assertEqual(resolved["count_kept"], 0)


if __name__ == "__main__":
    unittest.main()
