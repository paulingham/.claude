"""Slice 16: embedder CLI — doctor/status/setup subcommands."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))


class DoctorReportsFakeHealthy(unittest.TestCase):
    def test_doctor_prints_ok_when_fake_backend(self):
        os.environ["CLAUDE_EMBEDDER"] = "fake"
        try:
            from embedder import cli
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["doctor"])
            self.assertEqual(rc, 0)
            self.assertIn("ok", buf.getvalue().lower())
        finally:
            os.environ.pop("CLAUDE_EMBEDDER", None)


class StatusCommandWritesJSON(unittest.TestCase):
    def test_status_writes_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s.json"
            os.environ["CLAUDE_EMBEDDER_STATUS"] = str(out)
            os.environ["CLAUDE_EMBEDDER"] = "fake"
            try:
                from embedder import cli
                cli.main(["status"])
                self.assertTrue(out.exists())
                payload = json.loads(out.read_text())
                self.assertIn("ok", payload)
            finally:
                os.environ.pop("CLAUDE_EMBEDDER_STATUS", None)
                os.environ.pop("CLAUDE_EMBEDDER", None)


class SetupCommandPrintsInstructions(unittest.TestCase):
    def test_setup_mentions_ort_dylib_path(self):
        from embedder import cli
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["setup"])
        self.assertIn("ORT_DYLIB_PATH", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
