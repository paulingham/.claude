"""Non-gating unit tests for hooks/_lib/preamble-tokens-emit.py helper.

Tests helper arithmetic: known byte sizes → sum(ceil(bytes/3.5)),
missing files → 0, nonexistent root → 0.
"""
import importlib.util
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / "hooks" / "_lib" / "preamble-tokens-emit.py"


def _load_helper():
    """Load the helper module dynamically from its path."""
    spec = importlib.util.spec_from_file_location("preamble_tokens_emit", HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PreambleTokensEmitArithmetic(unittest.TestCase):
    """Tests for the per-file ceil(bytes/3.5) summation."""

    def setUp(self):
        self.mod = _load_helper()

    def test_single_file_ceil_arithmetic(self):
        """ceil(7 bytes / 3.5) = 2 tokens."""
        result = self.mod._tokens_for_bytes(7)
        self.assertEqual(result, 2)

    def test_single_file_non_integer_division(self):
        """ceil(8 bytes / 3.5) = ceil(2.285...) = 3 tokens."""
        result = self.mod._tokens_for_bytes(8)
        self.assertEqual(result, 3)

    def test_zero_bytes_returns_zero(self):
        self.assertEqual(self.mod._tokens_for_bytes(0), 0)

    def test_sum_across_multiple_files(self):
        """Sum of per-file ceil(bytes/3.5) for known sizes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CLAUDE.md").write_bytes(b"a" * 100)
            rules_dir = root / "rules"
            rules_dir.mkdir()
            (rules_dir / "core.md").write_bytes(b"b" * 200)
            instincts_dir = root / "learning" / "instincts"
            instincts_dir.mkdir(parents=True)
            (instincts_dir / "instinct1.md").write_bytes(b"c" * 350)

            expected = (
                math.ceil(100 / 3.5)
                + math.ceil(200 / 3.5)
                + math.ceil(350 / 3.5)
            )
            result = self.mod._sum_preamble_tokens(root)
            self.assertEqual(result, expected)

    def test_missing_file_contributes_zero(self):
        """A missing file does not raise; contributes 0 to the sum."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # No CLAUDE.md, no rules/core.md, no instincts
            result = self.mod._sum_preamble_tokens(root)
            self.assertEqual(result, 0)

    def test_nonexistent_root_returns_zero(self):
        """A completely nonexistent root → 0 (top-level fail-open)."""
        root = Path("/tmp/does_not_exist_xyzzy_preamble_test")
        result = self.mod._sum_preamble_tokens(root)
        self.assertEqual(result, 0)

    def test_unreadable_file_contributes_zero(self):
        """An unreadable file (OSError) contributes 0 to the sum."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude_md = root / "CLAUDE.md"
            claude_md.write_bytes(b"x" * 70)
            os.chmod(str(claude_md), 0o000)
            try:
                result = self.mod._sum_preamble_tokens(root)
                self.assertEqual(result, 0)
            finally:
                os.chmod(str(claude_md), 0o644)

    def test_instinct_glob_includes_multiple_files(self):
        """Multiple instinct files are all included in the sum."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instincts_dir = root / "learning" / "instincts"
            instincts_dir.mkdir(parents=True)
            sizes = [100, 200, 300]
            for i, size in enumerate(sizes):
                (instincts_dir / f"instinct{i}.md").write_bytes(b"x" * size)
            expected = sum(math.ceil(s / 3.5) for s in sizes)
            result = self.mod._sum_preamble_tokens(root)
            self.assertEqual(result, expected)

    def test_main_outputs_integer_to_stdout(self):
        """main() prints a non-negative integer (str representation)."""
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.mod.main()
        output = buf.getvalue().strip()
        self.assertRegex(output, r"^[0-9]+$")


if __name__ == "__main__":
    unittest.main()
