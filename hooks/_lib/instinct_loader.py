"""Disk-aware loader for instinct files (Wave 4-M, Slice 2).

Reads `{base}/{project_hash}/instincts/*.md` (project, scope="project") AND
`{base}/instincts/*.md` (global, scope="global"). Tolerates malformed files;
never raises. Per-file failures emit a JSONL warning via log-injection.sh.
Uses yaml.safe_load — MUST NOT import pipeline_frontmatter (lists corrupt).
"""
import os
from pathlib import Path

from instinct_loader_helpers import (
    parse_file, validate, normalize, log_warning,
)


def _base_dir(override):
    env = os.environ.get("CLAUDE_INSTINCTS_DIR")
    return Path(override or env or Path.home() / ".claude" / "learning")


def _try_load(path, scope):
    try:
        fm, body = parse_file(path)
    except Exception:
        log_warning(path, "malformed-yaml")
        return None
    reason = validate(fm, body)
    if reason:
        log_warning(path, reason)
        return None
    return normalize(fm, body, scope)


def _load_dir(directory, scope):
    if not directory.is_dir():
        return []
    loaded = (_try_load(p, scope) for p in sorted(directory.glob("*.md")))
    return [d for d in loaded if d is not None]


def _dedup(items):
    by_id = {}
    [by_id.setdefault(i["id"], i) for i in items]
    return list(by_id.values())


def load_instincts(project_hash, instincts_base=None):
    base = _base_dir(instincts_base)
    return _dedup(_load_dir(base / project_hash / "instincts", "project")
                  + _load_dir(base / "instincts", "global"))
