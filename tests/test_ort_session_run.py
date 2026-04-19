"""Slice 5b: Run produces output tensor of shape (1, seq_len, 384)."""
import ctypes
import os
import sys
import types
import unittest
from ctypes import c_int64, c_size_t, c_void_p
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

_DYLIB = "/opt/homebrew/lib/libonnxruntime.dylib"


def _env_ok():
    model = os.environ.get("BGE_MODEL_PATH")
    return Path(_DYLIB).exists() and bool(model) and Path(model).exists()


@unittest.skipUnless(_env_ok(), "ORT dylib/model not available")
class RunOutputTensorShape(unittest.TestCase):
    def test_run_returns_tensor_of_shape_1_seq_384(self):
        from embedder._lib import ort_api, ort_session, ort_session_run
        api = ort_api.load_api(_DYLIB)
        handle = ort_session.build(api, os.environ["BGE_MODEL_PATH"])
        try:
            seq_len = 8
            ids = [101] + [7] * (seq_len - 2) + [102]
            mask = [1] * seq_len
            types_ = [0] * seq_len
            out = ort_session_run.run(handle, ids, mask, types_)
            self.assertEqual(_shape(api, out), (1, seq_len, 384))
        finally:
            ort_session.close(handle)


def _shape(api, ort_value):
    from embedder._lib import ort_dispatch
    info = c_void_p()
    ort_dispatch.call(api, "GetTensorTypeAndShape", ort_value,
                      ctypes.byref(info))
    rank = c_size_t()
    ort_dispatch.call(api, "GetDimensionsCount", info, ctypes.byref(rank))
    dims = (c_int64 * rank.value)()
    ort_dispatch.call(api, "GetDimensions", info, dims, c_size_t(rank.value))
    ort_dispatch.call(api, "ReleaseTensorTypeAndShapeInfo", info)
    return tuple(int(d) for d in dims)


class RunCallsDispatchWithThreeInputsOneOutput(unittest.TestCase):
    def test_run_builds_three_inputs_and_one_output_name_array(self):
        from embedder._lib import ort_session_run
        handle = _fake_handle()
        calls = _record_calls(ort_session_run)
        ort_session_run.run(handle, [1, 2], [1, 1], [0, 0])
        run_call = next(c for c in calls if c[1] == "Run")
        in_count, out_count = run_call[6].value, run_call[8].value
        self.assertEqual((in_count, out_count), (3, 1))


def _fake_handle():
    return types.SimpleNamespace(
        api="api", session="sess", mem_info="mem",
        input_names=("input_ids", "attention_mask", "token_type_ids"),
        output_names=("last_hidden_state",))


def _record_calls(ort_session_run):
    calls = []

    def fake_call(*args):
        calls.append(args)
        if args[1] == "CreateTensorWithDataAsOrtValue":
            args[-1]._obj.value = 1
    patcher = mock.patch.object(ort_session_run, "ort_dispatch")
    d = patcher.start()
    d.call.side_effect = fake_call
    mi = mock.patch.object(ort_session_run, "model_io")
    mio = mi.start()
    mio.int64_tensor.side_effect = lambda api, v, mem: (c_void_p(1), v)
    return calls


class RunReleasesInputsWhenInvokeRaises(unittest.TestCase):
    def test_release_called_even_when_run_dispatch_raises(self):
        from embedder._lib import ort_session_run
        handle = _fake_handle()
        release_count = _count_releases_on_invoke_error(ort_session_run)
        with self.assertRaises(RuntimeError):
            ort_session_run.run(handle, [1, 2], [1, 1], [0, 0])
        self.assertEqual(release_count[0], 3)


def _count_releases_on_invoke_error(ort_session_run):
    count = [0]

    def fake_call(*args):
        if args[1] == "Run":
            raise RuntimeError("boom")
        if args[1] == "ReleaseValue":
            count[0] += 1
    patcher = mock.patch.object(ort_session_run, "ort_dispatch")
    d = patcher.start()
    d.call.side_effect = fake_call
    mi = mock.patch.object(ort_session_run, "model_io")
    mio = mi.start()
    mio.int64_tensor.side_effect = lambda api, v, mem: (c_void_p(1), v)
    return count


if __name__ == "__main__":
    unittest.main()
