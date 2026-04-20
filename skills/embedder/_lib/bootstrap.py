"""S9: embedder bootstrap for zero-config macOS install.

run() is platform-gated, graceful-fallback, never raises. Returns 0 on
healthy/bootstrapped, non-zero skip/partial codes otherwise.
"""
import platform
import shutil
import subprocess

from embedder._lib import (
    bootstrap_paths, bootstrap_steps, doctor_probe, settings_patch)

SKIP_NON_MACOS = 10
PARTIAL = 20


def run():
    if platform.system() != "Darwin":
        return _skip_non_macos()
    if _is_healthy():
        return 0
    return _bootstrap()


def _bootstrap():
    rc = 0
    if not _dylib_path().exists():
        rc |= bootstrap_steps.install_ort()
    if not _model_path().exists():
        rc |= bootstrap_steps.download_model()
    return PARTIAL if rc else 0


def _skip_non_macos():
    print("embedder bootstrap skipped (non-macOS)")
    return SKIP_NON_MACOS


def _is_healthy():
    ok, _ = doctor_probe.probe_facade()
    return ok


def _dylib_path():
    return bootstrap_paths.dylib_path()


def _model_path():
    return bootstrap_paths.model_path()
