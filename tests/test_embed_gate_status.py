"""BC2: embed_gate writes status.record_success on success / record_failure on EmbedderUnavailable."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "skills"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "reindex-memory"))


def _obj():
    return {"session_id": "s", "timestamp": "2026-04-19T00:00:00Z",
            "tool": "Read", "file": "/a.py", "outcome": "ok",
            "project_hash": "ph", "searchable_text": "hello"}


class SuccessRecordsLastSuccessAt(unittest.TestCase):
    def test_maybe_embed_writes_success_timestamp(self):
        with _env("fake") as out:
            _run_embed()
            payload = json.loads(out.read_text())
            self.assertIn("last_success_at", payload)


class FailureRecordsLastError(unittest.TestCase):
    def test_embedder_unavailable_records_reason(self):
        with _env(None) as out:
            _run_embed()
            payload = json.loads(out.read_text())
            self.assertIn("last_error", payload)
            self.assertIn("last_error_at", payload)


def _run_embed():
    from _lib import embed_gate, schema
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "memory.sqlite"
        schema.ensure(db)
        con = sqlite3.connect(str(db))
        try:
            embed_gate.maybe_embed(con, _obj(), "h" * 64)
            con.commit()
        finally:
            con.close()


_MANAGED = ("CLAUDE_EMBEDDER_STATUS", "CLAUDE_EMBEDDER",
            "ORT_DYLIB_PATH", "BGE_MODEL_PATH")


class _env:
    def __init__(self, backend):
        self.backend = backend

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _MANAGED}
        self.tmp = tempfile.TemporaryDirectory()
        self._models = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "s.json"
        ort = Path(self._models.name) / "s.dylib"; ort.write_bytes(b"")
        bge = Path(self._models.name) / "s.onnx"; bge.write_bytes(b"")
        self._apply(str(ort), str(bge))
        _reset_embedder()
        _reset_warn_cache()
        return self.out

    def _apply(self, ort, bge):
        for k in _MANAGED:
            os.environ.pop(k, None)
        os.environ["CLAUDE_EMBEDDER_STATUS"] = str(self.out)
        os.environ["ORT_DYLIB_PATH"] = ort
        os.environ["BGE_MODEL_PATH"] = bge
        if self.backend:
            os.environ["CLAUDE_EMBEDDER"] = self.backend

    def __exit__(self, *a):
        for k, v in self._saved.items():
            _restore(k, v)
        _reset_embedder()
        _reset_warn_cache()
        self._models.cleanup()
        self.tmp.cleanup()


def _reset_warn_cache():
    from _lib import embed_presence
    embed_presence._reset_warn_cache()


def _restore(key, value):
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


def _reset_embedder():
    mod = sys.modules.get("embedder.embedder")
    if mod is not None:
        mod.reset_singleton_for_tests()


if __name__ == "__main__":
    unittest.main()
