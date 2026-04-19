"""AC11: recall emits stderr banner when embedder unavailable."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "skills"))

from _support import build_populated_db  # noqa: E402
from recall import recall as recall_mod  # noqa: E402

BANNER = ("[recall: lexical-only — run 'embedder doctor' "
          "to enable semantic rerank]")


class BannerOnMissingEmbedder(unittest.TestCase):
    def test_banner_emitted_when_embedder_missing(self):
        os.environ.pop("CLAUDE_EMBEDDER", None)
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            buf = io.StringIO()
            with redirect_stderr(buf):
                recall_mod.search("Read", db_path=db)
            self.assertIn(BANNER, buf.getvalue())


class NoBannerOnHappyPath(unittest.TestCase):
    def test_no_banner_when_fake_embedder_available(self):
        os.environ["CLAUDE_EMBEDDER"] = "fake"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db, _ = build_populated_db(tmp)
                buf = io.StringIO()
                with redirect_stderr(buf):
                    recall_mod.search("Read", db_path=db)
                self.assertNotIn("recall: lexical-only", buf.getvalue())
        finally:
            os.environ.pop("CLAUDE_EMBEDDER", None)


if __name__ == "__main__":
    unittest.main()
