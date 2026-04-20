"""S9 AC6: atomic JSON patcher for settings.json env keys.

patch(path, key, value) reads JSON, sets env[key] only if absent, and
writes atomically via mkstemp + os.replace mirroring status._atomic_write.
Invalid JSON surfaces SettingsPatchError.
"""
import json
import os
import tempfile


class SettingsPatchError(RuntimeError):
    """Raised on JSON parse failure or write failure."""


def patch(path, key, value):
    payload = _read(path)
    env = payload.setdefault("env", {})
    if key in env:
        return
    env[key] = value
    _write(path, payload)


def _read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsPatchError(f"cannot read {path}: {exc}") from exc


def _write(path, payload):
    body = json.dumps(payload, indent=2, sort_keys=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".json")
    with os.fdopen(fd, "w") as fh:
        fh.write(body)
    os.replace(tmp, path)
