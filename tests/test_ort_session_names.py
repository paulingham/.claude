"""Unit cover for ort_session_names helpers (fake dispatch)."""
import sys
import unittest
from ctypes import c_char_p, c_size_t
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class ReadNamesFakeDispatch(unittest.TestCase):
    def test_read_input_names_returns_tuple_of_decoded_strings(self):
        from embedder._lib import ort_session_names
        with mock.patch.object(ort_session_names, "ort_dispatch") as disp:
            disp.call.side_effect = _fake_dispatch(["input_ids"])
            names = ort_session_names.read_input_names("api", "sess", "alloc")
            self.assertEqual(names, ("input_ids",))


def _fake_dispatch(payload):
    state = {"names": list(payload)}

    def call(_api, op, *args):
        if "Count" in op:
            args[-1]._obj.value = len(payload)
        elif "Name" in op:
            args[-1]._obj.value = state["names"].pop(0).encode("utf-8")
    return call


if __name__ == "__main__":
    unittest.main()
