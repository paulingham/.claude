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


def format_ac_line(ac_id: str, form: str, text: str, citation: str) -> str:
    """Render: '- [ ] {ac_id} (form: {form}): {text} [grounded: {citation}]'."""
    return f"- [ ] {ac_id} (form: {form}): {text} [grounded: {citation}]"
