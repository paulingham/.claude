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
    result = subprocess.run(
        ["bash", str(bootstrap_paths.download_script())],
        env=env, timeout=600)
    return _rc(result, "model download failed")


def _run_brew():
    result = subprocess.run(
        ["brew", "install", "onnxruntime"], timeout=300)
    return _rc(result, "brew install failed")


def _rc(result, warn_msg):
    if result.returncode != 0:
        _warn(warn_msg)
        return 1
    return 0


def _warn(msg):
    print(f"WARN: {msg}")
