"""Tests for github-cache-server-lib (M1: XDG default cache root)."""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
LIB_PATH = REPO / "hooks" / "_lib" / "github-cache-server-lib.py"


def _load():
    spec = importlib.util.spec_from_file_location("gh_cache_lib", LIB_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gh_cache_lib"] = module
    spec.loader.exec_module(module)
    return module


class TestDefaultCacheRootXdg(unittest.TestCase):
    """M1: default cache root respects XDG_CACHE_HOME, never /tmp."""

    def test_uses_xdg_cache_home_when_set(self):
        env = {"XDG_CACHE_HOME": "/explicit/xdg"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("CLAUDE_GH_CACHE_DIR", None)
            path = _load().cache_dir_for("s", 1)
        self.assertEqual(path, "/explicit/xdg/claude/gh-pr/s-1")

    def test_falls_back_to_home_dot_cache(self):
        with mock.patch.dict(os.environ, {"HOME": "/tmp/h"}, clear=False):
            os.environ.pop("CLAUDE_GH_CACHE_DIR", None)
            os.environ.pop("XDG_CACHE_HOME", None)
            path = _load().cache_dir_for("s", 2)
        self.assertEqual(path, "/tmp/h/.cache/claude/gh-pr/s-2")

    def test_never_returns_tmp_default(self):
        os.environ.pop("CLAUDE_GH_CACHE_DIR", None)
        path = _load().cache_dir_for("s", 3)
        self.assertNotIn("/tmp/gh-pr-cache", path)


if __name__ == "__main__":
    unittest.main()
