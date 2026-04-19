"""Punctuation-split primitive: each punctuation char becomes its own token."""
import unicodedata


def split_on_punc(word):
    return ["".join(g) for g in _group(word)]


def _group(word):
    group, last = [], None
    for c in word:
        is_p = _is_punc(c)
        if last is not None and (is_p or last):
            yield group
            group = []
        group.append(c)
        last = is_p
    if group:
        yield group


def _is_punc(c):
    return _is_ascii_punc(c) or unicodedata.category(c).startswith("P")


def _is_ascii_punc(c):
    return (("!" <= c <= "/") or (":" <= c <= "@")
            or ("[" <= c <= "`") or ("{" <= c <= "~"))
