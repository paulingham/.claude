"""Detect whether an observation matches the privacy allowlist."""
import fnmatch
import os


def is_private(obj, allow):
    if _file_matches(obj.get("file"), allow.file_globs):
        return True
    return _content_matches(obj, allow.content_regexes)


def _file_matches(path, globs):
    if not path or not globs:
        return False
    normalized = os.path.normpath(path)
    basename = normalized.rsplit("/", 1)[-1]
    return any(_glob_hits(normalized, basename, g) for g in globs)


def _glob_hits(path, basename, glob):
    if "/" in glob:
        return fnmatch.fnmatch(path, glob) or fnmatch.fnmatch(path, "*/" + glob)
    return fnmatch.fnmatch(basename, glob) or fnmatch.fnmatch(path, glob)


def _content_matches(obj, regexes):
    if not regexes:
        return False
    haystack = _haystack(obj)
    return any(r.search(haystack) for r in regexes)


_FIELDS = ("command", "searchable_text", "body", "outcome")


def _haystack(obj):
    return "\n".join(obj.get(f) or "" for f in _FIELDS if obj.get(f))
