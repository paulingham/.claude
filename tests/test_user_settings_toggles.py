"""Tests for developer-configurable toggles in user settings.json.

ACs:
  a. CLAUDE_PIPELINE_MODE present in user settings.json env (moved to user layer).
  b. CLAUDE_PIPELINE_MODE absent from managed-settings.json env.
  c. Each of the 9 toggles has a value AND a _doc_<name> sibling in user settings env.
  d. Behavior-preserving defaults: DISABLE_* = "0", VISIBLE_TEAMS = "0",
     ENABLE_TRACE = "0", PLAN_CACHE_MODE = "shadow", PIPELINE_MODE = "autonomous".
  e. Iron-Law gate vars absent from user settings env.
  f. README.md has ## Configuration section with always-on statement and no excluded keys.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
USER_SETTINGS = REPO_ROOT / "settings.json"
MANAGED_SETTINGS = REPO_ROOT / "managed-settings.json"
README = REPO_ROOT / "README.md"

NINE_TOGGLES = [
    "CLAUDE_PIPELINE_MODE",
    "CLAUDE_ENABLE_TRACE",
    "CLAUDE_DISABLE_SANDBOX_VERIFY",
    "CLAUDE_DISABLE_VLM_CRITIC",
    "CLAUDE_DISABLE_SWE_PRUNER",
    "CLAUDE_DISABLE_INSTINCT_INJECTION",
    "CLAUDE_DISABLE_WORKTREE_REAPER",
    "CLAUDE_VISIBLE_TEAMS",
    "CLAUDE_PLAN_CACHE_MODE",
]

IRON_LAW_GATES = [
    # Correctness-gate break-glass set — must NEVER be developer-documented.
    # Expand here when new undocumented escapes are added; keep both surfaces covered
    # (user settings env AND README Configuration section).
    "CLAUDE_DISABLE_QUALITY_GATE",
    "CLAUDE_DISABLE_TOOL_ALLOWLIST",
    "CLAUDE_INTAKE_BACKSTOP",
    "CLAUDE_DISABLE_FRESHNESS_GUARD",
    "CLAUDE_DISABLE_RUNTIME_STATE_GUARD",
]


def _load_user_env():
    data = json.loads(USER_SETTINGS.read_text())
    return data.get("env", {})


def _load_managed_env():
    data = json.loads(MANAGED_SETTINGS.read_text())
    return data.get("env", {})


def test_pipeline_mode_present_in_user_settings():
    """AC-a: CLAUDE_PIPELINE_MODE is present in user settings.json env."""
    env = _load_user_env()
    assert "CLAUDE_PIPELINE_MODE" in env, (
        "CLAUDE_PIPELINE_MODE must be present in user settings.json env "
        "(it moved from managed to user layer so developers can configure it)"
    )


def test_pipeline_mode_absent_from_managed_settings():
    """AC-b: CLAUDE_PIPELINE_MODE is absent from managed-settings.json env."""
    env = _load_managed_env()
    assert "CLAUDE_PIPELINE_MODE" not in env, (
        "CLAUDE_PIPELINE_MODE must NOT appear in managed-settings.json env "
        "(it moved to the user layer to be developer-configurable)"
    )


def test_enable_trace_absent_from_managed_settings():
    """AC-b mirror: CLAUDE_ENABLE_TRACE is absent from managed-settings.json env.

    Trace is a debug convenience, not a safety gate. Pinning it in managed silently
    overrides any user-layer setting (managed > user precedence). It must stay in the
    user layer only so developers can actually configure it.
    """
    env = _load_managed_env()
    assert "CLAUDE_ENABLE_TRACE" not in env, (
        "CLAUDE_ENABLE_TRACE must NOT appear in managed-settings.json env "
        "(it moved to the user layer — managed pin silently overrides user setting)"
    )


def test_all_nine_toggles_have_doc_siblings():
    """AC-c: Each of the 9 toggles is present AND has a _doc_<name> sibling in user settings env."""
    env = _load_user_env()
    missing_toggle = []
    missing_doc = []
    for key in NINE_TOGGLES:
        if key not in env:
            missing_toggle.append(key)
        doc_key = f"_doc_{key}"
        if doc_key not in env:
            missing_doc.append(doc_key)
    assert not missing_toggle, f"user settings env missing toggle keys: {missing_toggle}"
    assert not missing_doc, f"user settings env missing _doc_ siblings: {missing_doc}"


def test_behavior_preserving_defaults():
    """AC-d: Defaults preserve current behavior: DISABLE_*=0, VISIBLE_TEAMS=0,
    ENABLE_TRACE=0, PLAN_CACHE_MODE=shadow, PIPELINE_MODE=autonomous."""
    env = _load_user_env()
    disable_keys = [
        "CLAUDE_DISABLE_SANDBOX_VERIFY",
        "CLAUDE_DISABLE_VLM_CRITIC",
        "CLAUDE_DISABLE_SWE_PRUNER",
        "CLAUDE_DISABLE_INSTINCT_INJECTION",
        "CLAUDE_DISABLE_WORKTREE_REAPER",
    ]
    for key in disable_keys:
        assert env.get(key) == "0", (
            f"{key} must default to '0' (feature enabled) to preserve current behavior"
        )
    assert env.get("CLAUDE_VISIBLE_TEAMS") == "0", (
        "CLAUDE_VISIBLE_TEAMS must default to '0' (teams opt-in mode)"
    )
    assert env.get("CLAUDE_ENABLE_TRACE") == "0", (
        "CLAUDE_ENABLE_TRACE must default to '0' (tracing off by default)"
    )
    assert env.get("CLAUDE_PLAN_CACHE_MODE") == "shadow", (
        "CLAUDE_PLAN_CACHE_MODE must default to 'shadow' (record, no reuse)"
    )
    assert env.get("CLAUDE_PIPELINE_MODE") == "autonomous", (
        "CLAUDE_PIPELINE_MODE must default to 'autonomous'"
    )


def test_managed_env_contains_exactly_eight_keys():
    """AC2 exact-count guard: managed-settings.json env must contain EXACTLY the 8
    expected keys — no more, no fewer.

    The absence assertions for CLAUDE_PIPELINE_MODE and CLAUDE_ENABLE_TRACE catch those
    two specific vars if re-added, but any OTHER newly-pinned key would silently pass
    those checks.  This test locks the full set so any addition (or removal) is caught
    regardless of which key changes.
    """
    env = _load_managed_env()
    expected = {
        "CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS",
        "CLAUDE_HOOK_PROFILE",
        "ENABLE_TOOL_SEARCH",
        "CLAUDE_CODE_SUBAGENT_MODEL",
        "CLAUDE_SUBAGENT_MAX_DEPTH",
        "CLAUDE_SUBAGENT_MAX_RUNTIME",
        "CLAUDE_TEAMMATE_MAX_RUNTIME",
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS",
    }
    actual = set(env.keys())
    extra = actual - expected
    missing = expected - actual
    assert not extra, (
        f"managed-settings.json env has unexpected key(s): {extra}. "
        "Feature toggles belong at the user layer, not pinned in managed settings."
    )
    assert not missing, (
        f"managed-settings.json env is missing expected key(s): {missing}."
    )


def test_iron_law_gates_absent_from_user_settings():
    """AC-e: Iron-Law/correctness gate vars must NOT appear in user settings env."""
    env = _load_user_env()
    present = [k for k in IRON_LAW_GATES if k in env]
    assert not present, (
        f"Iron-Law gate vars must stay undocumented break-glass only; "
        f"found in user settings env: {present}"
    )


def test_readme_configuration_section_present():
    """AC-f (part 1): README.md has a ## Configuration heading."""
    content = README.read_text()
    assert "## Configuration" in content, (
        "README.md must contain a ## Configuration section"
    )


