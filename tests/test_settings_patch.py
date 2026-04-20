"""S9 AC6: settings_patch atomic JSON patcher.

patch(path, key, value): read JSON, set env[key] only if absent,
write atomically via mkstemp + os.replace. Invalid JSON surfaces
SettingsPatchError.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib import settings_patch  # noqa: E402


class PatchAddsMissingEnvKey(unittest.TestCase):
    def test_adds_key_when_env_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text(json.dumps({"env": {}}))
            settings_patch.patch(p, "FOO", "bar")
            self.assertEqual(json.loads(p.read_text()),
                             {"env": {"FOO": "bar"}})


class PatchPreservesExistingValueByteForByte(unittest.TestCase):
    def test_existing_value_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            original = json.dumps({"env": {"FOO": "existing"}})
            p.write_text(original)
            before = p.read_bytes()
            settings_patch.patch(p, "FOO", "new")
            self.assertEqual(p.read_bytes(), before)


class PatchCreatesEnvObjectIfMissing(unittest.TestCase):
    def test_no_env_key_creates_it(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text(json.dumps({}))
            settings_patch.patch(p, "FOO", "bar")
            self.assertEqual(json.loads(p.read_text()),
                             {"env": {"FOO": "bar"}})


class PatchUsesAtomicWrite(unittest.TestCase):
    def test_mkstemp_and_replace_are_invoked(self):
        from unittest.mock import patch as mock_patch
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text(json.dumps({"env": {}}))
            with mock_patch("embedder._lib.settings_patch.os.replace") as rep:
                with mock_patch(
                        "embedder._lib.settings_patch.tempfile.mkstemp",
                        wraps=tempfile.mkstemp) as mk:
                    settings_patch.patch(p, "FOO", "bar")
            self.assertTrue(mk.called)
            self.assertTrue(rep.called)


class PatchRaisesSettingsPatchErrorOnInvalidJson(unittest.TestCase):
    def test_malformed_json_surfaces_typed_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text("{not-json")
            with self.assertRaises(settings_patch.SettingsPatchError):
                settings_patch.patch(p, "FOO", "bar")


if __name__ == "__main__":
    unittest.main()
