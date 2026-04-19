"""Text cleaning primitives: control/whitespace filter, CJK wrap, accent strip."""
import unicodedata

_WS_CHARS = (" ", "\t", "\n", "\r")
_CJK_RANGES = (
    (0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F), (0x2B740, 0x2B81F), (0x2B820, 0x2CEAF),
    (0xF900, 0xFAFF), (0x2F800, 0x2FA1F),
)


def clean_text(text):
    return "".join(" " if _is_ws(c) else c for c in text if not _is_bad(c))


def _is_ws(c):
    return c in _WS_CHARS or unicodedata.category(c) == "Zs"


def _is_bad(c):
    return c in ("\x00", "\ufffd") or _is_control(c)


def _is_control(c):
    return unicodedata.category(c).startswith("C") and c not in _WS_CHARS


def tokenize_cjk(text):
    return "".join(f" {c} " if _is_cjk(c) else c for c in text)


def _is_cjk(c):
    cp = ord(c)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")
