"""Frontmatter parsing + state field coercion for pipeline state files."""
import re

_TRUE = {"true", "yes", "1"}


def _kv(line):
    key, _, value = line.partition(":")
    return key.strip(), value.strip()


def parse_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return dict(_kv(line) for line in match.group(1).splitlines() if ":" in line) if match else {}


def _safe_int(raw):
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def coerce_state(fields, debug_active, debug_mtime=None):
    return {
        "task_id": fields.get("task_id", ""),
        "phase": fields.get("phase", ""),
        "task_class": fields.get("task_class", ""),
        "critical": fields.get("critical", "").lower() in _TRUE,
        "bestofn": fields.get("bestofn", "").lower() in _TRUE,
        "budget": _safe_int(fields.get("budget", "0")),
        "debug_active": debug_active or fields.get("phase", "") == "debugging",
        "debug_mtime": debug_mtime,
    }
