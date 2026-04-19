"""Direct unit tests for the text-to-ids pipeline (tokenizer_encode)."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class WordsToIds(unittest.TestCase):
    def test_uses_basic_tokenize_to_split_punctuation(self):
        from embedder._lib import tokenizer_encode
        vocab = {"[UNK]": 100, "bug": 500, ".": 501}
        ids = tokenizer_encode.words_to_ids("bug.", vocab)
        self.assertEqual(ids, [500, 501])

    def test_unknown_word_goes_to_unk_id(self):
        from embedder._lib import tokenizer_encode
        vocab = {"[UNK]": 100}
        self.assertEqual(tokenizer_encode.words_to_ids("zzz", vocab), [100])


if __name__ == "__main__":
    unittest.main()
