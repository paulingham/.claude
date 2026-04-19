"""rerank_support.try_embedder routes via embedder.embedder.get_embedder facade."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib.fake import FakeEmbedder  # noqa: E402
from embedder._lib.paths import EmbedderUnavailable  # noqa: E402
from recall._lib import rerank_support  # noqa: E402


def _env_without_embedder():
    return {k: v for k, v in os.environ.items() if k != "CLAUDE_EMBEDDER"}


class RoutesThroughFacadeWhenEnvUnset(unittest.TestCase):
    def test_returns_embedder_from_facade(self):
        fake = FakeEmbedder()
        with mock.patch.dict(os.environ, _env_without_embedder(), clear=True), \
                mock.patch("embedder.embedder.get_embedder", return_value=fake):
            self.assertIs(rerank_support.try_embedder(), fake)


class ReturnsNoneWhenFacadeUnavailable(unittest.TestCase):
    def test_embedder_unavailable_returns_none(self):
        def raiser():
            raise EmbedderUnavailable("ORT not set")
        with mock.patch("embedder.embedder.get_embedder", side_effect=raiser):
            self.assertIsNone(rerank_support.try_embedder())


if __name__ == "__main__":
    unittest.main()
