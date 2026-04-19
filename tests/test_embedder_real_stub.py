"""Real ctypes backend: stub that surfaces EmbedderUnavailable.

Full ctypes OrtApi binding is deferred — see build verdict §Slice 4 halt.
The stub ensures degraded-mode path is exercised today: the facade raises
EmbedderUnavailable, recall emits the AC11 banner, `doctor` reports it.
"""
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib import paths as paths_mod  # noqa: E402


_MANAGED = ("CLAUDE_EMBEDDER", "ORT_DYLIB_PATH", "BGE_MODEL_PATH")


class RealBuildSurfacesUnavailable(unittest.TestCase):
    def test_build_raises_embedder_unavailable(self):
        saved = {k: os.environ.get(k) for k in _MANAGED}
        try:
            self._run_unset_assertion()
        finally:
            _restore_all(saved)

    def _run_unset_assertion(self):
        for k in _MANAGED:
            os.environ.pop(k, None)
        from embedder._lib import real
        with self.assertRaises(paths_mod.EmbedderUnavailable):
            real.build()


def _restore_all(saved):
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
