"""Tests for hooks/_lib/harness_paths.py and migrated callers.

Slice a1-python-resolver ACs: AC-A1a, AC-A1b, AC-A1f.
"""
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_HOOKS_LIB = str(_REPO_ROOT / "hooks" / "_lib")
if _HOOKS_LIB not in sys.path:
    sys.path.insert(0, _HOOKS_LIB)


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC-A1a: harness_paths.py — three-tier resolver
# ---------------------------------------------------------------------------

class TestHarnessDataResolution:
    """harness_data() returns correct path based on env vars."""

    def test_harness_data_returns_plugin_data_when_set(self, tmp_path):
        plugin_data = str(tmp_path / "plugin-data")
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": plugin_data}, clear=False):
            import harness_paths
            importlib.reload(harness_paths)
            assert harness_paths.harness_data() == Path(plugin_data)

    def test_harness_data_falls_back_to_config_dir(self, tmp_path):
        config_dir = str(tmp_path / "config-dir")
        env = {"CLAUDE_CONFIG_DIR": config_dir}
        env_cleared = {k: v for k, v in os.environ.items()
                       if k != "CLAUDE_PLUGIN_DATA" and k != "CLAUDE_CONFIG_DIR"}
        env_cleared.update(env)
        with patch.dict(os.environ, env_cleared, clear=True):
            import harness_paths
            importlib.reload(harness_paths)
            assert harness_paths.harness_data() == Path(config_dir)

    def test_harness_data_falls_back_to_home_claude(self):
        env_stripped = {k: v for k, v in os.environ.items()
                        if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_CONFIG_DIR")}
        with patch.dict(os.environ, env_stripped, clear=True):
            import harness_paths
            importlib.reload(harness_paths)
            assert harness_paths.harness_data() == Path.home() / ".claude"

    def test_harness_root_returns_plugin_root_when_set(self, tmp_path):
        plugin_root = str(tmp_path / "plugin-root")
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": plugin_root}, clear=False):
            import harness_paths
            importlib.reload(harness_paths)
            assert harness_paths.harness_root() == Path(plugin_root)


# ---------------------------------------------------------------------------
# AC-A1b: callers use harness_data() / harness_root()
# ---------------------------------------------------------------------------

class TestInstinctLoaderUsesHarnessPaths:
    """instinct_loader._base_dir(None) returns harness_data()/'learning'."""

    def test_instinct_loader_uses_harness_paths(self, tmp_path):
        plugin_data = str(tmp_path / "plugin-data")
        env = {k: v for k, v in os.environ.items()
               if k != "CLAUDE_INSTINCTS_DIR" and k != "CLAUDE_PLUGIN_DATA"}
        env["CLAUDE_PLUGIN_DATA"] = plugin_data
        with patch.dict(os.environ, env, clear=True):
            import instinct_loader
            importlib.reload(instinct_loader)
            result = instinct_loader._base_dir(None)
            assert result == Path(plugin_data) / "learning"


class TestPipelineStateFallback:
    """pipeline_state._state_dir(None) uses CLAUDE_PIPELINE_STATE_DIR as tier 1."""

    def test_pipeline_state_harness_data_is_fallback_not_tier1(self, tmp_path):
        plugin_data = str(tmp_path / "plugin-data")
        pipeline_state_dir = str(tmp_path / "pipeline-state-explicit")
        # Tier 1: CLAUDE_PIPELINE_STATE_DIR wins
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_PIPELINE_STATE_DIR", "CLAUDE_PLUGIN_DATA")}
        env["CLAUDE_PIPELINE_STATE_DIR"] = pipeline_state_dir
        env["CLAUDE_PLUGIN_DATA"] = plugin_data
        with patch.dict(os.environ, env, clear=True):
            import pipeline_state
            importlib.reload(pipeline_state)
            result = pipeline_state._state_dir(None)
            # CLAUDE_PIPELINE_STATE_DIR must win over CLAUDE_PLUGIN_DATA
            assert result == pipeline_state_dir

        # When CLAUDE_PIPELINE_STATE_DIR unset, harness_data() provides fallback
        env2 = {k: v for k, v in os.environ.items()
                if k not in ("CLAUDE_PIPELINE_STATE_DIR", "CLAUDE_PLUGIN_DATA")}
        env2["CLAUDE_PLUGIN_DATA"] = plugin_data
        with patch.dict(os.environ, env2, clear=True):
            importlib.reload(pipeline_state)
            result2 = pipeline_state._state_dir(None)
            assert result2 == str(Path(plugin_data) / "pipeline-state")


# ---------------------------------------------------------------------------
# AC-A1f: agent_frontmatter_io uses CLAUDE_AGENTS_DIR as tier 1;
#          harness_root()/"agents" as cold-start fallback
# ---------------------------------------------------------------------------

class TestAgentFrontmatterIoUsesHarnessRoot:
    """agents_dir() returns harness_root()/"agents" when CLAUDE_AGENTS_DIR unset."""

    def test_agent_frontmatter_io_uses_harness_root_agents_fallback(self, tmp_path):
        plugin_root = str(tmp_path / "plugin-root")
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_AGENTS_DIR", "CLAUDE_PLUGIN_ROOT")}
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
        with patch.dict(os.environ, env, clear=True):
            import agent_frontmatter_io
            importlib.reload(agent_frontmatter_io)
            result = agent_frontmatter_io.agents_dir()
            assert result == Path(plugin_root) / "agents"

        # When CLAUDE_PLUGIN_ROOT also unset, fallback is Path.home()/".claude"/"agents"
        env2 = {k: v for k, v in os.environ.items()
                if k not in ("CLAUDE_AGENTS_DIR", "CLAUDE_PLUGIN_ROOT",
                              "CLAUDE_CONFIG_DIR")}
        with patch.dict(os.environ, env2, clear=True):
            importlib.reload(agent_frontmatter_io)
            result2 = agent_frontmatter_io.agents_dir()
            assert result2 == Path.home() / ".claude" / "agents"


class TestAgentToolsLoaderRetainsPrecedence:
    """CLAUDE_AGENTS_DIR env var takes precedence over harness_root()."""

    def test_agent_tools_loader_retains_claude_agents_dir_precedence(self, tmp_path):
        agents_dir = str(tmp_path / "agents-explicit")
        plugin_root = str(tmp_path / "plugin-root")
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_AGENTS_DIR", "CLAUDE_PLUGIN_ROOT")}
        env["CLAUDE_AGENTS_DIR"] = agents_dir
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
        with patch.dict(os.environ, env, clear=True):
            import agent_tools_loader
            importlib.reload(agent_tools_loader)
            result = agent_tools_loader._agents_dir()
            # CLAUDE_AGENTS_DIR must win over harness_root()
            assert result == Path(agents_dir)
