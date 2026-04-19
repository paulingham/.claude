"""AC1, AC2a, AC2b: privacy.apply facade — combines sanitize + allowlist check."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))

from capture._lib import privacy  # noqa: E402


class _AllowlistTmp:
    """Context manager that redirects privacy allowlist to a temp file."""
    def __init__(self, data):
        self._data = data

    def __enter__(self):
        self._dir = tempfile.TemporaryDirectory()
        path = Path(self._dir.name) / "user.json"
        path.write_text(json.dumps(self._data))
        self._prev = privacy._user_path, privacy._default_path
        privacy._user_path, privacy._default_path = path, None
        return self

    def __exit__(self, *a):
        privacy._user_path, privacy._default_path = self._prev
        self._dir.cleanup()


class SanitizesPrivateTagsInAllFields(unittest.TestCase):
    """AC1: <private>...</private> stripped from command/searchable_text/body."""
    def test_private_blocks_stripped_from_all_text_fields(self):
        obj = {
            "command": "echo <private>secret</private> hi",
            "searchable_text": "log <private>token</private> end",
            "body": "note <private>x</private>",
            "file": "app.ts",
        }
        with _AllowlistTmp({"file_globs": [], "content_regexes": []}):
            out = privacy.apply(obj)
        self.assertNotIn("secret", out["command"])
        self.assertNotIn("<private>", out["command"])
        self.assertNotIn("token", out["searchable_text"])
        self.assertNotIn("x", out["body"])


class AllowlistedFileSetsIsPrivateFlag(unittest.TestCase):
    """AC2a: .env file in allowlist → is_private=1."""
    def test_env_file_flagged_private(self):
        obj = {"file": ".env", "command": "cat .env"}
        with _AllowlistTmp({"file_globs": [".env"], "content_regexes": []}):
            out = privacy.apply(obj)
        self.assertEqual(out["is_private"], 1)


class NonAllowlistedFileNotFlagged(unittest.TestCase):
    def test_ordinary_file_is_private_zero(self):
        obj = {"file": "src/app.tsx", "command": "cat src/app.tsx"}
        with _AllowlistTmp({"file_globs": [".env"], "content_regexes": []}):
            out = privacy.apply(obj)
        self.assertEqual(out["is_private"], 0)


class ContentRegexMatchFlagsPrivate(unittest.TestCase):
    """AC4 via facade: AWS key in command triggers is_private=1."""
    def test_aws_key_in_command_flags(self):
        obj = {"command": "KEY=AKIAIOSFODNN7EXAMPLE", "file": "notes.md"}
        with _AllowlistTmp({"file_globs": [],
                            "content_regexes": [r"AKIA[0-9A-Z]{16}\b"]}):
            out = privacy.apply(obj)
        self.assertEqual(out["is_private"], 1)


class SanitizationAndAllowlistCompose(unittest.TestCase):
    """Both <private> stripping AND allowlist flagging happen in one pass."""
    def test_env_file_with_private_tag_stripped_and_flagged(self):
        obj = {"file": ".env",
               "command": "echo <private>secret</private>"}
        with _AllowlistTmp({"file_globs": [".env"], "content_regexes": []}):
            out = privacy.apply(obj)
        self.assertEqual(out["is_private"], 1)
        self.assertNotIn("secret", out["command"])


class ReturnsObjectMissingFields(unittest.TestCase):
    """apply() tolerates missing fields without raising."""
    def test_empty_obj_returns_empty_with_is_private_zero(self):
        with _AllowlistTmp({"file_globs": [], "content_regexes": []}):
            out = privacy.apply({})
        self.assertEqual(out["is_private"], 0)


class OriginalObjectNotMutated(unittest.TestCase):
    """apply() returns a new dict; caller's obj is untouched."""
    def test_input_object_unchanged(self):
        obj = {"command": "echo <private>x</private>", "file": "a.py"}
        with _AllowlistTmp({"file_globs": [], "content_regexes": []}):
            privacy.apply(obj)
        self.assertIn("<private>", obj["command"])


if __name__ == "__main__":
    unittest.main()
