"""BERT text-to-subword pipeline: clean, lower, split, WordPiece."""
import unicodedata

from embedder._lib import tokenizer_wordpiece as wp


def words_to_ids(text, vocab):
    unk_tok = "[UNK]" if "[UNK]" in vocab else None
    ids = []
    for word in _whitespace_split(_basic_clean(text)):
        ids.extend(_word_to_ids(word, vocab, unk_tok))
    return ids


def _basic_clean(text):
    text = unicodedata.normalize("NFC", text)
    return "".join(ch for ch in text.lower() if not _is_control(ch))


def _is_control(ch):
    return unicodedata.category(ch) in ("Cc", "Cf") and ch not in ("\t", "\n")


def _whitespace_split(text):
    return [w for w in text.split() if w]


def _word_to_ids(word, vocab, unk_tok):
    pieces = wp.split(word, vocab, unk_tok)
    return [vocab.get(p, vocab.get(unk_tok, 100)) for p in pieces]
