"""WordPiece longest-prefix greedy matcher. Returns list of sub-tokens."""


def split(word, vocab, unk):
    chunks = list(_iter_chunks(word, vocab))
    return [unk] if None in chunks else chunks


def _iter_chunks(word, vocab):
    start = 0
    while start < len(word):
        chunk = _longest_prefix(word, start, vocab)
        yield chunk
        start = _next_start(start, chunk)


def _next_start(start, chunk):
    if chunk is None:
        return 10 ** 9
    return start + len(chunk if start == 0 else chunk[2:])


def _longest_prefix(word, start, vocab):
    for end in range(len(word), start, -1):
        piece = _piece(word, start, end)
        if piece in vocab:
            return piece
    return None


def _piece(word, start, end):
    return word[start:end] if start == 0 else "##" + word[start:end]
