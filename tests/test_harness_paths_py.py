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


class TestValidateBase:
    """SEC-H1: _validate_base raises ValueError for unsafe paths."""

    def test_non_absolute_raises(self):
        import harness_paths
        importlib.reload(harness_paths)
        with pytest.raises(ValueError, match="absolute"):
            harness_paths._validate_base(Path("relative/path"))

    def test_dotdot_component_raises(self):
        import harness_paths
        importlib.reload(harness_paths)
        with pytest.raises(ValueError, match=r"\.\.|absolute"):
            harness_paths._validate_base(Path("/tmp/../etc"))

    def test_double_quote_metachar_raises(self):
        import harness_paths
        importlib.reload(harness_paths)
        with pytest.raises(ValueError, match="metachar"):
            harness_paths._validate_base(Path('/tmp/a"b'))

    def test_dollar_metachar_raises(self):
        import harness_paths
        importlib.reload(harness_paths)
        with pytest.raises(ValueError, match="metachar"):
            harness_paths._validate_base(Path("/tmp/a$b"))

    def test_semicolon_metachar_raises(self):
        import harness_paths
        importlib.reload(harness_paths)
        with pytest.raises(ValueError, match="metachar"):
            harness_paths._validate_base(Path("/tmp/a;b"))

    def test_valid_absolute_passes(self, tmp_path):
        import harness_paths
        importlib.reload(harness_paths)
        result = harness_paths._validate_base(tmp_path)
        assert result == tmp_path

    def test_harness_data_with_metachar_env_raises(self, tmp_path):
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": '/tmp/a$b'}, clear=False):
            import harness_paths
            importlib.reload(harness_paths)
            with pytest.raises(ValueError, match="metachar"):
                harness_paths.harness_data()

    def test_harness_data_non_absolute_env_raises(self):
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": 'relative/path'}, clear=False):
            import harness_paths
            importlib.reload(harness_paths)
            with pytest.raises(ValueError, match="absolute"):
                harness_paths.harness_data()


class TestHarnessDataPrecedence:
    """MUT4/MUT5: verify PLUGIN_DATA > CONFIG_DIR and PLUGIN_ROOT > CONFIG_DIR."""

    def test_harness_data_plugin_data_wins_over_config_dir(self, tmp_path):
        """MUT4: CLAUDE_PLUGIN_DATA wins over CLAUDE_CONFIG_DIR."""
        plugin_data = str(tmp_path / "plugin-data")
        config_dir = str(tmp_path / "config-dir")
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_CONFIG_DIR")}
        env["CLAUDE_PLUGIN_DATA"] = plugin_data
        env["CLAUDE_CONFIG_DIR"] = config_dir
        with patch.dict(os.environ, env, clear=True):
            import harness_paths
            importlib.reload(harness_paths)
            result = harness_paths.harness_data()
        assert result == Path(plugin_data), (
            f"CLAUDE_PLUGIN_DATA must win over CLAUDE_CONFIG_DIR; got {result}"
        )

    def test_harness_root_plugin_root_wins_over_config_dir(self, tmp_path):
        """MUT5: CLAUDE_PLUGIN_ROOT wins over CLAUDE_CONFIG_DIR."""
        plugin_root = str(tmp_path / "plugin-root")
        config_dir = str(tmp_path / "config-dir")
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_CONFIG_DIR")}
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
        env["CLAUDE_CONFIG_DIR"] = config_dir
        with patch.dict(os.environ, env, clear=True):
            import harness_paths
            importlib.reload(harness_paths)
            result = harness_paths.harness_root()
        assert result == Path(plugin_root), (
            f"CLAUDE_PLUGIN_ROOT must win over CLAUDE_CONFIG_DIR; got {result}"
        )


