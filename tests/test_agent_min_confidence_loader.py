"""Unit tests for hooks/_lib/agent_min_confidence_loader.py (slice-b AC4/AC4b).

Mirrors the silent-None behaviour of agent_instinct_categories_loader: returns
float on valid in-range value; returns None silently for absent / non-numeric /
out-of-range / missing-file. Never raises. Never writes to stderr.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from agent_min_confidence_loader import load_min_confidence  # noqa: E402


def _write_agent(tmp, body):
    (Path(tmp) / "test-role.md").write_text(f"---\n{body}---\nbody")


class LoaderReturnsFloat(unittest.TestCase):
    def test_returns_float_when_frontmatter_sets_min_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_agent(tmp, "name: test-role\nmin_confidence: 0.5\n")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                result = load_min_confidence("test-role")
            self.assertIsInstance(result, float)
            self.assertEqual(result, 0.5)

    def test_zero_boundary_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_agent(tmp, "min_confidence: 0.0\n")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                self.assertEqual(load_min_confidence("test-role"), 0.0)

    def test_one_boundary_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_agent(tmp, "min_confidence: 1.0\n")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                self.assertEqual(load_min_confidence("test-role"), 1.0)


class LoaderReturnsNoneSilently(unittest.TestCase):
    def _load_capturing_stderr(self, body):
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            _write_agent(tmp, body)
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}), \
                 redirect_stderr(buf):
                result = load_min_confidence("test-role")
        return result, buf.getvalue()

    def test_returns_none_when_field_absent(self):
        result, err = self._load_capturing_stderr("name: test-role\n")
        self.assertIsNone(result)
        self.assertEqual(err, "")

    def test_returns_none_silently_on_non_numeric_or_out_of_range(self):
        for body in ("min_confidence: high\n",
                     "min_confidence: 1.5\n",
                     "min_confidence: -0.1\n"):
            with self.subTest(body=body):
                result, err = self._load_capturing_stderr(body)
                self.assertIsNone(result)
                self.assertEqual(err, "")


class LoaderHandlesMissingAgentFile(unittest.TestCase):
    def test_returns_none_when_agent_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                self.assertIsNone(load_min_confidence("nonexistent-agent"))


if __name__ == "__main__":
    unittest.main()
