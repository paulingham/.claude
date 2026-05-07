"""Pure-function a11y assertion engine — TDD coverage for AC8–AC14, AC19–AC21.

Targets:
- `evaluate(snapshot, denylist) -> [findings]` — pure (AC11, AC14, AC19, AC20, AC21)
- `run(index_path, project_root=None) -> {verdict, findings, reason?}` — I/O wrapper
  (AC8, AC9, AC10, AC12)
"""
import copy
import json
import os
import unittest
from pathlib import Path

import a11y_assertions
from a11y_assertions import (
    DEFAULT_A6_DENYLIST,
    effective_a6_denylist,
    evaluate,
    run,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "a11y" / "assertions"


def _load(rel_path):
    return json.loads((FIXTURES / rel_path).read_text())


def _wrap_index(snapshot_path, captured=True, reason=None,
                a11y_global=None, schema_version=1):
    """Build an in-memory index.json dict pointing at one snapshot."""
    if a11y_global is None:
        a11y_global = {"captured": captured, "reason": reason,
                       "capture_path": "library" if captured else None}
    return {
        "schema_version": schema_version,
        "task_id": "test-task",
        "captured_at": "2026-05-07T11:30:00Z",
        "build_status": "PASS",
        "server_started": True,
        "routes": [
            {
                "route": "/dashboard",
                "screenshots": [],
                "a11y": {
                    "captured": True,
                    "capture_path": "library",
                    "snapshots": [
                        {"viewport": "desktop", "path": str(snapshot_path)}
                    ]
                }
            }
        ],
        "a11y_global": a11y_global,
    }


def _write_index_and_snapshot(tmp_path, snapshot_dict, **kwargs):
    snapshot_path = tmp_path / "snap.json"
    snapshot_path.write_text(json.dumps(snapshot_dict))
    index = _wrap_index(snapshot_path, **kwargs)
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(index))
    return index_path


