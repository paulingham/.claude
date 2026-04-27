"""Tests for the cache filesystem writer (atomic rename + perms)."""
import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
STORE_PATH = REPO / "hooks" / "_lib" / "github-cache-server-store.py"


def _load():
    spec = importlib.util.spec_from_file_location("gh_cache_store", STORE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gh_cache_store"] = module
    spec.loader.exec_module(module)
    return module


class TestAtomicRename(unittest.TestCase):
    def test_uses_os_replace_for_atomic_rename(self):
        """M3: writer must use os.replace for atomic file publication."""
        store = _load()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "x"
            with mock.patch.object(os, "replace", wraps=os.replace) as repl:
                store.write_cache(str(target), "v", "d", "f")
            self.assertGreaterEqual(repl.call_count, 3,
                                    "expected ≥3 os.replace calls (view, diff, files)")

    def test_complete_exists_alongside_finals(self):
        store = _load()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "x"
            store.write_cache(str(target), "v", "d", "f")
            for name in ("view.json", "diff.patch", "files.txt", ".complete"):
                self.assertTrue((target / name).exists(), f"missing {name}")


class TestPermsHardening(unittest.TestCase):
    """M1: cache dir 0o700, files 0o600."""

    def test_dir_mode_is_0700(self):
        store = _load()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "secrets"
            store.write_cache(str(target), "v", "d", "f")
            mode = stat.S_IMODE(target.stat().st_mode)
            self.assertEqual(mode, 0o700, f"got {oct(mode)}")

    def test_file_mode_is_0600(self):
        store = _load()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "secrets"
            store.write_cache(str(target), "v", "d", "f")
            for name in ("view.json", "diff.patch", "files.txt"):
                mode = stat.S_IMODE((target / name).stat().st_mode)
                self.assertEqual(mode, 0o600, f"{name}: got {oct(mode)}")


if __name__ == "__main__":
    unittest.main()
