"""Frontmatter parser for advisor-mode reviewer agent files.

Mirrors `pipeline_frontmatter.parse_frontmatter` in shape: regex match the
`---\\n...\\n---` block, return a dict of `key: value` pairs. No I/O.
"""
import re

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _kv(line):
    key, _, value = line.partition(":")
    return key.strip(), value.strip()


def parse_frontmatter(text):
    match = _FRONTMATTER_RE.match(text)
    return dict(_kv(line) for line in match.group(1).splitlines() if ":" in line) if match else {}