class EvaluateIsPureNoIO(unittest.TestCase):
    """AC20 — evaluate() does no file I/O, no global state."""

    def test_evaluate_with_clean_snapshot_returns_empty_findings(self):
        snapshot = _load("a1/negative.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        self.assertEqual(findings, [])

    def test_evaluate_is_deterministic_across_repeated_calls(self):
        snapshot = _load("a1/positive.json")
        first = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        second = evaluate(copy.deepcopy(snapshot), DEFAULT_A6_DENYLIST)
        self.assertEqual(first, second)

    def test_evaluate_does_not_mutate_input_snapshot(self):
        snapshot = _load("a1/positive.json")
        before = json.dumps(snapshot, sort_keys=True)
        evaluate(snapshot, DEFAULT_A6_DENYLIST)
        after = json.dumps(snapshot, sort_keys=True)
        self.assertEqual(before, after)

    def test_evaluate_does_not_mutate_input_denylist(self):
        snapshot = _load("a6/positive.json")
        denylist = list(DEFAULT_A6_DENYLIST)
        before = list(denylist)
        evaluate(snapshot, denylist)
        self.assertEqual(before, denylist)


class A1InteractiveNeedsName(unittest.TestCase):
    """A1 — every interactive element has a non-empty accessible name."""

    def test_a1_positive_empty_name_button_triggers(self):
        snapshot = _load("a1/positive.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        ids = {f["assertion_id"] for f in findings}
        self.assertIn("A1", ids)

    def test_a1_negative_named_button_does_not_trigger(self):
        snapshot = _load("a1/negative.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a1_findings = [f for f in findings if f["assertion_id"] == "A1"]
        self.assertEqual(a1_findings, [])

    def test_a1_edge_aria_hidden_interactive_does_not_trigger_a1(self):
        # aria.hidden interactive node is excluded from A1 (handled by A4)
        snapshot = _load("a1/edge.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a1_findings = [f for f in findings if f["assertion_id"] == "A1"]
        self.assertEqual(a1_findings, [])


class A2ImgRequiresAlt(unittest.TestCase):
    """A2 — <img> without alt fails unless role=presentation."""

    def test_a2_positive_unalt_img_triggers(self):
        snapshot = _load("a2/positive.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        self.assertIn("A2", {f["assertion_id"] for f in findings})

    def test_a2_negative_alt_img_does_not_trigger(self):
        snapshot = _load("a2/negative.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a2 = [f for f in findings if f["assertion_id"] == "A2"]
        self.assertEqual(a2, [])

    def test_a2_edge_presentation_role_does_not_trigger(self):
        snapshot = _load("a2/edge.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a2 = [f for f in findings if f["assertion_id"] == "A2"]
        self.assertEqual(a2, [])


class A3FormControlsNamed(unittest.TestCase):
    """A3 — form controls have an accessible name."""

    def test_a3_positive_unnamed_textbox_triggers(self):
        snapshot = _load("a3/positive.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        self.assertIn("A3", {f["assertion_id"] for f in findings})

    def test_a3_negative_named_textbox_does_not_trigger(self):
        snapshot = _load("a3/negative.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a3 = [f for f in findings if f["assertion_id"] == "A3"]
        self.assertEqual(a3, [])

    def test_a3_edge_combobox_with_resolved_name_does_not_trigger(self):
        snapshot = _load("a3/edge.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a3 = [f for f in findings if f["assertion_id"] == "A3"]
        self.assertEqual(a3, [])

    def test_a3_edge_aria_hidden_textbox_does_not_trigger_a3(self):
        # aria.hidden interactive form control is excluded from A3
        # (handled by A4); avoids overlapping findings on the same node.
        snapshot = _load("a3/edge-aria-hidden.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a3 = [f for f in findings if f["assertion_id"] == "A3"]
        self.assertEqual(a3, [])
        # A4 still fires for aria-hidden interactive node — sanity check.
        a4 = [f for f in findings if f["assertion_id"] == "A4"]
        self.assertEqual(len(a4), 1)


class A4InteractiveNotAriaHidden(unittest.TestCase):
    """A4 (revised) — no interactive element is aria-hidden."""

    def test_a4_positive_aria_hidden_button_triggers(self):
        snapshot = _load("a4/positive.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        self.assertIn("A4", {f["assertion_id"] for f in findings})

    def test_a4_negative_visible_button_does_not_trigger(self):
        snapshot = _load("a4/negative.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a4 = [f for f in findings if f["assertion_id"] == "A4"]
        self.assertEqual(a4, [])

    def test_a4_edge_non_interactive_aria_hidden_does_not_trigger(self):
        snapshot = _load("a4/edge.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a4 = [f for f in findings if f["assertion_id"] == "A4"]
        self.assertEqual(a4, [])


class A5HeadingLevels(unittest.TestCase):
    """A5 — heading levels do not skip downward by more than 1 (DFS pre-order)."""

    def test_a5_positive_h1_then_h3_triggers(self):
        snapshot = _load("a5/positive.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        self.assertIn("A5", {f["assertion_id"] for f in findings})

    def test_a5_negative_h1_h2_h3_does_not_trigger(self):
        snapshot = _load("a5/negative.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a5 = [f for f in findings if f["assertion_id"] == "A5"]
        self.assertEqual(a5, [])

    def test_a5_edge_h1_h3_h2_triggers_only_on_h1_to_h3(self):
        # h1->h3 fires (skip), h3->h2 is upward and must not fire
        snapshot = _load("a5/edge.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a5 = [f for f in findings if f["assertion_id"] == "A5"]
        self.assertEqual(len(a5), 1)
        self.assertIn("Bad jump", a5[0].get("breadcrumb", ""))


class A6Denylist(unittest.TestCase):
    """A6 — buttons/links must not use anti-pattern names."""

    def test_a6_positive_click_here_link_triggers(self):
        snapshot = _load("a6/positive.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        self.assertIn("A6", {f["assertion_id"] for f in findings})

    def test_a6_negative_descriptive_link_does_not_trigger(self):
        snapshot = _load("a6/negative.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a6 = [f for f in findings if f["assertion_id"] == "A6"]
        self.assertEqual(a6, [])

    def test_a6_edge_parenthetical_extra_does_not_trigger(self):
        snapshot = _load("a6/edge.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a6 = [f for f in findings if f["assertion_id"] == "A6"]
        self.assertEqual(a6, [])


class A6DenylistOverrides(unittest.TestCase):
    """AC21 — project-overridable A6 denylist (additions and removals)."""

    def test_additions_extend_denylist(self):
        merged = effective_a6_denylist(
            DEFAULT_A6_DENYLIST,
            {"a6_denylist_additions": ["custom-bad-name"],
             "a6_denylist_removals": []})
        self.assertIn("custom-bad-name", merged)

    def test_removals_drop_from_denylist(self):
        merged = effective_a6_denylist(
            DEFAULT_A6_DENYLIST,
            {"a6_denylist_additions": [],
             "a6_denylist_removals": ["click here"]})
        self.assertNotIn("click here", merged)

    def test_removals_then_additions_compose(self):
        merged = effective_a6_denylist(
            DEFAULT_A6_DENYLIST,
            {"a6_denylist_additions": ["here-bad"],
             "a6_denylist_removals": ["click here"]})
        self.assertNotIn("click here", merged)
        self.assertIn("here-bad", merged)

    def test_normalises_additions_to_lower_trim(self):
        merged = effective_a6_denylist(
            DEFAULT_A6_DENYLIST,
            {"a6_denylist_additions": ["  Custom-BAD  "],
             "a6_denylist_removals": []})
        self.assertIn("custom-bad", merged)


class FindingShape(unittest.TestCase):
    """AC10 + AC14 — finding shape with breadcrumb and locator fields."""

    def test_a1_finding_includes_required_fields(self):
        snapshot = _load("a1/positive.json")
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a1 = [f for f in findings if f["assertion_id"] == "A1"][0]
        for key in ("assertion_id", "role", "path_in_tree", "breadcrumb",
                    "route", "viewport"):
            self.assertIn(key, a1, f"missing field {key!r} in {a1!r}")
            self.assertIsNotNone(a1[key])

    def test_breadcrumb_uses_ancestor_names_with_role_fallback(self):
        # Build a tree where one ancestor has empty name -> role fallback.
        snapshot = {
            "schema_version": 1,
            "route": "/dashboard",
            "viewport": "desktop",
            "captured_at": "2026-05-07T11:30:00Z",
            "tree": {
                "role": "WebArea", "name": "Dashboard", "tag": "html",
                "interactive": False, "disabled": False,
                "aria": {"hidden": False, "level": None, "checked": None,
                         "expanded": None, "pressed": None, "selected": None},
                "ref": None,
                "children": [
                    {
                        "role": "navigation", "name": "",  # empty -> fallback
                        "tag": "nav", "interactive": False, "disabled": False,
                        "aria": {"hidden": False, "level": None,
                                 "checked": None, "expanded": None,
                                 "pressed": None, "selected": None},
                        "ref": None,
                        "children": [
                            {
                                "role": "button", "name": "",
                                "tag": "button", "interactive": True,
                                "disabled": False,
                                "aria": {"hidden": False, "level": None,
                                         "checked": None, "expanded": None,
                                         "pressed": None, "selected": None},
                                "ref": None, "children": []
                            }
                        ]
                    }
                ]
            }
        }
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        a1 = [f for f in findings if f["assertion_id"] == "A1"][0]
        # Ancestors before the offending node: WebArea(name=Dashboard),
        # navigation(name="") -> fallback to role.
        self.assertIn("Dashboard", a1["breadcrumb"])
        self.assertIn("navigation", a1["breadcrumb"])


class RunSkipsWhenIndexAbsent(unittest.TestCase):
    """AC8 — index missing or unparsable returns SKIP, reason=index-absent."""

    def test_skip_when_index_path_does_not_exist(self):
        result = run("/nonexistent/path/index.json")
        self.assertEqual(result["verdict"], "SKIP")
        self.assertEqual(result["reason"], "index-absent")

    def test_skip_when_index_is_malformed_json(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False,
                                         mode="w") as fh:
            fh.write("{not valid json")
            tmp = fh.name
        try:
            result = run(tmp)
            self.assertEqual(result["verdict"], "SKIP")
            self.assertEqual(result["reason"], "index-absent")
        finally:
            os.unlink(tmp)


class RunSkipsWhenCapturedFalse(unittest.TestCase):
    """AC9 — a11y_global.captured == false yields SKIP with preserved reason."""

    def test_skip_preserves_reason_non_web_target(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index_path = _write_index_and_snapshot(
                tmp_path, _load("a1/negative.json"),
                a11y_global={"captured": False,
                             "reason": "non-web-target",
                             "capture_path": None})
            result = run(str(index_path))
            self.assertEqual(result["verdict"], "SKIP")
            self.assertEqual(result["reason"], "non-web-target")

    def test_skip_reason_mcp_unavailable_passed_through(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index_path = _write_index_and_snapshot(
                tmp_path, _load("a1/negative.json"),
                a11y_global={"captured": False,
                             "reason": "mcp-unavailable",
                             "capture_path": None})
            result = run(str(index_path))
            self.assertEqual(result["verdict"], "SKIP")
            self.assertEqual(result["reason"], "mcp-unavailable")


class RunReturnsFailOnA1Violation(unittest.TestCase):
    """AC10 — A1 violation produces FAIL with structured finding."""

    def test_a1_empty_name_button_triggers_fail_with_finding(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index_path = _write_index_and_snapshot(
                tmp_path, _load("a1/positive.json"))
            result = run(str(index_path))
            self.assertEqual(result["verdict"], "FAIL")
            self.assertEqual(len(result["findings"]), 1)
            f = result["findings"][0]
            self.assertEqual(f["assertion_id"], "A1")
            self.assertEqual(f["role"], "button")
            self.assertIn("path_in_tree", f)
            self.assertIn("breadcrumb", f)
            self.assertEqual(f["route"], "/dashboard")
            self.assertEqual(f["viewport"], "desktop")


class RunSkipsRouteOnPerRouteCaptureError(unittest.TestCase):
    """AC12 — per-route capture error => SKIP route, never FAIL the patch."""

    def test_route_with_captured_false_skipped_other_routes_evaluated(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            good_snap = tmp_path / "good.json"
            good_snap.write_text(json.dumps(_load("a1/negative.json")))
            index = {
                "schema_version": 1,
                "task_id": "test-task",
                "captured_at": "2026-05-07T11:30:00Z",
                "build_status": "PASS",
                "server_started": True,
                "routes": [
                    {
                        "route": "/dashboard",
                        "screenshots": [],
                        "a11y": {"captured": True,
                                 "capture_path": "library",
                                 "snapshots": [
                                     {"viewport": "desktop",
                                      "path": str(good_snap)}
                                 ]}
                    },
                    {
                        "route": "/profile",
                        "screenshots": [],
                        "a11y": {"captured": False,
                                 "reason": "capture-error",
                                 "snapshots": []}
                    }
                ],
                "a11y_global": {"captured": True,
                                "capture_path": "library",
                                "reason": None}
            }
            index_path = tmp_path / "index.json"
            index_path.write_text(json.dumps(index))
            result = run(str(index_path))
            self.assertEqual(result["verdict"], "PASS")
            skipped_routes = result.get("skipped_routes", [])
            self.assertIn("/profile", [r["route"] for r in skipped_routes])


class RunSkipsOnSchemaIncompatible(unittest.TestCase):
    """AC19 — major schema_version mismatch => SKIP."""

    def test_major_version_mismatch_returns_schema_incompatible(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index_path = _write_index_and_snapshot(
                tmp_path, _load("a1/negative.json"), schema_version=2)
            result = run(str(index_path))
            self.assertEqual(result["verdict"], "SKIP")
            self.assertEqual(result["reason"], "schema-incompatible")
            self.assertEqual(result["expected"], 1)
            self.assertEqual(result["found"], 2)


class RunUsesProjectOverrides(unittest.TestCase):
    """AC21 — .claude/a11y-overrides.json is honoured when project_root passed."""

    def test_run_applies_overrides_from_project_root(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Project root with overrides removing 'click here'.
            project = tmp_path / "proj"
            (project / ".claude").mkdir(parents=True)
            (project / ".claude" / "a11y-overrides.json").write_text(
                json.dumps({"a6_denylist_additions": [],
                            "a6_denylist_removals": ["click here"]}))
            index_path = _write_index_and_snapshot(
                tmp_path, _load("a6/positive.json"))
            result = run(str(index_path), project_root=str(project))
            # With 'click here' removed from denylist, A6 should NOT fire.
            a6 = [f for f in result.get("findings", [])
                  if f.get("assertion_id") == "A6"]
            self.assertEqual(a6, [])


class MalformedOverridesEmitsWarning(unittest.TestCase):
    """Malformed overrides JSON: warn on stderr, fall back to default denylist."""

    def test_malformed_overrides_warns_to_stderr_and_uses_default(self):
        import io
        import tempfile
        from contextlib import redirect_stderr
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            project = tmp_path / "proj"
            (project / ".claude").mkdir(parents=True)
            (project / ".claude" / "a11y-overrides.json").write_text(
                "{not valid json")
            index_path = _write_index_and_snapshot(
                tmp_path, _load("a6/positive.json"))
            buf = io.StringIO()
            with redirect_stderr(buf):
                result = run(str(index_path), project_root=str(project))
            # Default denylist still in effect — A6 fires for "click here".
            a6_ids = {f.get("assertion_id") for f in result.get("findings", [])}
            self.assertIn("A6", a6_ids)
            # Warning surfaced on stderr with the offending path.
            err = buf.getvalue()
            self.assertIn("a11y_assertions", err)
            self.assertIn("a11y-overrides.json", err)
            self.assertIn("falling back", err)


if __name__ == "__main__":
    unittest.main()
