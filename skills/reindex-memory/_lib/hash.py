"""Content-addressable hashing for observations and findings."""
import hashlib


def content_hash(session_id, timestamp, tool, file):
    """sha256 over pipe-delimited dedup key. Matches schema.sql spec."""
    key = f"{session_id or ''}|{timestamp or ''}|{tool or ''}|{file or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def searchable_text(tool, file, outcome):
    """Concatenate non-empty fields into the FTS5-indexed blob."""
    parts = [p for p in (tool, file, outcome) if p]
    return " ".join(parts)
