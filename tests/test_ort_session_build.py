"""Unit cover for ort_session_build helpers (fake dispatch)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class AllocAndMemCallsExpectedOps(unittest.TestCase):
    def test_alloc_and_mem_invokes_allocator_then_cpu_mem_info(self):
        from embedder._lib import ort_session_build
        with mock.patch.object(ort_session_build, "ort_dispatch") as disp:
            ort_session_build.alloc_and_mem("api")
            ops = [c.args[1] for c in disp.call.call_args_list]
            self.assertEqual(
                ops, ["GetAllocatorWithDefaultOptions", "CreateCpuMemoryInfo"])


if __name__ == "__main__":
    unittest.main()
