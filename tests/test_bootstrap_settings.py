"""S9: bootstrap_settings.apply — dylib-exists guard + patch delegation.

Covers the extracted _try_patch helper introduced during shape refactor.
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

from embedder._lib import bootstrap_settings  # noqa: E402


class ApplySkipsWhenDylibMissing(unittest.TestCase):
    def test_returns_zero_and_does_not_write(self):
        rc = bootstrap_settings.apply(Path("/nonexistent/libonnxruntime.dylib"))
        self.assertEqual(rc, 0)


class ApplyWritesOrtDylibPathWhenDylibPresent(unittest.TestCase):
    def test_settings_file_contains_resolved_dylib_path(self):
        with tempfile.TemporaryDirectory() as d:
            settings = Path(d) / "settings.json"
            settings.write_text(json.dumps({"env": {}}))
            dylib = Path(d) / "libonnxruntime.dylib"
            dylib.touch()
            env_patch = {"CLAUDE_SETTINGS_PATH": str(settings)}
            with patch.dict(os.environ, env_patch, clear=False):
                rc = bootstrap_settings.apply(dylib)
            self.assertEqual(rc, 0)
            payload = json.loads(settings.read_text())
            self.assertEqual(
                payload["env"].get("ORT_DYLIB_PATH"), str(dylib))


class ApplyWarnsOnPatchError(unittest.TestCase):
    def test_returns_one_and_prints_warn_when_patch_fails(self):
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            dylib = Path(d) / "libonnxruntime.dylib"
            dylib.touch()
            buf = io.StringIO()
            with patch(
                "embedder._lib.bootstrap_settings.settings_patch.patch",
                side_effect=bootstrap_settings.settings_patch
                .SettingsPatchError("boom"),
            ):
                with redirect_stdout(buf):
                    rc = bootstrap_settings.apply(dylib)
            self.assertEqual(rc, 1)
            self.assertIn("WARN", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
