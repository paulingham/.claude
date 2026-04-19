"""Load privacy allowlist JSON — user file overrides default."""
import json
import re
import sys
from collections import namedtuple

from capture._lib import _allowlist_cache as _cache

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
    try:
        return _parse(path)
    except Exception as exc:  # noqa: BLE001 — fail-safe posture (AC7)
        sys.stderr.write(f"allowlist: failed to parse {path}: {exc}\n")
        return _EMPTY


def _parse(path):
    data = json.loads(path.read_text())
    globs = tuple(data.get("file_globs") or ())
    regexes = tuple(re.compile(r) for r in (data.get("content_regexes") or ()))
    return Allowlist(file_globs=globs, content_regexes=regexes)
