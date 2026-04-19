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


def _haystack(obj):
    parts = (obj.get("command"), obj.get("searchable_text"), obj.get("body"))
    return "\n".join(p for p in parts if p)
