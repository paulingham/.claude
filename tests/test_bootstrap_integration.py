"""S9 AC11: shared-identifier contract — bootstrap writes ORT_DYLIB_PATH
to settings.json; paths.resolve_dylib() reads the written value.

This is the end-to-end integration test for the cross-module shared
identifier. Unit tests cover each module in isolation — this one
proves the hand-off works.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib import bootstrap, paths  # noqa: E402


class BootstrapToPathsIntegration(unittest.TestCase):
    def test_written_dylib_path_is_readable_by_paths_module(self):
        from subprocess import CompletedProcess
        ok = CompletedProcess(args=[], returncode=0)
        with tempfile.TemporaryDirectory() as d:
            settings, dylib, model = _prepare(d)
            env_patch = {"CLAUDE_SETTINGS_PATH": str(settings)}
            env_patch.pop("ORT_DYLIB_PATH", None)
            _run_bootstrap(env_patch, dylib, model, ok)
            written = json.loads(settings.read_text())["env"][
                "ORT_DYLIB_PATH"]
            with patch.dict(os.environ,
                            {"ORT_DYLIB_PATH": written}, clear=False):
                resolved = paths.resolve_dylib()
            self.assertEqual(resolved, Path(written))
            self.assertEqual(resolved, dylib)


def _prepare(d):
    settings = Path(d) / "settings.json"
    settings.write_text(json.dumps({"env": {}}))
    dylib = Path(d) / "libonnxruntime.dylib"
    dylib.touch()
    model = Path(d) / "model.onnx"
    model.touch()
    return settings, dylib, model


def _run_bootstrap(env_patch, dylib, model, ok):
    with patch.dict(os.environ, env_patch, clear=False), \
         patch("embedder._lib.bootstrap.platform.system",
               return_value="Darwin"), \
         patch("embedder._lib.bootstrap._is_healthy",
               return_value=False), \
         patch("embedder._lib.bootstrap._dylib_path",
               return_value=dylib), \
         patch("embedder._lib.bootstrap._model_path",
               return_value=model), \
         patch("embedder._lib.bootstrap_steps.subprocess.run",
               return_value=ok):
        bootstrap.run()


if __name__ == "__main__":
    unittest.main()
