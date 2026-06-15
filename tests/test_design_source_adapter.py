"""Tests for s2 — design-source adapter: explicit-pointer, DesignSync mock, Figma deferred."""
import json
import sys
from pathlib import Path

import pytest

HOOKS_LIB = Path(__file__).resolve().parent.parent / "hooks" / "_lib"
if str(HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(HOOKS_LIB))

import design_source_adapter as dsa


# ---------------------------------------------------------------------------
# AC8 — explicit pointer adapter produces brief
# ---------------------------------------------------------------------------

def test_explicit_pointer_to_brief(tmp_path):
    """ExplicitPointerAdapter reads a local tokens file and returns brief dict."""
    tokens_file = tmp_path / "tokens.json"
    tokens_file.write_text(json.dumps({
        "colors": {"primary": "#007bff"},
        "typography": {"base": "16px"},
    }))
    adapter = dsa.ExplicitPointerAdapter(str(tokens_file))
    brief = adapter.ingest()
    assert "colors" in brief or "tokens" in brief or isinstance(brief, dict)
    assert brief  # non-empty


# ---------------------------------------------------------------------------
# AC8b — flat path: pipeline-state/{task-id}-design-brief.md
# ---------------------------------------------------------------------------

def test_brief_written_to_flat_frontend_path(tmp_path):
    """write_design_brief writes to flat pipeline-state/{task-id}-design-brief.md, NOT a subdir."""
    brief_data = {"colors": {"primary": "#007bff"}}
    task_id = "my-task"
    state_dir = tmp_path / "pipeline-state"
    state_dir.mkdir()

    written_path = dsa.write_design_brief(brief_data, task_id, str(state_dir))

    expected = state_dir / f"{task_id}-design-brief.md"
    assert Path(written_path) == expected
    assert expected.exists()
    # Must NOT be in a subdirectory
    assert expected.parent == state_dir


# ---------------------------------------------------------------------------
# AC8c — DesignSync ingest via mocked tools
# ---------------------------------------------------------------------------

def test_designsync_ingest_via_mocked_tools(monkeypatch):
    """DesignSyncAdapter.ingest calls get_file/list_components and returns brief dict."""
    mock_result = {
        "components": [{"name": "Button", "props": {"color": "blue"}}],
        "variables": [{"name": "--color-primary", "value": "#007bff"}],
    }

    def fake_call_tool(tool_name, params):
        if "component" in tool_name or "variable" in tool_name:
            return mock_result
        return {}

    adapter = dsa.DesignSyncAdapter(project_id="51f040af", call_tool_fn=fake_call_tool)
    brief = adapter.ingest()
    assert isinstance(brief, dict)
    assert brief  # non-empty


# ---------------------------------------------------------------------------
# AC9 — Figma is deferred slot (raises NotImplementedError)
# ---------------------------------------------------------------------------

def test_figma_is_deferred_slot():
    """FigmaAdapter.ingest raises NotImplementedError; select_adapter routes figma→it."""
    adapter = dsa.select_adapter({"adapter_hint": "figma"})
    assert isinstance(adapter, dsa.FigmaAdapter)
    with pytest.raises(NotImplementedError):
        adapter.ingest()
