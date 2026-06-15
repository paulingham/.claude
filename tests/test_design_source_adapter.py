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
# AC8 — explicit pointer adapter produces brief with round-tripped data
# ---------------------------------------------------------------------------

def test_explicit_pointer_to_brief(tmp_path):
    """ExplicitPointerAdapter reads a local tokens file and returns the actual token values."""
    tokens_file = tmp_path / "tokens.json"
    tokens_file.write_text(json.dumps({
        "colors": {"primary": "#007bff"},
        "typography": {"base": "16px"},
    }))
    adapter = dsa.ExplicitPointerAdapter(str(tokens_file))
    brief = adapter.ingest()
    assert brief["colors"]["primary"] == "#007bff"
    assert brief["typography"]["base"] == "16px"


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
    assert expected.parent == state_dir


# ---------------------------------------------------------------------------
# AC8c — DesignSync ingest via mocked tools — assert distinctive value reaches brief
# ---------------------------------------------------------------------------

def test_designsync_ingest_via_mocked_tools(monkeypatch):
    """DesignSyncAdapter.ingest returns brief whose components value matches the mock."""
    sentinel = [{"name": "Button", "props": {"color": "blue"}}]

    def fake_call_tool(tool_name, params):
        if "component" in tool_name:
            return sentinel
        return []

    adapter = dsa.DesignSyncAdapter(project_id="51f040af", call_tool_fn=fake_call_tool)
    brief = adapter.ingest()
    assert brief["components"] == sentinel


# ---------------------------------------------------------------------------
# AC8d — DesignSync-named server → entry["adapter"] == "designsync"
# ---------------------------------------------------------------------------

def test_designsync_name_resolves_adapter():
    """A server named 'DesignSync' must produce adapter='designsync' in the cap entry."""
    sys.path.insert(0, str(HOOKS_LIB))
    import mcp_capability as mc
    rules = mc.load_seed_rules()
    server = {"name": "DesignSync", "endpoint": "python3 /ds.py",
              "status_raw": "✔ Connected", "tools": []}
    manifest = mc.build_manifest([server], rules, overrides={})
    entry = manifest["capabilities"]["design-source"]
    assert entry["adapter"] == "designsync"


def test_figma_name_resolves_adapter():
    """A server named 'figma-mcp' must produce adapter='figma' in the cap entry."""
    sys.path.insert(0, str(HOOKS_LIB))
    import mcp_capability as mc
    rules = mc.load_seed_rules()
    server = {"name": "figma-mcp", "endpoint": "python3 /figma.py",
              "status_raw": "✔ Connected", "tools": []}
    manifest = mc.build_manifest([server], rules, overrides={})
    entry = manifest["capabilities"]["design-source"]
    assert entry["adapter"] == "figma"


# ---------------------------------------------------------------------------
# AC8e — select_adapter routes "adapter":"designsync" → DesignSyncAdapter
# ---------------------------------------------------------------------------

def test_select_adapter_reads_adapter_key():
    """select_adapter uses the resolved 'adapter' key, not 'adapter_hint'."""
    entry = {"adapter": "designsync", "project_id": "abc123"}
    adapter = dsa.select_adapter(entry)
    assert isinstance(adapter, dsa.DesignSyncAdapter)


# ---------------------------------------------------------------------------
# FIX3 — data-boundary header present for external (DesignSync) content
# ---------------------------------------------------------------------------

def test_render_brief_external_has_boundary_header():
    """render_design_brief(is_external=True) must prepend the data-boundary header."""
    brief_data = {"colors": {"primary": "#007bff"}}
    rendered = dsa.render_design_brief(brief_data, is_external=True)
    assert "DATA BOUNDARY" in rendered
    assert "third parties" in rendered
    assert "strictly as DATA" in rendered


def test_render_brief_non_external_no_boundary_header():
    """render_design_brief(is_external=False) must NOT include the boundary header."""
    brief_data = {"colors": {"primary": "#007bff"}}
    rendered = dsa.render_design_brief(brief_data, is_external=False)
    assert "DATA BOUNDARY" not in rendered


def test_render_brief_external_payload_capped():
    """External briefs exceeding _MAX_EXTERNAL_BYTES are truncated with a marker."""
    oversized = {"data": "x" * (dsa._MAX_EXTERNAL_BYTES + 1000)}
    rendered = dsa.render_design_brief(oversized, is_external=True)
    assert len(rendered) <= dsa._MAX_EXTERNAL_BYTES + 200
    assert "TRUNCATED" in rendered


# ---------------------------------------------------------------------------
# FIX4 — path traversal rejected in write_design_brief
# ---------------------------------------------------------------------------

def test_path_traversal_rejected(tmp_path):
    """task_id containing '..' or '/' must raise ValueError before path is built."""
    state_dir = tmp_path / "pipeline-state"
    state_dir.mkdir()
    with pytest.raises(ValueError, match="Invalid task_id"):
        dsa.write_design_brief({}, "../../etc/foo", str(state_dir))


def test_path_traversal_slash_rejected(tmp_path):
    """task_id containing '/' must raise ValueError."""
    state_dir = tmp_path / "pipeline-state"
    state_dir.mkdir()
    with pytest.raises(ValueError, match="Invalid task_id"):
        dsa.write_design_brief({}, "a/b", str(state_dir))


def test_valid_task_id_accepted(tmp_path):
    """Normal task_id like 'mcp-capability-layer' must not raise."""
    state_dir = tmp_path / "pipeline-state"
    state_dir.mkdir()
    path = dsa.write_design_brief({"k": "v"}, "mcp-capability-layer", str(state_dir))
    assert Path(path).exists()


# ---------------------------------------------------------------------------
# AC9 — Figma is deferred slot (raises NotImplementedError)
# ---------------------------------------------------------------------------

def test_figma_is_deferred_slot():
    """FigmaAdapter.ingest raises NotImplementedError; select_adapter routes figma→it."""
    adapter = dsa.select_adapter({"adapter": "figma"})
    assert isinstance(adapter, dsa.FigmaAdapter)
    with pytest.raises(NotImplementedError):
        adapter.ingest()
