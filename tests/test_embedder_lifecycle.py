"""Slice 6: reset_singleton_for_tests closes prior embedder; close order."""
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class ResetClosesPriorEmbedder(unittest.TestCase):
    def test_reset_calls_close_on_embedder_with_close(self):
        from embedder import embedder as facade
        stub = mock.Mock(spec=["close", "encode"])
        facade._singleton = stub
        facade.reset_singleton_for_tests()
        stub.close.assert_called_once()
        self.assertIsNone(facade._singleton)

    def test_reset_tolerates_embedder_without_close(self):
        from embedder import embedder as facade
        facade._singleton = types.SimpleNamespace(encode=lambda t: b"")
        facade.reset_singleton_for_tests()
        self.assertIsNone(facade._singleton)


class OrtSessionCloseReleaseOrder(unittest.TestCase):
    def test_release_order_is_session_opts_meminfo_env(self):
        from embedder._lib import ort_session
        handle, calls = _recording_handle()
        with mock.patch.object(ort_session, "ort_dispatch") as disp:
            disp.call.side_effect = lambda api, name, _p: calls.append(name)
            ort_session.close(handle)
        self.assertEqual(calls, [
            "ReleaseSession", "ReleaseSessionOptions",
            "ReleaseMemoryInfo", "ReleaseEnv"])

    def test_close_is_idempotent(self):
        from embedder._lib import ort_session
        handle, calls = _recording_handle()
        with mock.patch.object(ort_session, "ort_dispatch") as disp:
            disp.call.side_effect = lambda *a: calls.append(a[1])
            ort_session.close(handle)
            ort_session.close(handle)
        self.assertEqual(len(calls), 4)


def _recording_handle():
    from ctypes import c_void_p
    return types.SimpleNamespace(
        api="api", env=c_void_p(1), session_options=c_void_p(2),
        session=c_void_p(3), allocator=c_void_p(4), mem_info=c_void_p(5),
        input_names=(), output_names=()), []


if __name__ == "__main__":
    unittest.main()
