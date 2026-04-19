"""Env-var resolution for ORT_DYLIB_PATH / BGE_MODEL_PATH."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib import paths  # noqa: E402


class DylibResolution(unittest.TestCase):
    def test_unset_env_raises_unavailable(self):
        with _clean_env("ORT_DYLIB_PATH"):
            with self.assertRaises(paths.EmbedderUnavailable):
                paths.resolve_dylib()

    def test_missing_file_raises_unavailable(self):
        with _env("ORT_DYLIB_PATH", "/tmp/does-not-exist.dylib"):
            with self.assertRaises(paths.EmbedderUnavailable):
                paths.resolve_dylib()

    def test_existing_file_returns_resolved_path(self):
        with tempfile.NamedTemporaryFile(suffix=".dylib") as fh:
            with _env("ORT_DYLIB_PATH", fh.name):
                self.assertEqual(paths.resolve_dylib(), Path(fh.name))


class ModelResolution(unittest.TestCase):
    def test_unset_falls_back_to_default(self):
        with _clean_env("BGE_MODEL_PATH"):
            with self.assertRaises(paths.EmbedderUnavailable):
                paths.resolve_model()

    def test_set_returns_path(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as fh:
            with _env("BGE_MODEL_PATH", fh.name):
                self.assertEqual(paths.resolve_model(), Path(fh.name))


class _env:
    def __init__(self, key, val):
        self.key, self.val = key, val
        self.prev = None

    def __enter__(self):
        self.prev = os.environ.get(self.key)
        os.environ[self.key] = self.val

    def __exit__(self, *_):
        if self.prev is None:
            os.environ.pop(self.key, None)
        else:
            os.environ[self.key] = self.prev


class _clean_env(_env):
    def __init__(self, key):
        super().__init__(key, "")

    def __enter__(self):
        self.prev = os.environ.pop(self.key, None)


if __name__ == "__main__":
    unittest.main()
