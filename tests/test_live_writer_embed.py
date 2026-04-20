"""AC1 + AC2 + AC9: capture-time embedding is on by default; opt-out via CLAUDE_EMBED_AT_CAPTURE=0."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "skills"))

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


class OptOutSkipsEmbedder(unittest.TestCase):
    def test_opt_out_skips_embedder_import(self):
        _clear_embedder_env()
        os.environ["CLAUDE_EMBED_AT_CAPTURE"] = "0"
        for mod in [m for m in list(sys.modules)
                    if m.startswith("embedder")]:
            sys.modules.pop(mod, None)
        try:
            self._assert_zero_cost_on_write()
        finally:
            _clear_embedder_env()

    def _assert_zero_cost_on_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            live_writer.write_one(_obj(), db)
            self.assertEqual(_count_embeddings(db), 0)
            self.assertNotIn("embedder.embedder", sys.modules)


class DefaultPathAttemptsEmbed(unittest.TestCase):
    def test_default_path_imports_embedder_module(self):
        from _lib import embed_gate
        saved = os.environ.pop("CLAUDE_EMBED_AT_CAPTURE", None)
        for mod in [m for m in list(sys.modules)
                    if m.startswith("embedder")]:
            sys.modules.pop(mod, None)
        try:
            self._invoke_gate_and_assert_import(embed_gate)
        finally:
            _restore_env("CLAUDE_EMBED_AT_CAPTURE", saved)

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
        _set_opt_in_fake()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db = Path(tmp) / "memory.sqlite"
                schema.ensure(db)
                live_writer.write_one(_obj(), db)
                self.assertEqual(_count_embeddings(db), 1)
        finally:
            _clear_embedder_env()


_MODEL_KEYS = ("ORT_DYLIB_PATH", "BGE_MODEL_PATH")


class OptInToleratesMissingModel(unittest.TestCase):
    def test_observation_still_written_when_embedder_unavailable(self):
        saved = {k: os.environ.get(k) for k in _MODEL_KEYS}
        for k in _MODEL_KEYS:
            os.environ.pop(k, None)
        os.environ["CLAUDE_EMBED_AT_CAPTURE"] = "1"
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
        os.environ["CLAUDE_EMBED_AT_CAPTURE"] = "1"
        os.environ.pop("CLAUDE_EMBEDDER", None)
        _reset_singleton()
        corrupt = tempfile.NamedTemporaryFile(suffix=".onnx", delete=False)
        corrupt.close()
        prev_bge = os.environ.get("BGE_MODEL_PATH")
        os.environ["BGE_MODEL_PATH"] = corrupt.name
        try:
            self._assert_write_tolerates_bad_model()
        finally:
            _restore_env("BGE_MODEL_PATH", prev_bge)
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
        _set_opt_in_fake()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db = Path(tmp) / "memory.sqlite"
                schema.ensure(db)
                durations = [_measure(db, _timed_obj(i), time)
                             for i in range(20)]
                median = sorted(durations)[10]
                self.assertLess(median, 0.05)
        finally:
            _clear_embedder_env()


def _timed_obj(i):
    return {"session_id": "t", "timestamp": f"2026-04-19T00:00:{i:02d}Z",
            "tool": "Read", "file": f"/f{i}.py", "outcome": "ok",
            "project_hash": "pha"}


def _measure(db, obj, time_mod):
    t0 = time_mod.perf_counter()
    live_writer.write_one(obj, db)
    return time_mod.perf_counter() - t0


def _set_opt_in_fake():
    os.environ["CLAUDE_EMBED_AT_CAPTURE"] = "1"
    os.environ["CLAUDE_EMBEDDER"] = "fake"
    _reset_singleton()


def _clear_embedder_env():
    for k in ("CLAUDE_EMBED_AT_CAPTURE", "CLAUDE_EMBEDDER"):
        os.environ.pop(k, None)
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
