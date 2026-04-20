"""S9: settings.json injection for embedder bootstrap.

Writes ORT_DYLIB_PATH via settings_patch (atomic, byte-preserving).
Honors CLAUDE_SETTINGS_PATH override for testability.
"""
import os
from pathlib import Path

from embedder._lib import settings_patch


def apply(dylib):
    if not dylib.exists():
        return 0
    return _try_patch(dylib)


def _try_patch(dylib):
    try:
        settings_patch.patch(
            settings_path(), "ORT_DYLIB_PATH", str(dylib))
        return 0
    except settings_patch.SettingsPatchError as exc:
        print(f"WARN: settings patch failed: {exc}")
        return 1


def settings_path():
    override = os.environ.get("CLAUDE_SETTINGS_PATH")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "settings.json"
