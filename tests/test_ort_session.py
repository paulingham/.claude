"""Slice 4: session bring-up — env + options + session + names."""
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

_DYLIB = "/opt/homebrew/lib/libonnxruntime.dylib"


def _model_available():
    model = os.environ.get("BGE_MODEL_PATH")
    return Path(_DYLIB).exists() and bool(model) and Path(model).exists()


@unittest.skipUnless(_model_available(), "BGE_MODEL_PATH not set/usable")
class BuildSessionExposesInputNames(unittest.TestCase):
    def test_build_returns_handle_with_input_names(self):
        from embedder._lib import ort_api, ort_session
        api = ort_api.load_api(_DYLIB)
        handle = ort_session.build(api, os.environ["BGE_MODEL_PATH"])
        try:
            self.assertEqual(set(handle.input_names),
                             {"input_ids", "attention_mask", "token_type_ids"})
            self.assertEqual(handle.output_names[0], "last_hidden_state")
        finally:
            ort_session.close(handle)


class CloseReleasesAllFieldsEvenOnFailure(unittest.TestCase):
    def test_remaining_releases_run_after_first_failure(self):
        from embedder._lib import ort_session
        from unittest import mock
        import types as _types
        handle = _types.SimpleNamespace(
            api="api", env=_Ptr(1), session_options=_Ptr(2),
            session=_Ptr(3), mem_info=_Ptr(4))
        calls = _record_releases_with_first_failure(ort_session)
        with self.assertRaises(RuntimeError):
            ort_session.close(handle)
        ops = [c[1] for c in calls]
        self.assertEqual(set(ops), {"ReleaseSession", "ReleaseSessionOptions",
                                    "ReleaseMemoryInfo", "ReleaseEnv"})


class _Ptr:
    def __init__(self, v):
        self.value = v


def _record_releases_with_first_failure(ort_session):
    from unittest import mock
    from embedder._lib import ort_session_close
    calls = []

    def fake_call(api, op, ptr):
        calls.append((api, op))
        if op == "ReleaseSession":
            raise RuntimeError("session release boom")
    mock.patch.object(ort_session_close.ort_dispatch, "call",
                      side_effect=fake_call).start()
    return calls


if __name__ == "__main__":
    unittest.main()
