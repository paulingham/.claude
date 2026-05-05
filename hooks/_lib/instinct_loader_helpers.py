"""Helpers for instinct_loader: parse, validate, normalize, log."""
import re

import yaml

from instinct_warning_log import log_warning  # noqa: F401 (re-export)

_FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_BODY = re.compile(r"^## Pattern[ \t]*\n(.*?)(?=\n##|\Z)",
                   re.MULTILINE | re.DOTALL)
_REQUIRED = ("id", "confidence", "roles")
_VALID_CATEGORIES = frozenset({
    "discovery", "warning", "pattern", "fragility", "decision", "anti-pattern",
})


def parse_file(path):
    match = _FM.match(path.read_text())
    fm = yaml.safe_load(match.group(1)) if match else None
    return (fm, match.group(2) if match else "")


def extract_summary(body):
    m = _BODY.search(body)
    text = (m.group(1).strip() if m else "")
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    return first[:200]


def validate(fm, body):
    if not isinstance(fm, dict):
        return "malformed-yaml"
    missing = next((k for k in _REQUIRED if k not in fm), None)
    if missing:
        return f"missing-{missing}-field"
    if "prefer_opus" in fm and not isinstance(fm["prefer_opus"], bool):
        return "non-bool-prefer-opus"
    if "category" in fm and fm["category"] not in _VALID_CATEGORIES:
        return "invalid-category"
    return None if extract_summary(body) else "missing-or-empty-pattern-body"


def normalize(fm, body, scope):
    raw = fm.get("prefer_opus", False)
    return {"id": fm["id"], "confidence": float(fm["confidence"]),
            "roles": list(fm["roles"]), "domain": fm.get("domain", ""),
            "scope": scope, "pattern_summary": extract_summary(body),
            "prefer_opus": raw if isinstance(raw, bool) else False,
            "category": fm.get("category", "")}


