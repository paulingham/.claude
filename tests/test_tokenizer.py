"""Slice 1: stdlib BertTokenizer WordPiece — algorithm parity tests.

Uses mini_vocab fixture (124 tokens) so tests have a known oracle
without the 30522-token production vocab.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

_MINI = REPO_ROOT / "skills" / "embedder" / "vocab" / "tests" / "mini_vocab.txt"


class EncodeBasic(unittest.TestCase):
    def test_hello_world_ids(self):
        from embedder._lib import tokenizer
        ids, mask, types = tokenizer.encode("hello world", max_len=8,
                                            vocab_path=str(_MINI))
        self.assertEqual(ids[:4], [101, 104, 105, 102])
        self.assertEqual(ids[4:], [0, 0, 0, 0])
        self.assertEqual(mask, [1, 1, 1, 1, 0, 0, 0, 0])
        self.assertEqual(types, [0] * 8)

    def test_empty_string(self):
        from embedder._lib import tokenizer
        ids, mask, _ = tokenizer.encode("", max_len=4, vocab_path=str(_MINI))
        self.assertEqual(ids, [101, 102, 0, 0])
        self.assertEqual(mask, [1, 1, 0, 0])

    def test_unknown_word_goes_to_unk(self):
        from embedder._lib import tokenizer
        ids, _, _ = tokenizer.encode("zzzqqqxxx", max_len=4,
                                     vocab_path=str(_MINI))
        self.assertEqual(ids[:3], [101, 100, 102])


class EncodeSubword(unittest.TestCase):
    def test_wordpiece_suffix_lookup(self):
        # "unknown" -> ["un", "##known"] -> ids 116, 117
        from embedder._lib import tokenizer
        ids, _, _ = tokenizer.encode("unknown", max_len=6,
                                     vocab_path=str(_MINI))
        self.assertEqual(ids[:4], [101, 116, 117, 102])


class EncodeTruncation(unittest.TestCase):
    def test_max_len_truncates_body_preserving_cls_sep(self):
        from embedder._lib import tokenizer
        ids, _, _ = tokenizer.encode("hello world the cat sat on mat",
                                     max_len=4, vocab_path=str(_MINI))
        self.assertEqual(len(ids), 4)
        self.assertEqual(ids[0], 101)
        self.assertEqual(ids[-1], 102)


class EncodeWithPreloadedVocab(unittest.TestCase):
    def test_encode_accepts_vocab_dict_without_path(self):
        from embedder._lib import tokenizer, tokenizer_vocab
        vocab = tokenizer_vocab.load(str(_MINI))
        ids, _, _ = tokenizer.encode("hello world", max_len=4, vocab=vocab)
        self.assertEqual(ids, [101, 104, 105, 102])

    def test_encode_does_not_resolve_path_when_vocab_provided(self):
        from embedder._lib import tokenizer, tokenizer_vocab
        vocab = tokenizer_vocab.load(str(_MINI))
        with mock.patch.object(tokenizer_vocab, "load",
                               side_effect=AssertionError("should not reload")):
            tokenizer.encode("hello", max_len=3, vocab=vocab)


if __name__ == "__main__":
    unittest.main()
