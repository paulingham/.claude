"""BasicTokenizer unit tests: punctuation split, CJK wrap, accent strip."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class BasicTokenize(unittest.TestCase):
    def test_period_splits_off_word(self):
        from embedder._lib import tokenizer_basic
        self.assertEqual(tokenizer_basic.basic_tokenize("bug."), ["bug", "."])

    def test_accents_are_stripped(self):
        from embedder._lib import tokenizer_basic
        self.assertEqual(tokenizer_basic.basic_tokenize("café"), ["cafe"])

    def test_cjk_chars_wrapped_each_as_own_token(self):
        from embedder._lib import tokenizer_basic
        self.assertEqual(tokenizer_basic.basic_tokenize("你好"), ["你", "好"])

    def test_lowercases_mixed_case(self):
        from embedder._lib import tokenizer_basic
        self.assertEqual(tokenizer_basic.basic_tokenize("Hello World"),
                         ["hello", "world"])

    def test_tab_treated_as_whitespace(self):
        from embedder._lib import tokenizer_basic
        self.assertEqual(tokenizer_basic.basic_tokenize("tab\ttab"),
                         ["tab", "tab"])


if __name__ == "__main__":
    unittest.main()
