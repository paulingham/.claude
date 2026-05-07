"""Role × sub-file mapping for session memory injection (AC15 source of truth).

Encodes the table from `pipeline-state/wave2a-c3-session-memory-split/plan.md`
§ 4.2. Active-work.md is NEVER included in any role's sub-file list — it is
orchestrator-only state, written via session_store_put directly.

Public API:
    CANONICAL_SUBFILES: tuple[str, ...]    # all five sub-file basenames
    resolve_subfiles_for_role(role: str) -> list[str]
    body_chars(text: str) -> int
    should_inject_subfile(text: str) -> bool
"""
import re

CANONICAL_SUBFILES = (
    "codebase-map",
    "build-test",
    "patterns",
    "fragility",
    "active-work",
)

# Role → sub-file injection list (active-work.md NEVER appears here).
_ROLE_TABLE = {
    "architect":               ["codebase-map", "patterns", "fragility"],
    "software-engineer":       ["build-test", "patterns", "fragility"],
    "frontend-engineer":       ["build-test", "patterns", "fragility"],
    "database-engineer":       ["build-test", "patterns", "fragility"],
    "infrastructure-engineer": ["build-test", "fragility"],
    "qa-engineer":             ["build-test", "fragility"],
    "code-reviewer":           ["patterns", "fragility"],
    "security-engineer":       ["patterns", "fragility"],
    "product-reviewer":        [],
    "patch-critic":            ["fragility"],
    "session-memory-updater":  [],
}

EMPTY_BODY_CHAR_THRESHOLD = 50


def resolve_subfiles_for_role(role):
    """Return the ordered sub-file list for `role`. Unknown role → []."""
    return list(_ROLE_TABLE.get(role, []))


def body_chars(text):
    """Count body bytes after stripping headers, italic descriptions, blanks."""
    body = [
        line for line in text.splitlines()
        if not _is_header(line) and not _is_italic_description(line) and line.strip()
    ]
    return sum(len(line) for line in body)


def should_inject_subfile(text):
    """True iff body_chars(text) >= EMPTY_BODY_CHAR_THRESHOLD."""
    return body_chars(text) >= EMPTY_BODY_CHAR_THRESHOLD


def _is_header(line):
    return bool(re.match(r"^#\s", line))


def _is_italic_description(line):
    return bool(re.match(r"^_.+_\s*$", line))
