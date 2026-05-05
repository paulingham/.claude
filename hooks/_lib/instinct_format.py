"""Markdown formatter for resolved instincts (Wave 4-M Slice 1).

C8 extension: instincts whose `category` is `"anti-pattern"` are prefixed
with `AVOID: `. The prefix is added AFTER `_truncate` runs, so it sits
OUTSIDE the 200-char truncation budget — anti-pattern bullets may be up
to about 210 visible characters.
"""

HEADER = "## Learned Patterns (from system learning — apply these proactively)"


def _truncate(body):
    return (body[:200] + "...") if len(body) > 200 else body


def _summary_with_avoid(instinct):
    body = _truncate(instinct["pattern_summary"])
    return f"AVOID: {body}" if instinct.get("category") == "anti-pattern" else body


def _bullet(i):
    return f"- [{i['confidence']:.2f}] {_summary_with_avoid(i)} ({i['domain']})"


def render(instincts):
    return "\n".join([HEADER, *(_bullet(i) for i in instincts)])
