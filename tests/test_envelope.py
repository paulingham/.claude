"""CLI envelope + missing-db guard helpers."""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import envelope  # noqa: E402


class Envelope(unittest.TestCase):
    def test_exact_limit_is_not_truncated(self):
        env = envelope.envelope("search", [1, 2, 3], limit=3)
        self.assertFalse(env["truncated"])
        self.assertEqual(env["total"], 3)

    def test_truncated_when_fetched_exceeds_limit(self):
        env = envelope.envelope("search", [1, 2, 3], limit=3, fetched=4)
        self.assertTrue(env["truncated"])
        self.assertEqual(env["total"], 3)

    def test_envelope_not_truncated_below_limit(self):
        env = envelope.envelope("search", [1], limit=20)
        self.assertFalse(env["truncated"])


class MissingDbGuard(unittest.TestCase):
    def test_warns_once_on_missing(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            missing = envelope.db_missing(Path("/no/such.sqlite"))
        self.assertTrue(missing)
        self.assertIn("run reindex-memory", buf.getvalue())

    def test_present_db_is_not_missing(self):
        with tempfile.NamedTemporaryFile() as tmp:
            self.assertFalse(envelope.db_missing(tmp.name))

    def test_stderr_escapes_control_bytes(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            envelope.db_missing("/tmp/\x1b[2Jhacked.sqlite")
        out = buf.getvalue()
        self.assertNotIn("\x1b", out)
        self.assertIn("\\x1b", out)


if __name__ == "__main__":
    unittest.main()