class TestValidateBasePerMetachar:
    """MUT3: one rejection test per metachar in _SHELL_METACHARS (any→all kill)."""

    @pytest.mark.parametrize("char,label", [
        ('"',  "double-quote"),
        ('$',  "dollar"),
        ('`',  "backtick"),
        (';',  "semicolon"),
        ('\n', "newline"),
        ('|',  "pipe"),
        ('&',  "ampersand"),
        ('<',  "less-than"),
        ('>',  "greater-than"),
        ('(',  "open-paren"),
        (')',  "close-paren"),
    ])
    def test_single_metachar_rejected(self, char, label):
        """Each metachar in isolation must trigger ValueError."""
        import harness_paths
        importlib.reload(harness_paths)
        bad = Path(f"/tmp/test{char}bad")
        with pytest.raises(ValueError, match="metachar"):
            harness_paths._validate_base(bad)

    def test_path_with_space_passes(self):
        """Space is NOT a shell metachar for Path objects — must pass validation."""
        import harness_paths
        importlib.reload(harness_paths)
        p = Path("/tmp/path with space")
        result = harness_paths._validate_base(p)
        assert result == p

    def test_pipe_in_env_raises(self):
        """T3.5-M5: CLAUDE_PLUGIN_DATA containing pipe must raise (MUT3 pipe kill)."""
        with patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": "/tmp/test|bad"}, clear=False):
            import harness_paths
            importlib.reload(harness_paths)
            with pytest.raises(ValueError, match="metachar"):
                harness_paths.harness_data()

    def test_home_with_space_cold_start(self, tmp_path):
        """HOME containing a space: cold-start fallback must not raise."""
        spaced = tmp_path / "home with space"
        spaced.mkdir()
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_CONFIG_DIR", "HOME")}
        env["HOME"] = str(spaced)
        with patch.dict(os.environ, env, clear=True):
            import harness_paths
            importlib.reload(harness_paths)
            # Path.home() reads HOME; cold-start returns HOME/.claude which contains space
            result = harness_paths.harness_data()
            assert result == spaced / ".claude"


class TestInjectionScanFailClosed:
    """SEC-H2: injection-scan.sh exits 1 when HARNESS_DATA is empty.

    harness-paths.sh (sourced via log.sh) always exports a non-empty HARNESS_DATA
    using the $HOME/.claude fallback, so HARNESS_DATA is only empty when it is
    explicitly cleared after sourcing (adversarial env mutation). The guard prevents
    an empty prefix in the case match from matching every file path.
    """

    def test_injection_scan_fails_when_harness_data_empty(self, tmp_path):
        import json
        import subprocess
        hook = _REPO_ROOT / "hooks" / "injection-scan.sh"
        target = tmp_path / "file.txt"
        target.write_text("safe content")
        payload = {"tool_name": "Write",
                   "tool_input": {"file_path": str(target)}}
        env = {k: v for k, v in os.environ.items()}
        env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
        env["CLAUDE_PLUGIN_DATA"] = str(tmp_path)
        # Set source-guard so harness-paths.sh does NOT re-run and reset HARNESS_DATA.
        # This simulates HARNESS_DATA being cleared after the initial source
        # (adversarial env mutation that the [ -n "$HARNESS_DATA" ] guard catches).
        env["_HARNESS_PATHS_LOADED"] = "1"
        env["HARNESS_DATA"] = ""
        result = subprocess.run(
            ["bash", str(hook)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=10, env=env,
        )
        assert result.returncode == 1, (
            f"injection-scan must exit 1 when HARNESS_DATA is empty; "
            f"rc={result.returncode}, stderr={result.stderr!r}"
        )
        assert "HARNESS_DATA unset" in result.stderr

    def test_injection_scan_normal_path_exits_zero(self, tmp_path):
        """Guard does not fire when HARNESS_DATA is properly set."""
        import json
        import subprocess
        hook = _REPO_ROOT / "hooks" / "injection-scan.sh"
        payload = {"tool_name": "Write",
                   "tool_input": {"file_path": str(tmp_path / "outside.txt")}}
        env = {k: v for k, v in os.environ.items()}
        env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
        env["CLAUDE_PLUGIN_DATA"] = str(tmp_path)
        env.pop("_HARNESS_PATHS_LOADED", None)
        env.pop("HARNESS_DATA", None)
        result = subprocess.run(
            ["bash", str(hook)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=10, env=env,
        )
        # File not under HARNESS_DATA/ → case falls through → exit 0
        assert result.returncode == 0


class TestResolvedHarnessData:
    """A-M1: resolved_harness_data() returns HARNESS_DATA env or harness_data() string."""

    def test_returns_harness_data_env_when_set(self, tmp_path):
        val = str(tmp_path / "override")
        with patch.dict(os.environ, {"HARNESS_DATA": val}, clear=False):
            import harness_paths
            importlib.reload(harness_paths)
            assert harness_paths.resolved_harness_data() == val

    def test_falls_back_to_harness_data_fn(self, tmp_path):
        plugin_data = str(tmp_path / "plugin-data")
        env = {k: v for k, v in os.environ.items()
               if k not in ("HARNESS_DATA", "CLAUDE_PLUGIN_DATA", "CLAUDE_CONFIG_DIR")}
        env["CLAUDE_PLUGIN_DATA"] = plugin_data
        with patch.dict(os.environ, env, clear=True):
            import harness_paths
            importlib.reload(harness_paths)
            assert harness_paths.resolved_harness_data() == plugin_data


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
