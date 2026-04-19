"""BertTokenizer facade: encode(text, max_len) -> (ids, mask, types)."""
from pathlib import Path

from embedder._lib import tokenizer_encode, tokenizer_vocab

_DEFAULT_VOCAB = Path(__file__).resolve().parents[1] / "vocab" / "vocab.txt"
CLS, SEP, PAD = 101, 102, 0


def encode(text, max_len=128, vocab_path=None):
    vocab = tokenizer_vocab.load(str(vocab_path or _DEFAULT_VOCAB))
    body = tokenizer_encode.words_to_ids(text, vocab)[: max_len - 2]
    ids = [CLS] + body + [SEP]
    mask = [1] * len(ids)
    return _pad(ids, max_len), _pad(mask, max_len), [0] * max_len


def _pad(seq, target):
    return seq + [PAD] * (target - len(seq))
