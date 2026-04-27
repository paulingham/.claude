"""Split YAML frontmatter from a markdown body.

Returns (frontmatter, body) when both delimiters are present, else None.
"""


def split_frontmatter(text: str) -> tuple[str, str] | None:
    """Split YAML frontmatter from body. Returns None if malformed."""
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return None
    rest = text.split("\n", 1)[1] if "\n" in text else ""
    if "\n---" not in rest:
        return None
    frontmatter, _, body = rest.partition("\n---")
    return frontmatter, body.lstrip("\r\n")


def extract_category(frontmatter: str) -> str | None:
    """Find a `category: <value>` line in YAML frontmatter."""
    for line in frontmatter.splitlines():
        value = _category_value(line)
        if value is not None:
            return value or None
    return None


def _category_value(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.lower().startswith("category:"):
        return None
    return stripped.split(":", 1)[1].strip().lower()
