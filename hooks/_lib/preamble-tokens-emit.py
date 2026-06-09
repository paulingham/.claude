#!/usr/bin/env python3
"""Estimate preamble token count for session_end cost record.

Sums ceil(utf8_bytes / 3.5) over shipped preamble sources:
  - CLAUDE.md
  - rules/core.md
  - learning/instincts/*.md

2am breadcrumb:
  - Shipped content lives under HARNESS_ROOT (CLAUDE_PLUGIN_ROOT > CLAUDE_CONFIG_DIR
    > ~/.claude), NOT HARNESS_DATA. Using harness_data() would silently return 0
    because runtime state dirs don't contain these files.
  - print(int) guarantees no leading-zero/empty output, which keeps --argjson
    from rejecting the value. Non-integer helper stdout would fail the entire jq
    block and the existing || true would silently drop the whole session_end record.
  - Fail-open: any error → print 0, exit 0. Never a control-flow gate.

Mirrors the fail-open shape of hooks/_lib/cost-jsonl-emit.py.
"""
import math
import os
import sys
from pathlib import Path


def _tokens_for_bytes(n: int) -> int:
    """Return ceil(n / 3.5) token estimate for n bytes."""
    return math.ceil(n / 3.5) if n > 0 else 0


def _sum_preamble_tokens(root: Path) -> int:
    """Sum ceil(utf8_bytes/3.5) over resolvable preamble sources under root."""
    total = 0
    sources = [
        root / "CLAUDE.md",
        root / "rules" / "core.md",
    ]
    instincts_dir = root / "learning" / "instincts"
    try:
        if instincts_dir.is_dir():
            sources.extend(sorted(instincts_dir.glob("*.md")))
    except OSError:
        pass

    for path in sources:
        try:
            data = path.read_bytes()
            total += _tokens_for_bytes(len(data))
        except OSError:
            pass
    return total


def main() -> None:
    """Print estimated preamble token count to stdout. Always exits 0."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import harness_paths
        root = harness_paths.harness_root()
        result = _sum_preamble_tokens(root)
    except Exception:
        result = 0
    print(result)


if __name__ == "__main__":
    main()
