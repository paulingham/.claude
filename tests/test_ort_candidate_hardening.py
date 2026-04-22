"""M1: Drop /usr/local/lib/libonnxruntime.so from Linux defaults.

/usr/local/lib is often group-writable; including it in the default
probe list widens the library-injection surface. Distro-managed paths
are the only defaults. Users installing into /usr/local can still set
ORT_DYLIB_PATH explicitly.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib import bootstrap_paths  # noqa: E402


class LinuxCandidatesExcludeUsrLocal(unittest.TestCase):
    def test_usr_local_so_not_in_default_linux_candidates(self):
        self.assertNotIn(
            "/usr/local/lib/libonnxruntime.so",
            bootstrap_paths._LINUX_CANDIDATES)


class LinuxCandidatesCoverDistroPaths(unittest.TestCase):
    def test_candidates_include_multiarch_and_usr_lib(self):
        self.assertIn(
            "/usr/lib/x86_64-linux-gnu/libonnxruntime.so",
            bootstrap_paths._LINUX_CANDIDATES)
        self.assertIn(
            "/usr/lib/libonnxruntime.so",
            bootstrap_paths._LINUX_CANDIDATES)


if __name__ == "__main__":
    unittest.main()
