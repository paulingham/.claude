"""AC-A3a/e: sibling harness_paths modules exist and callers use harness_data/harness_root."""
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REINDEX_LIB = str(_REPO_ROOT / "skills" / "reindex-memory" / "_lib")
_EMBEDDER_LIB = str(_REPO_ROOT / "skills" / "embedder" / "_lib")


def _load_from(lib_dir, module_name, file_name=None):
    file_name = file_name or f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        module_name, str(Path(lib_dir) / file_name)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, lib_dir)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


class TestReindexSiblingModuleExists:
    """AC-A3a: sibling harness_paths.py importable from reindex _lib dir."""

    def test_reindex_sibling_harness_paths_module_exists(self):
        hp_path = _REPO_ROOT / "skills" / "reindex-memory" / "_lib" / "harness_paths.py"
        assert hp_path.exists(), f"Missing sibling: {hp_path}"
        mod = _load_from(_REINDEX_LIB, "harness_paths_reindex", "harness_paths.py")
        assert hasattr(mod, "harness_data")
        assert hasattr(mod, "harness_root")


class TestReindexPathsUsesHarnessData:
    """AC-A3a: default_db() and default_learning() use CLAUDE_PLUGIN_DATA."""

    def test_reindex_default_db_uses_claude_plugin_data(self, tmp_path):
        plugin_data = str(tmp_path / "plugin-data")
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_CONFIG_DIR")}
        env["CLAUDE_PLUGIN_DATA"] = plugin_data
        with patch.dict(os.environ, env, clear=True):
            sys.path.insert(0, _REINDEX_LIB)
            try:
                import paths as reindex_paths
                importlib.reload(reindex_paths)
                result = reindex_paths.default_db()
            finally:
                sys.path.pop(0)
        assert result == Path(plugin_data) / "db" / "memory.sqlite"

    def test_reindex_default_learning_uses_claude_plugin_data(self, tmp_path):
        plugin_data = str(tmp_path / "plugin-data")
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_CONFIG_DIR")}
        env["CLAUDE_PLUGIN_DATA"] = plugin_data
        with patch.dict(os.environ, env, clear=True):
            sys.path.insert(0, _REINDEX_LIB)
            try:
                import paths as reindex_paths
                importlib.reload(reindex_paths)
                result = reindex_paths.default_learning()
            finally:
                sys.path.pop(0)
        assert result == Path(plugin_data) / "learning"


class TestReindexOverlayEquivalence:
    """AC-A3e: when CLAUDE_PLUGIN_DATA unset, default_db() falls back to ~/.claude."""

    def test_reindex_default_db_falls_back_to_home_claude(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_CONFIG_DIR")}
        with patch.dict(os.environ, env, clear=True):
            sys.path.insert(0, _REINDEX_LIB)
            try:
                import paths as reindex_paths
                importlib.reload(reindex_paths)
                result = reindex_paths.default_db()
            finally:
                sys.path.pop(0)
        assert result == Path.home() / ".claude" / "db" / "memory.sqlite"
