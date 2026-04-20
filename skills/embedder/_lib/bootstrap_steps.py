"""S9: bootstrap step handlers — brew install, model download, settings patch.

Each step returns 0 on success, non-zero on partial. Never raises.
"""
import os
import shutil
import subprocess

from embedder._lib import bootstrap_paths


def install_ort():
    if shutil.which("brew") is None:
        _warn("brew not on PATH — skipping onnxruntime install")
        return 1
    return _run_brew()


def download_model():
    env = dict(os.environ)
    env["NONINTERACTIVE"] = "1"
    return _run_timed(
        ["bash", str(bootstrap_paths.download_script())],
        "model download failed", timeout=600, env=env)


def _run_brew():
    return _run_timed(
        ["brew", "install", "onnxruntime"],
        "brew install failed", timeout=300)


def _run_timed(cmd, warn_msg, timeout, env=None):
    try:
        result = subprocess.run(cmd, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        _warn(f"{warn_msg} (timed out after {timeout}s)")
        return 1
    return _rc(result, warn_msg)


def _rc(result, warn_msg):
    if result.returncode != 0:
        _warn(warn_msg)
        return 1
    return 0


def _warn(msg):
    print(f"WARN: {msg}")
