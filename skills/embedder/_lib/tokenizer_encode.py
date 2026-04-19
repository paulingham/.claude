"""BERT text-to-subword pipeline: basic_tokenize -> WordPiece -> vocab ids."""
from embedder._lib import tokenizer_basic, tokenizer_wordpiece as wp


def words_to_ids(text, vocab):
    unk_tok = "[UNK]" if "[UNK]" in vocab else None
    ids = []
    for word in tokenizer_basic.basic_tokenize(text):
        ids.extend(_word_to_ids(word, vocab, unk_tok))
    return ids


def _word_to_ids(word, vocab, unk_tok):
    pieces = wp.split(word, vocab, unk_tok)
    return [vocab.get(p, vocab.get(unk_tok, 100)) for p in pieces]
