"""Model allowlist check — gates agent frontmatter against a hard-coded allowlist.

Public API:
- ``check(repo_root: pathlib.Path) -> list[str]`` — returns error tokens
  ``f"unknown-model: {path}:{line}"`` for every offending entry. Empty list = pass.

Allowlist source: ``_ALLOWED`` frozenset at module top — hard-coded, code-reviewed.

Invoked by ``skills/harness-audit/SKILL.md`` (model-allowlist check, slice-a). Pure stdlib.
"""
from __future__ import annotations

import pathlib
import re

# Hard-coded allowlist — the only model strings that may appear in agent frontmatter.
# Update requires a code-review and PR. Keep alphabetised within each tier.
_ALLOWED: frozenset[str] = frozenset({
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "claude-haiku-4-5-20251001",
    "opus",     # alias resolved by orchestrator
    "sonnet",   # alias resolved by orchestrator
    "haiku",    # alias resolved by orchestrator
    "none",     # advisor: none sentinel (single-arm config)
})

# Matches `model:`, `executor:`, `advisor:` keys with a model string value.
_MODEL_KEY = re.compile(r"^\s*(?:model|executor|advisor):\s*([A-Za-z0-9._\-]+)\s*$")


def _frontmatter_lines(path: pathlib.Path) -> list[tuple[int, str]]:
    """Return (1-indexed-lineno, line) pairs from the YAML frontmatter block."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if not text.startswith("---\n"):
        return []
    end = text.find("\n---\n", 4)
    if end == -1:
        return []
    block = text[4:end]
    return [(i + 2, line) for i, line in enumerate(block.splitlines())]


def _check_one(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    for lineno, line in _frontmatter_lines(path):
        match = _MODEL_KEY.match(line)
        if not match:
            continue
        if match.group(1) not in _ALLOWED:
            errors.append(f"unknown-model: {path}:{lineno}")
    return errors


def check(repo_root: pathlib.Path) -> list[str]:
    """Validate every agent frontmatter ``model:``/``executor:``/``advisor:`` field."""
    agents_dir = repo_root / "agents"
    if not agents_dir.is_dir():
        return [f"missing-agents-dir: {repo_root}"]
    errors: list[str] = []
    for path in sorted(agents_dir.glob("*.md")):
        errors.extend(_check_one(path))
    return errors


if __name__ == "__main__":
    import sys
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path.cwd()
    for token in check(root):
        print(token)
