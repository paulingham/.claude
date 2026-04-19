"""Embedder facade: env-dispatch between FakeEmbedder and real ctypes path."""
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


def _reload():
    """Drop cached embedder module so env-var changes take effect."""
    for mod in [m for m in list(sys.modules)
                if m.startswith("embedder.embedder")]:
        sys.modules.pop(mod, None)


class FakeDispatch(unittest.TestCase):
    def test_claude_embedder_fake_returns_fake(self):
        _reload()
        os.environ["CLAUDE_EMBEDDER"] = "fake"
        try:
            from embedder.embedder import get_embedder
            emb = get_embedder()
            self.assertEqual(len(emb.encode("hi")), 1536)
        finally:
            os.environ.pop("CLAUDE_EMBEDDER", None)


class SingletonReuse(unittest.TestCase):
    def test_two_calls_return_same_instance(self):
        _reload()
        os.environ["CLAUDE_EMBEDDER"] = "fake"
        try:
            from embedder.embedder import get_embedder
            self.assertIs(get_embedder(), get_embedder())
        finally:
            os.environ.pop("CLAUDE_EMBEDDER", None)


if __name__ == "__main__":
    unittest.main()
