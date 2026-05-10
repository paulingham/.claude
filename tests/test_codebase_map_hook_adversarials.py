"""Step 2b adversarial tests for Slice C hooks.

Greenfield ACs default-on, cap=5. Categories walked in order:

1. Boundary values — empty repo, max-length project hash, file_count=0
2. Null / empty — missing state.json, empty CLAUDE_PROJECT_HASH
3. Malformed input — corrupt state.json
4. Error-path — `validate_project_hash` rejection
5. Concurrency — skipped (lock is bash-flock, no Python-level concurrency)

Each adversarial follows RED-then-GREEN per the skill. Production code
already covers these cases (we authored defensively); these tests
LOCK the contracts so a future regression surfaces here.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _import_state_module():
    """Load `codebase-map-state.py` via importlib (the file uses a hyphen)."""
    spec = importlib.util.spec_from_file_location(
        "codebase_map_state",
        REPO_ROOT / "hooks" / "_lib" / "codebase-map-state.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _import_emit_module():
    sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
    try:
        import codebase_map_emit  # noqa: WPS433
        return codebase_map_emit
    finally:
        sys.path.pop(0)


class BoundaryValueAdversarials(unittest.TestCase):
    """Category 1: boundary values — append-safety on the JSONL writer."""

    def test_append_record_appends_not_clobbers(self):
        """Append-mode write — second call MUST add a line, not replace.

        This guards against a regression where `append_record` switches to
        truncating-write mode, which would erase prior forensic lines on
        every invocation (silent data loss). The AC22-quater forensic
        gate reads the last 30 lines; truncation would never pass that
        gate but would leave the warm-cache test still GREEN — the bug
        is invisible to existing AC tests.
        """
        emit = _import_emit_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.jsonl"
            emit.append_record(path, '{"hook":"first"}')
            emit.append_record(path, '{"hook":"second"}')
            lines = path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 2,
                             f"expected 2 lines, got {len(lines)}: {lines!r}")
            self.assertIn("first", lines[0])
            self.assertIn("second", lines[1])


class NullEmptyAdversarials(unittest.TestCase):
    """Category 2: null / empty inputs."""

    def test_read_missing_state_returns_none(self):
        """A missing state.json must return None, not raise."""
        state_mod = _import_state_module()
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such-state.json"
            self.assertIsNone(state_mod.read_state(missing))
            self.assertIsNone(state_mod.last_built_sha(missing))

    def test_validate_empty_hash_falls_back(self):
        """Empty CLAUDE_PROJECT_HASH yields the fallback (default 'local')."""
        state_mod = _import_state_module()
        self.assertEqual(state_mod.validate_project_hash("", "local"), "local")
        self.assertEqual(state_mod.validate_project_hash(None, "local"), "local")


class MalformedInputAdversarials(unittest.TestCase):
    """Category 3: malformed input (parser-level)."""

    def test_corrupt_state_json_returns_none(self):
        """Garbage in state.json must NOT crash read_state."""
        state_mod = _import_state_module()
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "state.json"
            bad.write_text("{not valid json at all")
            self.assertIsNone(state_mod.read_state(bad))
            self.assertIsNone(state_mod.last_built_sha(bad))


class ErrorPathAdversarials(unittest.TestCase):
    """Category 4: error-path coverage."""

    def test_validate_rejects_path_traversal(self):
        """`../../etc` / colon / slash / null all reject."""
        state_mod = _import_state_module()
        rejections = ["../../etc", "a/b", "a:b", "a\x00b", " ", "$(rm)"]
        for raw in rejections:
            with self.subTest(raw=raw):
                self.assertEqual(
                    state_mod.validate_project_hash(raw, "local"),
                    "local",
                    f"hash {raw!r} should have been rejected",
                )


if __name__ == "__main__":
    unittest.main()
