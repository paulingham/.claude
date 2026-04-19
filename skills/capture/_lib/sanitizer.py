"""Strip <private>...</private> blocks from captured text."""
import re
import sys

# Tempered-dot: "any char, so long as the remaining string does not start
# with <private> or </private>". This causes outer matches containing a
# nested <private> to be REJECTED by the engine, so re.sub naturally hits
# innermost tags first. DO NOT replace with `.*?` or `[^<]*?` — the former
# breaks nesting semantics; the latter rejects legitimate `<` characters
# inside a block.
_PRIVATE_RE = re.compile(
    r'<private>(?:(?!<private>|</private>).)*?</private>',
    re.DOTALL,
)
_MAX_DEPTH = 10


def sanitize(text):
    if "<private>" not in text:
        return text
    return _strip(text)


def _strip(original):
    text, exhausted = _reduce(original)
    if exhausted:
        return _warn_and_return_original(original)
    return text


def _reduce(text):
    for _ in range(_MAX_DEPTH):
        text, changed = _PRIVATE_RE.subn("", text)
        if not changed:
            return text, False
    return text, True


def _warn_and_return_original(original):
    sys.stderr.write(
        "sanitizer: <private> depth cap exceeded; "
        "returning original\n")
    return original
