"""Direct unit tests for allowlist_parse — helper for allowlist_loader."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))

from capture._lib import allowlist_parse  # noqa: E402


def _build(globs, regexes):
    return {"globs": globs, "regexes": regexes}


class InvalidRegexSkippedKeepsValidOnes(unittest.TestCase):
    """One bad regex must not drop valid siblings."""
    def test_bad_regex_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            path.write_text(json.dumps({
                "file_globs": [],
                "content_regexes": ["good[0-9]+", "(bad"],
            }))
            buf = io.StringIO()
            with redirect_stderr(buf):
                out = allowlist_parse.safe_parse(path, _build)
            self.assertEqual(len(out["regexes"]), 1)
            self.assertIn("skipped invalid regex", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
