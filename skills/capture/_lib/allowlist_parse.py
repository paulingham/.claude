"""Parse allowlist JSON — size-capped, fail-safe per-entry."""
import json
import re
import sys

_MAX_BYTES = 1024 * 1024  # 1 MiB cap — DoS guard on capture hot path


def safe_parse(path, build):
    if _oversize(path):
        return _warn_empty(path, f"file exceeds {_MAX_BYTES}-byte cap", build)
    try:
        return _parse(path, build)
    except Exception as exc:  # noqa: BLE001 — fail-safe posture (AC7)
        return _warn_empty(path, exc, build)


def _oversize(path):
    return path.stat().st_size > _MAX_BYTES


def _warn_empty(path, reason, build):
    sys.stderr.write(f"allowlist: failed to parse {path}: {reason}\n")
    return build(globs=(), regexes=())


def _parse(path, build):
    data = json.loads(path.read_text())
    globs = tuple(data.get("file_globs") or ())
    regexes = _compile_each(data.get("content_regexes") or (), path)
    return build(globs=globs, regexes=regexes)


def _compile_each(patterns, path):
    return tuple(c for c in (_compile_one(p, path) for p in patterns) if c)


def _compile_one(pattern, path):
    try:
        return re.compile(pattern)
    except re.error as exc:
        sys.stderr.write(
            f"allowlist: skipped invalid regex {pattern!r} in {path}: {exc}\n")
        return None
