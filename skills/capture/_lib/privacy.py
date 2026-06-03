"""Privacy facade: sanitize <private> tags + apply allowlist in one pass."""
from pathlib import Path

from capture._lib import allowlist_loader, allowlist_matcher, sanitizer
from capture._lib.harness_paths import harness_data

_TEXT_FIELDS = ("command", "searchable_text", "body", "outcome", "file")
_user_path = harness_data() / "privacy-allowlist.json"
_default_path = (Path(__file__).resolve().parents[1]
                 / "privacy-allowlist.default.json")


def apply(obj):
    sanitized = _sanitize_fields(obj)
    allow = allowlist_loader.load(_user_path, _default_path)
    sanitized["is_private"] = 1 if allowlist_matcher.is_private(
        sanitized, allow) else 0
    return sanitized


def _sanitize_fields(obj):
    out = dict(obj)
    for field in _TEXT_FIELDS:
        if field in out and isinstance(out[field], str):
            out[field] = sanitizer.sanitize(out[field])
    return out
