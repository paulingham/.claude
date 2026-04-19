"""Load privacy allowlist JSON — user file overrides default."""
from collections import namedtuple

from capture._lib import _allowlist_cache as _cache
from capture._lib import allowlist_parse as _parse

Allowlist = namedtuple("Allowlist", ["file_globs", "content_regexes"])
_EMPTY = Allowlist(file_globs=(), content_regexes=())


def load(user_path=None, default_path=None):
    path = _pick(user_path, default_path)
    if path is None:
        return _EMPTY
    return _cache.get_or_fill(path, _safe_parse)


def _pick(user, default):
    if user is not None and user.exists():
        return user
    if default is not None and default.exists():
        return default
    return None


def _safe_parse(path):
    return _parse.safe_parse(path, _build)


def _build(globs, regexes):
    return Allowlist(file_globs=globs, content_regexes=regexes)
