"""Tests for the sibling-module loader."""
import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOADER_PATH = REPO / "hooks" / "_lib" / "github-cache-server-loader.py"


def _load_loader():
    spec = importlib.util.spec_from_file_location("gh_cache_loader", LOADER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gh_cache_loader"] = module
    spec.loader.exec_module(module)
    return module


class TestLoadSibling(unittest.TestCase):
    def test_loads_shape_module(self):
        loader = _load_loader()
        shape = loader.load_sibling("shape")
        self.assertTrue(hasattr(shape, "reshape_view"))


if __name__ == "__main__":
    unittest.main()
