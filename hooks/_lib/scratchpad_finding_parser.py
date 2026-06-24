"""Parse a scratchpad finding file into a typed dict."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TypedDict

from scratchpad_frontmatter import extract_category, split_frontmatter

# Cap reads at 1MB. Scratchpad findings are short prose; a multi-MB file is
# either malformed or hostile. Without this cap, a 1GB scratchpad file OOMs
# the planning-agent's poll loop.
MAX_BYTES = 1_048_576


class Finding(TypedDict):
    path: str
    filename: str
    content_hash: str
    category: str
    body: str


def parse_finding(path: Path) -> Finding | None:
    """Parse a scratchpad .md file. Returns None if unparseable."""
    with path.open("rb") as fh:
        raw = fh.read(MAX_BYTES)
    parts = split_frontmatter(raw.decode("utf-8", errors="replace"))
    if parts is None:
        return None
    category = extract_category(parts[0])
    if category is None:
        return None
    return _build_finding(path, raw, category, parts[1])


def _build_finding(path: Path, raw: bytes, category: str, body: str) -> Finding:
    return Finding(
        path=str(path), filename=path.name,
        content_hash=content_hash(raw),
        category=category, body=body,
    )


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]
