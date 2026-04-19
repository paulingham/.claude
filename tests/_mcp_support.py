"""Shared sys.path bootstrap + stream helpers for MCP memory tests."""
import io
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_SKILLS = _TESTS.parent / "skills"
for _p in (str(_TESTS), str(_SKILLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def streams(text):
    return io.StringIO(text), io.StringIO()
