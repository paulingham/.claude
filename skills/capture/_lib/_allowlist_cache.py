"""mtime-keyed memoization for allowlist_loader.

Keeps capture hook hot path free of JSON parsing on repeated calls with
unchanged user/default files."""
import os

_CACHE = {}


def get_or_fill(path, parse):
    key, mtime = str(path), os.stat(path).st_mtime
    hit = _CACHE.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    return _fill(key, mtime, path, parse)


def _fill(key, mtime, path, parse):
    allow = parse(path)
    _CACHE[key] = (mtime, allow)
    return allow
