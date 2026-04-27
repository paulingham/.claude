"""Parse a scratchpad finding file into a typed dict."""
import hashlib
from pathlib import Path
from typing import TypedDict

from scratchpad_frontmatter import extract_category, split_frontmatter


class Finding(TypedDict):
    path: str
    filename: str
    content_hash: str
    category: str
    body: str


def parse_finding(path: Path) -> Finding | None:
    """Parse a scratchpad .md file. Returns None if unparseable."""
    raw = path.read_bytes()
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
