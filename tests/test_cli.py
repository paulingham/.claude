"""CLI envelope + argparse wrapper for /recall."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import cli  # noqa: E402


class CliSearchEnvelope(unittest.TestCase):
    def test_search_emits_json_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main(["search", "Read", "--source", "observations",
                          "--db", str(db)])
            env = json.loads(buf.getvalue())
            self.assertEqual(env["tier"], "search")
            self.assertIn("hits", env)

    def test_rejects_include_private_flag(self):
        with self.assertRaises(SystemExit):
            cli.main(["search", "x", "--include-private"])


if __name__ == "__main__":
    unittest.main()
