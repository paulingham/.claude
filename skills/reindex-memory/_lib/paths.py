"""Default paths. Keeps reindex.py free of path literals."""
from pathlib import Path

CLAUDE_HOME = Path.home() / ".claude"


def default_db():
    return CLAUDE_HOME / "db" / "memory.sqlite"


def default_learning():
    return CLAUDE_HOME / "learning"
