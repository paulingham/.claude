"""Markdown heading-stack walker for AC18 enforcement.

Pure-Python (no external lib). Walks markdown line-by-line and yields
each non-heading line tagged with its current heading-stack — i.e. the
ordered list of `(level, text)` pairs from the document root down to
the most recent heading at-or-above the line.

Used to assert that a given finding line lives under the literal
`## Findings` heading and NOT under any case-insensitive
suppression/dismissal heading.
"""
import re

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def walk(markdown_text):
    """Yield (heading_stack, line_index, line) for every non-heading line.

    heading_stack is a tuple of (level, text) pairs in document order.
    Each subsequent heading at level L pops the stack until the top is
    strictly shallower (level < L), then pushes the new heading.
    """
    stack = []
    for index, line in enumerate(markdown_text.splitlines()):
        match = _HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            text = match.group(2)
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
            continue
        yield tuple(stack), index, line


def lines_under_heading(markdown_text, heading_text, level=2):
    """Return list of (line_index, line) under a heading matching exactly.

    Match is on (level, text) pair — the literal heading must appear at
    the given level. Returns lines until the next sibling-or-higher heading.
    """
    matches = []
    for stack, line_index, line in walk(markdown_text):
        if not stack:
            continue
        top_level, top_text = stack[-1]
        if top_level == level and top_text == heading_text:
            matches.append((line_index, line))
    return matches


def lines_under_any_heading_matching(markdown_text, heading_pattern):
    """Return [(line_index, line)] where ANY heading in the stack matches the regex.

    `heading_pattern` is a compiled re pattern, matched against the heading
    text (not the leading hashes).
    """
    matches = []
    for stack, line_index, line in walk(markdown_text):
        for _level, text in stack:
            if heading_pattern.search(text):
                matches.append((line_index, line))
                break
    return matches
