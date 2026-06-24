"""B6c — deploy-outcome-audit.sh registered in BOTH settings.json and hooks/hooks.json.

Guards against #18517 drift where the two files are loaded independently.
Both PostToolUse[0].hooks must have len==7 and index-6 must reference the hook.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_post_tool_use_block(path: Path) -> list:
    data = json.loads(path.read_text())
    return data["hooks"]["PostToolUse"][0]["hooks"]


def test_settings_json_has_7_hooks() -> None:
    hooks = _load_post_tool_use_block(REPO_ROOT / "settings.json")
    assert len(hooks) == 7, f"expected 7 hooks, got {len(hooks)}"


def test_hooks_json_has_7_hooks() -> None:
    hooks = _load_post_tool_use_block(REPO_ROOT / "hooks" / "hooks.json")
    assert len(hooks) == 7, f"expected 7 hooks, got {len(hooks)}"


def test_settings_json_index_6_references_deploy_outcome_audit() -> None:
    hooks = _load_post_tool_use_block(REPO_ROOT / "settings.json")
    entry = hooks[6]
    args_str = " ".join(entry.get("args", []))
    assert "deploy-outcome-audit.sh" in args_str, (
        f"hooks[6] does not reference deploy-outcome-audit.sh: {entry}"
    )


def test_hooks_json_index_6_references_deploy_outcome_audit() -> None:
    hooks = _load_post_tool_use_block(REPO_ROOT / "hooks" / "hooks.json")
    entry = hooks[6]
    args_str = " ".join(entry.get("args", []))
    assert "deploy-outcome-audit.sh" in args_str, (
        f"hooks[6] does not reference deploy-outcome-audit.sh: {entry}"
    )
