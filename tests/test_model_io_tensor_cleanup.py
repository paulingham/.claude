"""Regression: model_io.ort_dispatch mock must not bleed across tests.

test_model_io_tensor uses mock.patch.start without addCleanup — the patch
persists into later tests, causing test_ort_tensor to crash when it calls
model_io.int64_tensor with a mock-sidelined ort_dispatch (native segfault)."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
_TESTS = str(REPO_ROOT / "tests")
for p in (_SKILL, _TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)


class PatchDoesNotBleedOutsideTest(unittest.TestCase):
    def test_ort_dispatch_is_real_after_tensor_tests_run(self):
        from embedder._lib import model_io
        import embedder._lib.ort_dispatch as real_dispatch
        self._run_tensor_tests()
        self.assertIs(model_io.ort_dispatch, real_dispatch,
                      "model_io.ort_dispatch was not restored after patch")

    def _run_tensor_tests(self):
        import test_model_io_tensor as mod
        suite = unittest.TestLoader().loadTestsFromTestCase(
            mod.Int64TensorMarshalsInputs)
        import io
        unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite)


if __name__ == "__main__":
    unittest.main()
