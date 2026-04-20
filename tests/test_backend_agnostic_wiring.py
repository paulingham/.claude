"""Backend-agnosticism guard (S5 verify).

Codifies the claim that capture-time + recall-time wiring goes through
the embedder facade only. If a future commit reaches around the facade
and imports backend-specific symbols directly, these tests fail.

See pipeline-state/claude-mem-port-s5-verify.md for the verify rationale.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _grep(pattern, root):
    try:
        out = subprocess.check_output(
            ["grep", "-rlnE", "--include=*.py", pattern, str(root)],
            text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return []
    return [line for line in out.splitlines() if line]


def _callers_only(hits, allow_prefix):
    return [h for h in hits if not h.startswith(allow_prefix)]


class FacadeIsOnlyBackendSurface(unittest.TestCase):
    def test_no_caller_imports_fake_or_real_directly(self):
        allow = str(REPO_ROOT / "skills" / "embedder") + "/"
        forbidden = r"(FakeEmbedder|from embedder\._lib\.(fake|real|paths))"
        hits = _grep(forbidden, REPO_ROOT / "skills")
        leaks = _callers_only(hits, allow)
        self.assertEqual(leaks, [], f"Backend leak outside embedder/: {leaks}")


class EnvVarsStayInsideEmbedderSkill(unittest.TestCase):
    def test_ort_and_bge_env_confined_to_embedder_skill(self):
        hits = _grep(r"(ORT_DYLIB_PATH|BGE_MODEL_PATH)", REPO_ROOT / "skills")
        leaks = [h for h in hits if not _allowed(h)]
        self.assertEqual(leaks, [], f"Backend env leak: {leaks}")


_ALLOWED_PREFIXES = (
    str(REPO_ROOT / "skills" / "embedder") + "/",
    # S10: zero-cost capture gate duplicates env names to avoid loading
    # embedder.* on the miss path. Co-equivalence enforced by
    # tests/test_embed_presence_coeq.py.
    str(REPO_ROOT / "skills" / "reindex-memory" / "_lib" / "embed_presence.py"),
)


def _allowed(path):
    return any(path.startswith(p) for p in _ALLOWED_PREFIXES)


if __name__ == "__main__":
    unittest.main()
