"""S10: capture-time embedding gated by model-file presence (no env flag)."""
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

import _support  # noqa: F401
from _lib import live_writer, schema  # noqa: E402


def _obj():
    return {"session_id": "s1", "timestamp": "2026-04-19T00:00:00Z",
            "tool": "Read", "file": "/a.py", "outcome": "success",
            "project_hash": "pha"}


def _count_embeddings(db):
    con = sqlite3.connect(str(db))
    try:
        return con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    finally:
        con.close()


_MODEL_KEYS = ("ORT_DYLIB_PATH", "BGE_MODEL_PATH")


class CaptureSkipsEmbedderWhenModelMissing(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in _MODEL_KEYS}
        os.environ["ORT_DYLIB_PATH"] = "/nonexistent/stub.dylib"
        os.environ["BGE_MODEL_PATH"] = "/nonexistent/stub.onnx"
        for mod in [m for m in list(sys.modules)
                    if m.startswith("embedder")]:
            sys.modules.pop(mod, None)
        from _lib import embed_presence
        embed_presence._reset_warn_cache()

    def tearDown(self):
        for k, v in self._saved.items():
            _restore_env(k, v)
        from _lib import embed_presence
        embed_presence._reset_warn_cache()

    def test_capture_skips_embedder_when_model_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            rc = live_writer.write_one(_obj(), db)
            self.assertEqual(rc, 1)
            self.assertEqual(_count_embeddings(db), 0)
            self.assertNotIn("embedder.embedder", sys.modules)
            self.assertNotIn("embedder._lib", sys.modules)


class DefaultPathAttemptsEmbed(unittest.TestCase):
    def test_default_path_imports_embedder_module(self):
        from _lib import embed_gate, embed_presence
        saved = {k: os.environ.get(k) for k in _MODEL_KEYS}
        for mod in [m for m in list(sys.modules)
                    if m.startswith("embedder")]:
            sys.modules.pop(mod, None)
        embed_presence._reset_warn_cache()
        try:
            self._invoke_with_stub_models(embed_gate)
        finally:
            for k, v in saved.items():
                _restore_env(k, v)
            embed_presence._reset_warn_cache()

    def _invoke_with_stub_models(self, embed_gate):
        with tempfile.TemporaryDirectory() as td:
            ort = Path(td) / "stub.dylib"; ort.write_bytes(b"")
            bge = Path(td) / "stub.onnx"; bge.write_bytes(b"")
            os.environ["ORT_DYLIB_PATH"] = str(ort)
            os.environ["BGE_MODEL_PATH"] = str(bge)
            self._invoke_gate_and_assert_import(embed_gate)

    def _invoke_gate_and_assert_import(self, embed_gate):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            con = sqlite3.connect(str(db))
            try:
                embed_gate.maybe_embed(con, _obj(), "h" * 64)
            finally:
                con.close()
            self.assertIn("embedder.embedder", sys.modules)


class OptInWritesEmbeddingWithFake(unittest.TestCase):
    def test_embedding_row_written_when_opted_in(self):
        with _fake_backend_with_stub_models():
            try:
                self._assert_one_embedding_row()
            finally:
                _clear_embedder_env()

    def _assert_one_embedding_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            live_writer.write_one(_obj(), db)
            self.assertEqual(_count_embeddings(db), 1)


class ObservationStillWrittenWhenEmbedderUnavailable(unittest.TestCase):
    def test_observation_still_written_when_embedder_unavailable(self):
        saved = {k: os.environ.get(k) for k in _MODEL_KEYS}
        for k in _MODEL_KEYS:
            os.environ[k] = "/nonexistent/s." + k.split("_")[0].lower()
        os.environ.pop("CLAUDE_EMBEDDER", None)
        _reset_singleton()
        try:
            self._assert_observation_still_written()
        finally:
            for k, v in saved.items():
                _restore_env(k, v)
            _clear_embedder_env()

    def _assert_observation_still_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            rc = live_writer.write_one(_obj(), db)
            self.assertEqual(rc, 1)
            self.assertEqual(_count_embeddings(db), 0)


class CorruptModelPathHandled(unittest.TestCase):
    def test_corrupt_model_swallowed_observation_still_written(self):
        os.environ.pop("CLAUDE_EMBEDDER", None)
        _reset_singleton()
        corrupt = tempfile.NamedTemporaryFile(suffix=".onnx", delete=False)
        corrupt.close()
        saved = {k: os.environ.get(k) for k in _MODEL_KEYS}
        os.environ["ORT_DYLIB_PATH"] = corrupt.name
        os.environ["BGE_MODEL_PATH"] = corrupt.name
        try:
            self._assert_write_tolerates_bad_model()
        finally:
            for k, v in saved.items():
                _restore_env(k, v)
            os.unlink(corrupt.name)
            _clear_embedder_env()

    def _assert_write_tolerates_bad_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            rc = live_writer.write_one(_obj(), db)
            self.assertEqual(rc, 1)


class OptInLatencyUnder5ms(unittest.TestCase):
    def test_fake_embedder_opt_in_below_5ms_median(self):
        import time
        with _fake_backend_with_stub_models():
            try:
                self._assert_median_latency(time)
            finally:
                _clear_embedder_env()

    def _assert_median_latency(self, time_mod):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            durations = [_measure(db, _timed_obj(i), time_mod)
                         for i in range(20)]
            median = sorted(durations)[10]
            self.assertLess(median, 0.05)


def _timed_obj(i):
    return {"session_id": "t", "timestamp": f"2026-04-19T00:00:{i:02d}Z",
            "tool": "Read", "file": f"/f{i}.py", "outcome": "ok",
            "project_hash": "pha"}


def _measure(db, obj, time_mod):
    t0 = time_mod.perf_counter()
    live_writer.write_one(obj, db)
    return time_mod.perf_counter() - t0


class _fake_backend_with_stub_models:
    """Sets CLAUDE_EMBEDDER=fake + stub model paths; restores on exit."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k)
                       for k in _MODEL_KEYS + ("CLAUDE_EMBEDDER",)}
        self._td = tempfile.TemporaryDirectory()
        for k, suf in (("ORT_DYLIB_PATH", ".dylib"),
                       ("BGE_MODEL_PATH", ".onnx")):
            p = Path(self._td.name) / ("s" + suf); p.write_bytes(b"")
            os.environ[k] = str(p)
        os.environ["CLAUDE_EMBEDDER"] = "fake"
        _reset_singleton()
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            _restore_env(k, v)
        _reset_singleton()
        self._td.cleanup()


def _clear_embedder_env():
    os.environ.pop("CLAUDE_EMBEDDER", None)
    _reset_singleton()


def _reset_singleton():
    mod = sys.modules.get("embedder.embedder")
    if mod is not None:
        mod.reset_singleton_for_tests()


def _restore_env(key, value):
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
