"""Streaming parser for JSONL observation files.

Tolerates concatenated multi-line pretty-printed JSON objects produced by
the observation-capture hook. Malformed spans are skipped with a stderr log.
"""
import json
import sys

_DECODER = json.JSONDecoder()


def parse_file(path, on_error=None):
    """Yield dicts from a JSONL-ish file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    pos = 0
    while pos < len(text):
        pos, obj = _next_object(text, pos, path, on_error)
        if obj is not None:
            yield obj


def _next_object(text, pos, path, on_error):
    pos = _skip_ws(text, pos)
    if pos >= len(text):
        return pos, None
    try:
        obj, end = _DECODER.raw_decode(text, pos)
        return end, obj
    except json.JSONDecodeError as exc:
        _log(on_error, path, pos, exc)
        return _next_line(text, pos), None


def _skip_ws(text, pos):
    while pos < len(text) and text[pos] in " \t\r\n":
        pos += 1
    return pos


def _next_line(text, pos):
    nl = text.find("\n", pos)
    return len(text) if nl == -1 else nl + 1


def _log(on_error, path, pos, exc):
    if on_error:
        on_error(path, pos, exc)
    else:
        print(f"skip {path}:{pos}: {exc}", file=sys.stderr)
