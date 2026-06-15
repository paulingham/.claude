"""Tests for s0 — MCP capability detection: parsing, dedup, classification, manifest."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

HOOKS_LIB = Path(__file__).resolve().parent.parent / "hooks" / "_lib"
if str(HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(HOOKS_LIB))

import mcp_capability as mc


# ---------------------------------------------------------------------------
# AC1 — canonical line split (name via split(': ',1); status via rsplit(' - ',1))
# ---------------------------------------------------------------------------

def test_parse_canonical_line_split():
    """Flagged endpoint with ' - ' in args must parse correctly."""
    line = "plugin:harness:lsp-typescript: python3 /abs/path/lsp-bridge-server.py --language ts - ✔ Connected"
    result = mc.parse_mcp_list_line(line)
    assert result is not None
    assert result["name"] == "plugin:harness:lsp-typescript"
    assert "--language ts" in result["endpoint"]
    assert result["status_raw"] == "✔ Connected"


# ---------------------------------------------------------------------------
# AC1b — normalize four statuses
# ---------------------------------------------------------------------------

def test_normalize_four_statuses():
    """All four status symbols must map to canonical strings."""
    assert mc.normalize_status("✔ Connected") == "connected"
    assert mc.normalize_status("! Needs authentication") == "needs-auth"
    assert mc.normalize_status("⏸ Pending approval (run `claude` to approve)") == "pending"
    assert mc.normalize_status("") == "absent"


# ---------------------------------------------------------------------------
# AC1c — deduplicate namespace shadow
# ---------------------------------------------------------------------------

def test_deduplicate_namespace_shadow():
    """plugin:harness:X (connected) + bare X (pending) → keep prefixed/connected, drop bare."""
    servers = [
        {"name": "plugin:harness:gh-cache", "endpoint": "/abs/path/server.py", "status_raw": "✔ Connected"},
        {"name": "gh-cache", "endpoint": "${CLAUDE_PLUGIN_ROOT}/server.py", "status_raw": "⏸ Pending approval (run `claude` to approve)"},
    ]
    result = mc.deduplicate_servers(servers)
    assert len(result) == 1
    assert result[0]["name"] == "plugin:harness:gh-cache"
    assert mc.normalize_status(result[0]["status_raw"]) == "connected"


# ---------------------------------------------------------------------------
# AC1d — skip preamble and footer
# ---------------------------------------------------------------------------

def test_skip_preamble_and_footer():
    """Header, blank lines, and MCP Config Diagnostics footer → exactly 1 server parsed."""
    raw = (
        "Checking MCP server health…\n"
        "\n"
        "plugin:harness:gh-cache: python3 /abs/server.py - ✔ Connected\n"
        "\n"
        "MCP Config Diagnostics\n"
        "\n"
        "For help configuring MCP servers, see: https://example.com\n"
        "[Contains warnings] Project config\n"
        " ├ [Warning] Missing environment variables: CLAUDE_PLUGIN_ROOT\n"
    )
    servers = mc.parse_mcp_list(raw)
    assert len(servers) == 1
    assert servers[0]["name"] == "plugin:harness:gh-cache"


# ---------------------------------------------------------------------------
# AC2 — classify by name_regex
# ---------------------------------------------------------------------------

def test_classify_by_name_regex():
    """A server whose name matches a seed regex gets classified correctly."""
    rules = mc.load_seed_rules()
    server = {"name": "DesignSync", "endpoint": "python3 /path", "status_raw": "✔ Connected", "tools": []}
    cap = mc.classify_server(server, rules, overrides={})
    assert cap == "design-source"


# ---------------------------------------------------------------------------
# AC2b — classify by tool_family fallback (custom name, no regex match)
# ---------------------------------------------------------------------------

def test_classify_by_tool_family_fallback():
    """Custom-named server with no name match but matching tool-family verb → correct class."""
    rules = mc.load_seed_rules()
    # A server named "custom-tracker" (no regex) with a tool "move_card_to_list"
    server = {
        "name": "custom-tracker",
        "endpoint": "python3 /path",
        "status_raw": "✔ Connected",
        "tools": ["move_card_to_list", "list_board_columns"],
    }
    cap = mc.classify_server(server, rules, overrides={})
    assert cap == "issue-tracker"


# ---------------------------------------------------------------------------
# AC3 — override wins over seed
# ---------------------------------------------------------------------------

def test_override_wins_over_seed():
    """An override entry wins over name_regex and tool_family classification."""
    rules = mc.load_seed_rules()
    overrides = {"my-custom-server": "design-source"}
    server = {"name": "my-custom-server", "endpoint": "...", "status_raw": "✔ Connected", "tools": []}
    cap = mc.classify_server(server, rules, overrides=overrides)
    assert cap == "design-source"


# ---------------------------------------------------------------------------
# AC3b — missing override is advisory not error
# ---------------------------------------------------------------------------

def test_missing_override_is_advisory_not_error():
    """A server not in overrides does NOT raise; returns classification from seed."""
    rules = mc.load_seed_rules()
    server = {"name": "unknown-server-xyz", "endpoint": "...", "status_raw": "✔ Connected", "tools": []}
    cap = mc.classify_server(server, rules, overrides={})
    assert cap == "unclassified"


# ---------------------------------------------------------------------------
# AC4 — build and write manifest
# ---------------------------------------------------------------------------

def test_build_and_write_manifest(tmp_path):
    """build_manifest produces a valid schema_version 1 dict with known classes."""
    servers = [
        {"name": "plugin:harness:gh-cache", "endpoint": "/abs", "status_raw": "✔ Connected", "tools": []},
    ]
    rules = mc.load_seed_rules()
    manifest = mc.build_manifest(servers, rules, overrides={})
    assert manifest["schema_version"] == 1
    assert "capabilities" in manifest
    assert "unclassified" in manifest


# ---------------------------------------------------------------------------
# AC4b — unclassified server recorded in manifest
# ---------------------------------------------------------------------------

def test_unclassified_server_recorded():
    """Unknown servers go into manifest['unclassified'] list."""
    servers = [
        {"name": "mystery-server", "endpoint": "/path", "status_raw": "✔ Connected", "tools": []},
    ]
    rules = mc.load_seed_rules()
    manifest = mc.build_manifest(servers, rules, overrides={})
    names = [u["server"] for u in manifest["unclassified"]]
    assert "mystery-server" in names


# ---------------------------------------------------------------------------
# AC4c — lsp-nav servers recorded only (no consumer)
# ---------------------------------------------------------------------------

def test_lsp_record_only():
    """LSP server is recorded in manifest capabilities but no consumer invoked."""
    servers = [
        {"name": "plugin:harness:lsp-typescript", "endpoint": "/path", "status_raw": "✔ Connected", "tools": []},
    ]
    rules = mc.load_seed_rules()
    manifest = mc.build_manifest(servers, rules, overrides={})
    assert "lsp-nav" in manifest["capabilities"]
    assert manifest["capabilities"]["lsp-nav"]["status"] == "connected"


# ---------------------------------------------------------------------------
# AC4d — issue-tracker detected but NOT consumed
# ---------------------------------------------------------------------------

def test_issue_tracker_detected_not_consumed():
    """Issue-tracker server recorded in manifest; no consumer side-effect invoked."""
    servers = [
        {"name": "jira-bridge", "endpoint": "/path", "status_raw": "✔ Connected",
         "tools": ["create_issue", "transition_issue"]},
    ]
    rules = mc.load_seed_rules()
    manifest = mc.build_manifest(servers, rules, overrides={})
    assert "issue-tracker" in manifest["capabilities"]
    assert manifest["capabilities"]["issue-tracker"]["status"] == "connected"


# ---------------------------------------------------------------------------
# AC10 — no import cycle
# ---------------------------------------------------------------------------

def test_no_import_cycle():
    """All hooks/_lib modules import without circular-dependency errors."""
    import importlib
    for mod_name in ["mcp_capability", "capability_advisory", "design_source_adapter"]:
        mod = importlib.import_module(mod_name)
        assert mod is not None
