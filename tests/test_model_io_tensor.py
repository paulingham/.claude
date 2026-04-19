"""Slice 5a: model_io.int64_tensor marshals ids + shape into ctypes args."""
import sys
import unittest
from ctypes import c_int64
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class Int64TensorMarshalsInputs(unittest.TestCase):
    def test_dispatch_called_with_int64_element_type_and_shape_rank_2(self):
        from embedder._lib import model_io
        captured = _capture(self, model_io)
        model_io.int64_tensor("api", [1, 2, 3], "mem_info")
        self.assertEqual(captured["element_type"], 7)
        self.assertEqual(captured["shape_rank"], 2)

    def test_data_buffer_contains_ids_in_order(self):
        from embedder._lib import model_io
        captured = _capture(self, model_io)
        ids = [10, 20, 30]
        model_io.int64_tensor("api", ids, "mem_info")
        buf = (c_int64 * len(ids)).from_address(captured["data_ptr"])
        self.assertEqual(list(buf), ids)


def _capture(test_case, model_io):
    cap = {}

    def fake_call(_api, _name, _mem, data_ptr, _n, _shape, rank, elem, _out):
        cap["data_ptr"] = data_ptr.value
        cap["shape_rank"] = rank.value
        cap["element_type"] = int(elem)
    patcher = mock.patch.object(model_io, "ort_dispatch")
    d = patcher.start()
    test_case.addCleanup(patcher.stop)
    d.call.side_effect = fake_call
    return cap


if __name__ == "__main__":
    unittest.main()
