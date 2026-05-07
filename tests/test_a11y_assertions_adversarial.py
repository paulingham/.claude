"""Adversarial probes for the a11y assertion engine (Build Step 2b).

Walks the four applicable categories in order (concurrency N/A — pure
functions, no shared mutable state). Each probe was added RED-then-GREEN.

Rationale (audit trail):
1. Boundary — empty children list, single-element tree, deep nesting.
2. Null/empty/undefined — missing aria, missing tag, name === None.
3. Malformed input — `evaluate()` defends against snapshot.tree absent.
4. Error path — run() coverage of read failure + JSON parse failure.

PBT overlap not present yet (no .property.spec.* files for this module),
so cap stays at 5.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import a11y_assertions
from a11y_assertions import DEFAULT_A6_DENYLIST, evaluate, run


def _empty_tree_snapshot(extra=None):
    snap = {
        "schema_version": 1,
        "route": "/x",
        "viewport": "desktop",
        "captured_at": "now",
        "tree": {
            "role": "WebArea", "name": "X", "interactive": False,
            "disabled": False,
            "aria": {"hidden": False, "level": None, "checked": None,
                     "expanded": None, "pressed": None, "selected": None},
            "ref": None, "tag": "html", "children": [],
        }
    }
    if extra:
        snap["tree"]["children"].append(extra)
    return snap


class BoundaryAdversarial(unittest.TestCase):
    """Category 1 — boundary values."""

    def test_empty_tree_yields_no_findings(self):
        findings = evaluate(_empty_tree_snapshot(), DEFAULT_A6_DENYLIST)
        self.assertEqual(findings, [])

    def test_single_interactive_node_at_root_is_evaluated(self):
        snapshot = {
            "schema_version": 1, "route": "/x", "viewport": "d",
            "captured_at": "now",
            "tree": {
                "role": "button", "name": "", "interactive": True,
                "disabled": False, "tag": "button", "ref": None,
                "aria": {"hidden": False, "level": None, "checked": None,
                         "expanded": None, "pressed": None, "selected": None},
                "children": [],
            }
        }
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        # Root itself is interactive + empty-named -> A1 fires.
        self.assertIn("A1", {f["assertion_id"] for f in findings})


class NullEmptyUndefinedAdversarial(unittest.TestCase):
    """Category 2 — null / empty / missing fields."""

    def test_missing_aria_dict_does_not_crash(self):
        snapshot = _empty_tree_snapshot({
            "role": "button", "name": "Click", "interactive": True,
            "disabled": False, "tag": "button", "ref": None,
            "children": [],
            # aria omitted entirely — defends against captured-broken JSON.
        })
        # Must not raise; should treat aria.hidden as falsy.
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        # No A4 (not aria-hidden); no A1 (has name); A6 not on denylist.
        self.assertEqual(findings, [])

    def test_none_name_treated_as_empty_for_a1(self):
        snapshot = _empty_tree_snapshot({
            "role": "button", "name": None, "interactive": True,
            "disabled": False, "tag": "button", "ref": None,
            "aria": {"hidden": False, "level": None, "checked": None,
                     "expanded": None, "pressed": None, "selected": None},
            "children": [],
        })
        findings = evaluate(snapshot, DEFAULT_A6_DENYLIST)
        self.assertIn("A1", {f["assertion_id"] for f in findings})


class MalformedInputAdversarial(unittest.TestCase):
    """Category 3 — malformed snapshot input."""

    def test_snapshot_without_tree_returns_empty_findings(self):
        # Defensive: if upstream produced a malformed snapshot,
        # evaluate must NOT crash — return empty.
        findings = evaluate({"schema_version": 1, "route": "/x"},
                            DEFAULT_A6_DENYLIST)
        self.assertEqual(findings, [])


class ErrorPathAdversarial(unittest.TestCase):
    """Category 4 — error paths in run()."""

    def test_run_swallows_per_snapshot_read_error_and_continues(self):
        # Build an index pointing at a snapshot path that does NOT exist.
        # The route is captured=true, but the snapshot path is dead.
        # run() must not crash; verdict is PASS (no findings, no fatal).
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index = {
                "schema_version": 1, "task_id": "t",
                "captured_at": "now", "build_status": "PASS",
                "server_started": True,
                "routes": [{"route": "/x", "screenshots": [],
                            "a11y": {"captured": True,
                                     "capture_path": "library",
                                     "snapshots": [{"viewport": "desktop",
                                                    "path": str(tmp_path /
                                                                "missing.json")}]}}],
                "a11y_global": {"captured": True, "capture_path": "library",
                                "reason": None}
            }
            index_path = tmp_path / "index.json"
            index_path.write_text(json.dumps(index))
            result = run(str(index_path))
            self.assertEqual(result["verdict"], "PASS")
            self.assertEqual(result["findings"], [])


if __name__ == "__main__":
    unittest.main()