def test_readme_configuration_always_on_statement():
    """AC-f (part 2): README Configuration section contains always-on statement
    (phrases 'always-on' AND ('not configurable' or 'no workflow off-switch'))."""
    content = README.read_text()
    config_idx = content.find("## Configuration")
    assert config_idx >= 0, "## Configuration section not found in README"
    next_h2 = content.find("\n## ", config_idx + 1)
    section = content[config_idx:next_h2] if next_h2 >= 0 else content[config_idx:]
    has_always_on = "always-on" in section
    has_not_configurable = "not configurable" in section
    has_no_off_switch = "no workflow off-switch" in section
    assert has_always_on, (
        "README Configuration section must contain 'always-on'"
    )
    assert has_not_configurable or has_no_off_switch, (
        "README Configuration section must state the flow is not configurable "
        "(contain 'not configurable' or 'no workflow off-switch')"
    )


def test_readme_configuration_excludes_iron_law_keys():
    """AC-f (part 3): None of the AC4-excluded Iron-Law keys appear in the README
    Configuration section."""
    content = README.read_text()
    config_idx = content.find("## Configuration")
    assert config_idx >= 0, "## Configuration section not found in README"
    next_h2 = content.find("\n## ", config_idx + 1)
    section = content[config_idx:next_h2] if next_h2 >= 0 else content[config_idx:]
    for key in IRON_LAW_GATES:
        assert key not in section, (
            f"{key} must not appear in README Configuration section "
            "(it is an undocumented break-glass var, not a routine toggle)"
        )
