"""AC5: doctor emits 'verdict: OK' after a real encode succeeds.

Env-gated: requires ORT_DYLIB_PATH + BGE_MODEL_PATH. Asserts end-to-end
health loop — real backend encodes, status.record_success fires, next
doctor invocation reads the payload and prints verdict: OK. Also asserts
the merge semantics: last_error / last_error_at from a previous failure
are preserved when a later success records last_success_at."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))


def _real_available():
    return bool(os.environ.get("BGE_MODEL_PATH")) and \
        bool(os.environ.get("ORT_DYLIB_PATH"))


@unittest.skipUnless(_real_available(), "BGE_MODEL_PATH/ORT_DYLIB_PATH unset")
class RealDoctorVerdictOkAfterEncode(unittest.TestCase):
    def test_verdict_ok_after_successful_real_encode(self):
        with _scope() as s:
            _encode_and_mark_success()
            out = _run_doctor()
            self.assertIn("verdict: OK", out,
                          f"expected 'verdict: OK' in: {out}")
            payload = _read_status(s.status)
            self.assertIn("last_success_at", payload)


@unittest.skipUnless(_real_available(), "BGE_MODEL_PATH/ORT_DYLIB_PATH unset")
class RealDoctorMergesLastErrorWithLastSuccess(unittest.TestCase):
    def test_last_error_preserved_across_success(self):
        with _scope() as s:
            from embedder import status
            status.record_failure("prior boom", "2026-04-18T00:00:00Z")
            _encode_and_mark_success()
            payload = _read_status(s.status)
            self.assertEqual(payload["last_error"], "prior boom")
            self.assertEqual(payload["last_error_at"],
                             "2026-04-18T00:00:00Z")
            self.assertIn("last_success_at", payload)


def _encode_and_mark_success():
    _encode_once()
    from embedder import status
    status.record_success("2026-04-19T00:00:00Z")


def _encode_once():
    from embedder.embedder import get_embedder, reset_singleton_for_tests
    reset_singleton_for_tests()
    try:
        get_embedder().encode("hello world")
    finally:
        reset_singleton_for_tests()


def _run_doctor():
    from embedder import cli
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main(["doctor"])
    return buf.getvalue()


def _read_status(path):
    import json
    return json.loads(Path(path).read_text())


class _scope:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.status = Path(self.tmp.name) / "status.json"
        self._saved = os.environ.get("CLAUDE_EMBEDDER_STATUS")
        os.environ["CLAUDE_EMBEDDER_STATUS"] = str(self.status)
        return self

    def __exit__(self, *a):
        if self._saved is None:
            os.environ.pop("CLAUDE_EMBEDDER_STATUS", None)
        else:
            os.environ["CLAUDE_EMBEDDER_STATUS"] = self._saved
        self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
