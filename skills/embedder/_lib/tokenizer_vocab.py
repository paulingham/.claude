"""Load vocab.txt -> {token: id}. Line-number = id (0-indexed)."""
from functools import lru_cache


@lru_cache(maxsize=4)
def load(vocab_path):
    with open(vocab_path, encoding="utf-8") as fh:
        tokens = [line.rstrip("\n") for line in fh]
    return {tok: idx for idx, tok in enumerate(tokens)}


def unk_id(vocab):
    return vocab.get("[UNK]", 100)
