"""Byte-exact parity vs HF BertTokenizer(do_lower_case=True) on 10 diverse cases.

Oracle: skills/embedder/tests/fixtures/reference-tokens.json.
Covers punctuation, CJK, accents, subwords, apostrophes.
"""
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

_VOCAB = REPO_ROOT / "skills" / "embedder" / "vocab" / "vocab.txt"
_ORACLE = REPO_ROOT / "skills" / "embedder" / "tests" / "fixtures" / "reference-tokens.json"


def _load_cases():
    return json.loads(_ORACLE.read_text())


def _encode(text, max_len):
    from embedder._lib import tokenizer
    return tokenizer.encode(text, max_len=max_len, vocab_path=str(_VOCAB))


def _case(key):
    return next(c for c in _load_cases() if c["input"] == key)


def _assert_parity(tc, key):
    case = _case(key)
    ids, mask, types_ = _encode(case["input"], len(case["input_ids"]))
    tc.assertEqual(ids, case["input_ids"], f"ids mismatch for {key!r}")
    tc.assertEqual(mask, case["attention_mask"])
    tc.assertEqual(types_, case["token_type_ids"])


class ReferenceParity(unittest.TestCase):
    def test_baseline_hello_world(self):
        _assert_parity(self, "hello world")

    def test_punctuation_period_splits(self):
        _assert_parity(self, "I need to fix the bug.")

    def test_accent_strip_cafe(self):
        _assert_parity(self, "café")

    def test_cjk_chars(self):
        _assert_parity(self, "你好世界")

    def test_mixed_case_normalization(self):
        _assert_parity(self, "Hello World")

    def test_tab_whitespace(self):
        _assert_parity(self, "tab\ttab")

    def test_apostrophe_split(self):
        _assert_parity(self, "don't stop")

    def test_subword_wordpiece(self):
        _assert_parity(self, "embedder tokenizer test")

    def test_digits(self):
        _assert_parity(self, "run 42")

    def test_multiple_accents(self):
        _assert_parity(self, "naïve résumé")


if __name__ == "__main__":
    unittest.main()
