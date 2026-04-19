"""Direct tests for _lib.jsonl stream parser."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,
                str(Path(__file__).resolve().parents[1] /
                    "skills" / "reindex-memory"))

from _lib import jsonl  # noqa: E402


class ParsesCompactAndPrettyObjects(unittest.TestCase):
    def test_yields_each_object(self):
        raw = '{"a":1}\n{\n  "b": 2\n}\n'
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "f.jsonl"
            p.write_text(raw)
            objs = list(jsonl.parse_file(p))
        self.assertEqual(objs, [{"a": 1}, {"b": 2}])


class SkipsMalformedSpans(unittest.TestCase):
    def test_bad_line_skipped_good_yielded(self):
        raw = '{"a":1}\nnot-json\n{"b":2}\n'
        errors = []
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "f.jsonl"
            p.write_text(raw)
            objs = list(jsonl.parse_file(
                p, on_error=lambda *a: errors.append(a)))
        self.assertEqual(objs, [{"a": 1}, {"b": 2}])
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
