"""WordPiece longest-prefix matcher (direct unit coverage)."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class WordPieceSplit(unittest.TestCase):
    def test_whole_word_in_vocab_returns_single_piece(self):
        from embedder._lib import tokenizer_wordpiece
        vocab = {"hello": 1}
        self.assertEqual(
            tokenizer_wordpiece.split("hello", vocab, "[UNK]"), ["hello"])

    def test_prefix_plus_suffix_splits_with_double_hash(self):
        from embedder._lib import tokenizer_wordpiece
        vocab = {"un": 1, "##known": 2}
        self.assertEqual(
            tokenizer_wordpiece.split("unknown", vocab, "[UNK]"),
            ["un", "##known"])

    def test_no_prefix_match_returns_unk(self):
        from embedder._lib import tokenizer_wordpiece
        self.assertEqual(
            tokenizer_wordpiece.split("xyz", {}, "[UNK]"), ["[UNK]"])


if __name__ == "__main__":
    unittest.main()
