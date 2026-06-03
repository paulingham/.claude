"""EARS form classification and AC-line formatting."""
import re

EARS_TYPES = frozenset({
    "ears-ubiquitous",
    "ears-event",
    "ears-state",
    "ears-unwanted",
    "ears-optional",
    "prose",
})

# Pattern order is significant: most specific first.
_PATTERNS = [
    ("ears-event",      re.compile(r"\bWHEN\b.+\bSHALL\b",  re.IGNORECASE)),
    ("ears-state",      re.compile(r"\bWHILE\b.+\bSHALL\b", re.IGNORECASE)),
    ("ears-unwanted",   re.compile(r"\bIF\b.+\bTHEN\b",      re.IGNORECASE)),
    ("ears-optional",   re.compile(r"\bWHERE\b.+\bSHALL\b", re.IGNORECASE)),
    ("ears-ubiquitous", re.compile(r"\bSHALL\b",             re.IGNORECASE)),
]


def classify_form(ac_text: str) -> str:
    """Return the EARS form tag for ac_text. Never raises; defaults to 'prose'."""
    for form, pattern in _PATTERNS:
        if pattern.search(ac_text):
            return form
    return "prose"


_MAX_AC_TEXT = 2000  # chars; caps both text and citation to prevent prompt injection


def _sanitize(raw: str) -> str:
    """Strip injection vectors from a user-supplied string.

    Removes CR, collapses newlines to a space, strips leading/embedded YAML
    front-matter fences (---) and markdown headings (##...), and caps at
    _MAX_AC_TEXT chars.
    """
    safe = raw.replace("\r", "").replace("\n", " ")
    # Collapse any segment that looks like a YAML front-matter fence
    safe = re.sub(r"(?<!\S)---(?!\S)", " ", safe)
    # Strip markdown heading markers (e.g. "## Heading" → "Heading")
    safe = re.sub(r"#{1,6}\s+", "", safe)
    return safe[:_MAX_AC_TEXT]


def format_ac_line(ac_id: str, form: str, text: str, citation: str) -> str:
    """Render: '- [ ] {ac_id} (form: {form}): {text} [grounded: {citation}]'.

    text and citation are sanitized: newlines collapsed, --- fences stripped,
    and capped at _MAX_AC_TEXT chars to prevent front-matter/prompt injection.
    """
    safe_text = _sanitize(text)
    safe_citation = _sanitize(citation)
    return f"- [ ] {ac_id} (form: {form}): {safe_text} [grounded: {safe_citation}]"
