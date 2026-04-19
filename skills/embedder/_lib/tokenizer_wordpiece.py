"""WordPiece longest-prefix greedy matcher. Returns list of sub-tokens."""


def split(word, vocab, unk):
    out, start = [], 0
    while start < len(word):
        chunk = _longest_prefix(word, start, vocab)
        if chunk is None:
            return [unk]
        out.append(chunk)
        start += len(chunk if start == 0 else chunk[2:])
    return out


def _longest_prefix(word, start, vocab):
    end = len(word)
    while end > start:
        piece = word[start:end] if start == 0 else "##" + word[start:end]
        if piece in vocab:
            return piece
        end -= 1
    return None
