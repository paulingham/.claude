"""Import-time bootstrap: expose capture.privacy to reindex writers."""
import sys
from pathlib import Path

_SKILLS = str(Path(__file__).resolve().parents[2])
if _SKILLS not in sys.path:
    sys.path.insert(0, _SKILLS)
from capture._lib import privacy  # noqa: E402

apply = privacy.apply
