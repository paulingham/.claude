"""S9: embedder bootstrap for zero-config macOS install. Graceful fallback."""
import platform
import sys

from embedder._lib import (
    bootstrap_paths, bootstrap_settings, bootstrap_steps, doctor_probe)

SKIP_NON_MACOS = 10
PARTIAL = 20


def run():
    if platform.system() != "Darwin":
        return _skip()
    return 0 if _is_healthy() else _bootstrap()


def _skip():
    print("embedder bootstrap skipped (non-macOS)")
    return SKIP_NON_MACOS


def _bootstrap():
    rc = _ensure(_dylib_path(), bootstrap_steps.install_ort)
    rc |= _ensure(_model_path(), bootstrap_steps.download_model)
    rc |= bootstrap_settings.apply(_dylib_path())
    return PARTIAL if rc else 0


def _ensure(path, step):
    return 0 if path.exists() else step()


def _is_healthy():
    return doctor_probe.probe_facade()[0]


def _dylib_path():
    return bootstrap_paths.dylib_path()


def _model_path():
    return bootstrap_paths.model_path()


if __name__ == "__main__":
    sys.exit(run())
