"""S9: settings.json injection for embedder bootstrap.

Writes ORT_DYLIB_PATH via settings_patch (atomic, byte-preserving).
Honors CLAUDE_SETTINGS_PATH override for testability.
"""
import os
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from harness_paths import harness_root  # noqa: E402

from embedder._lib import settings_patch


def apply(dylib):
    if not dylib.exists():
        return 0
    return _try_patch(dylib)


def _try_patch(dylib):
    try:
        wrote = settings_patch.patch(
            settings_path(), "ORT_DYLIB_PATH", str(dylib))
        return _announce(wrote)
    except settings_patch.SettingsPatchError as exc:
        print(f"WARN: settings patch failed: {exc}")
        return 1


def _announce(wrote):
    if wrote:
        print("embedder bootstrap complete (ORT_DYLIB_PATH written)")
    return 0


def settings_path():
    override = os.environ.get("CLAUDE_SETTINGS_PATH")
    if override:
        return Path(override)
    return harness_root() / "settings.json"
