"""Default paths. Keeps reindex.py free of path literals."""
import sys
from pathlib import Path

# Ensure the sibling harness_paths module is importable regardless of
# how this file was loaded (direct sys.path vs. cross-skill import chain).
_LIB_DIR = str(Path(__file__).parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from harness_paths import harness_data  # noqa: E402


def default_db():
    return harness_data() / "db" / "memory.sqlite"


def default_learning():
    return harness_data() / "learning"
