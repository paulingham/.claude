"""AC1, AC6, AC9: <private>...</private> sanitizer unit tests."""
import io
import sys
import time
import unittest
from pathlib import Path
from contextlib import redirect_stderr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))

from capture._lib import sanitizer  # noqa: E402


class FastPathNoTag(unittest.TestCase):
    def test_returns_identical_string_when_no_tag(self):
        text = "hello world, no secrets here"
        self.assertEqual(sanitizer.sanitize(text), text)


class SingleBlockStripped(unittest.TestCase):
    def test_strips_tag_and_contents(self):
        out = sanitizer.sanitize("public <private>secret</private> more")
        self.assertEqual(out, "public  more")


class MultiLineBlockStripped(unittest.TestCase):
    def test_strips_block_spanning_newlines(self):
        out = sanitizer.sanitize("a\n<private>l1\nl2</private>\nb")
        self.assertEqual(out, "a\n\nb")


class NestedBlocksStripped(unittest.TestCase):
    def test_strips_outer_after_inner(self):
        out = sanitizer.sanitize(
            "x<private>a<private>b</private>c</private>y")
        self.assertEqual(out, "xy")


class LegitimateLessThanInsideBlock(unittest.TestCase):
    def test_strips_block_containing_less_than_char(self):
        out = sanitizer.sanitize("<private>x < y</private>!")
        self.assertEqual(out, "!")


class MalformedUnclosedReturnsInput(unittest.TestCase):
    def test_unclosed_private_tag_unchanged(self):
        text = "before <private>no end tag here"
        self.assertEqual(sanitizer.sanitize(text), text)


class EmptyBodyPrivateStripped(unittest.TestCase):
    """Gap 1: <private></private> with empty body must be removed."""
    def test_empty_body_removed(self):
        self.assertEqual(sanitizer.sanitize("a<private></private>b"), "ab")


class CrlfInsidePrivateStripped(unittest.TestCase):
    """Gap 2: CRLF line endings inside <private> block must be stripped."""
    def test_crlf_content_removed(self):
        out = sanitizer.sanitize("pre <private>\r\nsecret\r\n</private> post")
        self.assertEqual(out, "pre  post")


class AttributeVariantsNotStripped(unittest.TestCase):
    """Gap 4: only literal `<private>` opens a block.

    Attribute-bearing opens (`<private foo>`) and case variants (`<PRIVATE>`)
    must NOT match; they pass through unchanged. Protects against a future
    regex relax that would silently over-strip benign content.
    """
    def test_attribute_variant_unchanged(self):
        text = "<private foo>x</private>"
        self.assertEqual(sanitizer.sanitize(text), text)

    def test_uppercase_variant_unchanged(self):
        text = "<PRIVATE>x</PRIVATE>"
        self.assertEqual(sanitizer.sanitize(text), text)


class DeepUnclosedNoBacktrackingBlowup(unittest.TestCase):
    """1000-deep unclosed <private> must complete in <100ms (linearity)."""
    def test_thousand_deep_unclosed_returns_fast(self):
        text = "<private>" * 1000 + "no closer"
        start = time.perf_counter()
        out = sanitizer.sanitize(text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertEqual(out, text)
        self.assertLess(elapsed_ms, 100)


class DepthCapReturnsOriginalWithWarn(unittest.TestCase):
    """11-deep correctly nested blocks hit the cap — return original, WARN."""
    def test_over_cap_returns_original_and_warns(self):
        text = "<private>" * 11 + "x" + "</private>" * 11
        buf = io.StringIO()
        with redirect_stderr(buf):
            out = sanitizer.sanitize(text)
        self.assertEqual(out, text)
        self.assertIn("private", buf.getvalue().lower())


class FastPathThroughputOnRealisticPayload(unittest.TestCase):
    """AC6: 10k calls on ≥1KB payload without <private> in <50ms total."""
    def test_ten_thousand_calls_under_fifty_ms(self):
        payload = _realistic_kilobyte_payload()
        self.assertGreaterEqual(len(payload), 1024)
        start = time.perf_counter()
        for _ in range(10_000):
            sanitizer.sanitize(payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 50)


class ZeroCostImports(unittest.TestCase):
    """AC9: sanitizer imports nothing heavy (no embedder, recall, numpy)."""
    def test_only_stdlib_imports(self):
        src = Path(sanitizer.__file__).read_text()
        banned = ("numpy", "embedder", "recall", "sqlite3", "torch")
        for name in banned:
            self.assertNotIn(name, src)


def _realistic_kilobyte_payload():
    lines = [
        "Read /src/app/components/Header.tsx",
        "diff --git a/Header.tsx b/Header.tsx",
        "-  <h1>old title</h1>",
        "+  <h1>new title</h1>",
        "lint: 0 errors, 0 warnings",
        "tests: 42 passed, 0 failed, 1 skipped",
        "coverage: 87.3% statements, 72.1% branches",
        "bundle size: 124.3 KB gzipped (+1.2 KB)",
    ]
    return ("\n".join(lines) + "\n") * 16


if __name__ == "__main__":
    unittest.main()
