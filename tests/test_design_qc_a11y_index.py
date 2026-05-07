"""AC1 + AC2 — index.json + per-snapshot files exist with required keys.

Slice 1 capture path is a Node-driven script. These tests stub the capture
result by directly invoking the index-builder helper exposed by the
JS-Python boundary contract: a Python helper (`a11y_index_helper`) writes
the index given a list of route entries — the same data the Node capture
path would hand off via the JSON-on-disk seam.
"""
import json
import tempfile
import unittest
from pathlib import Path

import a11y_index_helper
from a11y_index_helper import (
    INDEX_SCHEMA_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    write_index,
)


class IndexJsonTopLevelKeys(unittest.TestCase):
    """AC1 — index.json contains required top-level keys."""

    def test_index_json_written_with_required_top_level_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index_path = tmp_path / "index.json"
            write_index(
                index_path,
                task_id="wave2a-b4-a11y-tree",
                captured_at="2026-05-07T11:30:00Z",
                build_status="PASS",
                server_started=True,
                routes=[],
                a11y_global={"captured": False, "reason": "no-routes",
                             "capture_path": None},
            )
            self.assertTrue(index_path.exists())
            payload = json.loads(index_path.read_text())
            for key in ("schema_version", "task_id", "captured_at",
                        "build_status", "server_started", "routes",
                        "a11y_global"):
                self.assertIn(key, payload)
            self.assertEqual(payload["schema_version"], INDEX_SCHEMA_VERSION)


class PerRouteSnapshotsParse(unittest.TestCase):
    """AC2 — per-route a11y snapshots resolve to JSON with required keys."""

    def test_per_route_a11y_snapshot_files_exist_and_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a11y_dir = tmp_path / "a11y"
            a11y_dir.mkdir()
            snap_path = a11y_dir / "dashboard-desktop.json"
            snapshot = {
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "route": "/dashboard",
                "viewport": "desktop",
                "captured_at": "2026-05-07T11:30:00Z",
                "tree": {
                    "role": "WebArea", "name": "Dashboard",
                    "interactive": False, "disabled": False,
                    "aria": {"hidden": False, "level": None,
                             "checked": None, "expanded": None,
                             "pressed": None, "selected": None},
                    "ref": None, "tag": "html", "children": []
                }
            }
            snap_path.write_text(json.dumps(snapshot))

            index_path = tmp_path / "index.json"
            write_index(
                index_path,
                task_id="t",
                captured_at="2026-05-07T11:30:00Z",
                build_status="PASS",
                server_started=True,
                routes=[
                    {
                        "route": "/dashboard",
                        "screenshots": [],
                        "a11y": {
                            "captured": True,
                            "capture_path": "library",
                            "snapshots": [
                                {"viewport": "desktop",
                                 "path": str(snap_path)}
                            ]
                        }
                    }
                ],
                a11y_global={"captured": True, "capture_path": "library",
                             "reason": None},
            )

            payload = json.loads(index_path.read_text())
            paths = [s["path"] for s in
                     payload["routes"][0]["a11y"]["snapshots"]]
            self.assertEqual(len(paths), 1)
            self.assertTrue(Path(paths[0]).exists())
            parsed = json.loads(Path(paths[0]).read_text())
            for key in ("schema_version", "route", "viewport", "captured_at",
                        "tree"):
                self.assertIn(key, parsed)


class IndexCarriesSchemaVersion(unittest.TestCase):
    """AC19 — index.json must carry schema_version: 1."""

    def test_index_root_carries_schema_version_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            index_path = tmp_path / "index.json"
            write_index(
                index_path, task_id="t", captured_at="now",
                build_status="PASS", server_started=True, routes=[],
                a11y_global={"captured": False, "reason": "x",
                             "capture_path": None})
            payload = json.loads(index_path.read_text())
            self.assertEqual(payload["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
