"""M3: Shared EnvSandbox used by both bootstrap_paths and ort_path_integration.

Unified API: dict-only updates. Callers needing to save-and-restore only
(no change) pass dict.fromkeys(keys, None) → treated as explicit unset
on enter, restored on exit.
"""
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests"))

from env_sandbox import EnvSandbox  # noqa: E402


class EnvSandboxSetsAndRestores(unittest.TestCase):
    def test_enter_sets_and_exit_restores_prior_value(self):
        os.environ["TEST_M3_KEY"] = "before"
        try:
            with EnvSandbox({"TEST_M3_KEY": "during"}):
                self.assertEqual(os.environ["TEST_M3_KEY"], "during")
            self.assertEqual(os.environ["TEST_M3_KEY"], "before")
        finally:
            os.environ.pop("TEST_M3_KEY", None)


class EnvSandboxRestoresAbsentKey(unittest.TestCase):
    def test_unset_on_enter_absent_on_exit(self):
        os.environ.pop("TEST_M3_KEY_ABSENT", None)
        with EnvSandbox({"TEST_M3_KEY_ABSENT": "tmp"}):
            self.assertEqual(os.environ["TEST_M3_KEY_ABSENT"], "tmp")
        self.assertNotIn("TEST_M3_KEY_ABSENT", os.environ)


class EnvSandboxNoneValueUnsets(unittest.TestCase):
    def test_none_removes_key_during_block(self):
        os.environ["TEST_M3_KEY_CLEAR"] = "present"
        try:
            with EnvSandbox({"TEST_M3_KEY_CLEAR": None}):
                self.assertNotIn("TEST_M3_KEY_CLEAR", os.environ)
            self.assertEqual(os.environ["TEST_M3_KEY_CLEAR"], "present")
        finally:
            os.environ.pop("TEST_M3_KEY_CLEAR", None)


if __name__ == "__main__":
    unittest.main()
