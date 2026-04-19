"""AC5, AC7: allowlist loader — default file, user override, cold path."""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))

from capture._lib import allowlist_loader  # noqa: E402


class DefaultFileLoads(unittest.TestCase):
    def test_returns_allowlist_from_default_when_user_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            default = Path(tmp) / "default.json"
            default.write_text(json.dumps({
                "version": 1,
                "file_globs": ["*.env"],
                "content_regexes": [r"AKIA[0-9A-Z]{16}\b"],
            }))
            allow = allowlist_loader.load(
                user_path=Path(tmp) / "missing.json",
                default_path=default)
            self.assertEqual(allow.file_globs, ("*.env",))
            self.assertEqual(len(allow.content_regexes), 1)


class UserFileOverridesDefault(unittest.TestCase):
    def test_user_file_wins_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            default = Path(tmp) / "default.json"
            user = Path(tmp) / "user.json"
            default.write_text(json.dumps(
                {"file_globs": ["*.default"], "content_regexes": []}))
            user.write_text(json.dumps(
                {"file_globs": ["*.user"], "content_regexes": []}))
            allow = allowlist_loader.load(
                user_path=user, default_path=default)
            self.assertEqual(allow.file_globs, ("*.user",))


class BothAbsentReturnsEmpty(unittest.TestCase):
    """AC7: no file = no allowlist, identical to pre-S6 behaviour."""
    def test_neither_file_present_empty_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            allow = allowlist_loader.load(
                user_path=Path(tmp) / "u.json",
                default_path=Path(tmp) / "d.json")
            self.assertEqual(allow.file_globs, ())
            self.assertEqual(allow.content_regexes, ())


class MalformedJsonWarnsAndReturnsEmpty(unittest.TestCase):
    def test_invalid_json_returns_empty_and_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            user = Path(tmp) / "user.json"
            user.write_text("{ this is not json }")
            buf = io.StringIO()
            with redirect_stderr(buf):
                allow = allowlist_loader.load(
                    user_path=user, default_path=None)
            self.assertEqual(allow.file_globs, ())
            self.assertIn("allowlist", buf.getvalue().lower())


class MtimeCacheAvoidsReparse(unittest.TestCase):
    """Repeated load() with unchanged mtime does not re-read the file."""
    def test_cached_allowlist_is_same_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            user = Path(tmp) / "u.json"
            user.write_text(json.dumps(
                {"file_globs": ["a"], "content_regexes": []}))
            first = allowlist_loader.load(user_path=user, default_path=None)
            second = allowlist_loader.load(user_path=user, default_path=None)
            self.assertIs(first, second)


class MtimeChangeTriggersReparse(unittest.TestCase):
    """When the file's mtime advances, the cache re-parses."""
    def test_mtime_bump_returns_fresh_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            user = Path(tmp) / "u.json"
            user.write_text(json.dumps(
                {"file_globs": ["old"], "content_regexes": []}))
            first = allowlist_loader.load(user_path=user, default_path=None)
            user.write_text(json.dumps(
                {"file_globs": ["new"], "content_regexes": []}))
            os.utime(user, (time.time() + 5, time.time() + 5))
            second = allowlist_loader.load(user_path=user, default_path=None)
            self.assertEqual(first.file_globs, ("old",))
            self.assertEqual(second.file_globs, ("new",))


class ShippedDefaultContainsMandatoryPatterns(unittest.TestCase):
    """AC5: default file ships at skills/capture/privacy-allowlist.default.json
    and contains .env*, *secret*, *credential*, *.pem, *.key, AKIA, JWT."""
    def test_default_file_exists_with_required_patterns(self):
        default = (Path(__file__).resolve().parents[1] / "skills"
                   / "capture" / "privacy-allowlist.default.json")
        self.assertTrue(default.exists(), default)
        data = json.loads(default.read_text())
        globs = set(data["file_globs"])
        regexes = data["content_regexes"]
        for required in (".env", ".env.*", "*secret*", "*credential*",
                         "*.pem", "*.key"):
            self.assertIn(required, globs)
        self.assertTrue(
            any("AKIA[0-9A-Z]{16}" in r for r in regexes), regexes)
        self.assertTrue(
            any(r.startswith("eyJ") for r in regexes), regexes)


if __name__ == "__main__":
    unittest.main()
