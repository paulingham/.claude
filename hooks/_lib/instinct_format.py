"""Markdown formatter for resolved instincts (Wave 4-M Slice 1)."""

HEADER = "## Learned Patterns (from system learning — apply these proactively)"


def _truncate(body):
    return (body[:200] + "...") if len(body) > 200 else body


def _bullet(i):
    return f"- [{i['confidence']:.2f}] {_truncate(i['pattern_summary'])} ({i['domain']})"


def render(instincts):
    return "\n".join([HEADER, *(_bullet(i) for i in instincts)])
