"""BC1: doctor CLI 6-field diagnostic + verdict."""
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "reindex-memory"))


REQUIRED_KEYS = ("ORT_DYLIB_PATH", "BGE_MODEL_PATH", "last_error",
                 "last_error_at", "last_success_at", "unembedded_count",
                 "verdict")


class DoctorEmitsAllSixFields(unittest.TestCase):
    def test_all_keys_plus_verdict_present(self):
        with _ctx():
            output = _run_doctor()
            for key in REQUIRED_KEYS:
                self.assertIn(key, output,
                              f"missing key {key} in doctor output")


class DoctorVerdictOkWhenFakeAndNoUnembedded(unittest.TestCase):
    def test_verdict_ok_with_fake_and_success(self):
        with _ctx(backend="fake", db=_make_empty_db, mark_success=True):
            output = _run_doctor()
            self.assertIn("verdict: OK", output)


class DoctorVerdictUnavailableWhenFacadeRaises(unittest.TestCase):
    def test_verdict_unavailable_when_facade_raises(self):
        with _ctx():  # no CLAUDE_EMBEDDER set → real backend → raises
            output = _run_doctor()
            self.assertIn("verdict: UNAVAILABLE", output)


class DoctorVerdictStaleWhenBackendHealthyButUnembedded(unittest.TestCase):
    def test_verdict_stale_with_unembedded_rows(self):
        with _ctx(backend="fake", db=_make_db_with_unembedded,
                  mark_success=True):
            output = _run_doctor()
            self.assertIn("verdict: STALE", output)
            self.assertIn("2 unembedded", output)


class DoctorShowsUnsetForMissingEnv(unittest.TestCase):
    def test_unset_env_displays_placeholder(self):
        with _ctx():
            output = _run_doctor()
            self.assertIn("ORT_DYLIB_PATH: <unset>", output)


class DoctorHandlesMissingDb(unittest.TestCase):
    def test_unembedded_zero_when_db_missing(self):
        with _ctx(backend="fake", mark_success=True):
            output = _run_doctor()
            self.assertIn("unembedded_count: 0", output)


def _run_doctor():
    from embedder import cli
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main(["doctor"])
    return buf.getvalue()


def _make_empty_db(path):
    from _lib import schema
    schema.ensure(path)


def _make_db_with_unembedded(path):
    from _lib import schema
    schema.ensure(path)
    con = sqlite3.connect(str(path))
    for i in range(2):
        hash_ = f"{i}".zfill(64)
        con.execute(
            "INSERT INTO observations (content_hash, session_id, "
            "timestamp, tool, file) VALUES (?, ?, ?, ?, ?)",
            (hash_, "s", f"t{i}", "Read", "/a"))
    con.commit()
    con.close()


class _ctx:
    def __init__(self, backend=None, db=None, mark_success=False):
        self.backend = backend
        self.db_fn = db
        self.mark_success = mark_success

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.status = Path(self.tmp.name) / "status.json"
        os.environ["CLAUDE_EMBEDDER_STATUS"] = str(self.status)
        for k in ("ORT_DYLIB_PATH", "BGE_MODEL_PATH", "CLAUDE_EMBEDDER"):
            os.environ.pop(k, None)
        if self.backend:
            os.environ["CLAUDE_EMBEDDER"] = self.backend
        db = Path(self.tmp.name) / "memory.sqlite"
        os.environ["CLAUDE_DB_PATH"] = str(db)
        if self.db_fn:
            self.db_fn(db)
        if self.mark_success:
            from embedder import status
            status.record_success("2026-04-19T00:00:00Z")
        _reset_embedder()
        return self

    def __exit__(self, *a):
        for k in ("CLAUDE_EMBEDDER_STATUS", "CLAUDE_EMBEDDER",
                  "CLAUDE_DB_PATH", "ORT_DYLIB_PATH", "BGE_MODEL_PATH"):
            os.environ.pop(k, None)
        _reset_embedder()
        self.tmp.cleanup()


def _reset_embedder():
    mod = sys.modules.get("embedder.embedder")
    if mod is not None:
        mod.reset_singleton_for_tests()


if __name__ == "__main__":
    unittest.main()
