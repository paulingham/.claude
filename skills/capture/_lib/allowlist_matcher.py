"""Detect whether an observation matches the privacy allowlist."""
import fnmatch


def is_private(obj, allow):
    if _file_matches(obj.get("file"), allow.file_globs):
        return True
    return _content_matches(obj, allow.content_regexes)


def _file_matches(path, globs):
    if not path or not globs:
        return False
    basename = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(basename, g) or fnmatch.fnmatch(path, g)
               or path.endswith("/" + g) for g in globs)


def _content_matches(obj, regexes):
    if not regexes:
        return False
    haystack = _haystack(obj)
    return any(r.search(haystack) for r in regexes)


_FIELDS = ("command", "searchable_text", "body", "outcome")


def _haystack(obj):
    return "\n".join(obj.get(f) or "" for f in _FIELDS if obj.get(f))
