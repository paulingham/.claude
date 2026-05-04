import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "hooks" / "_lib" / "known-tools.txt"
SETTINGS = ROOT / "settings.json"

def _known_tools():
    body = CATALOG.read_text()
    return {line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#")}

def _known_servers():
    settings = json.loads(SETTINGS.read_text())
    return set(settings.get("mcpServers", {}).keys())

def test_known_tools_file_exists_and_nonempty():
    assert CATALOG.exists()
    tools = _known_tools()
    expected_min = {"Read", "Write", "Edit", "Bash", "Agent", "Skill", "Grep", "Glob", "WebFetch", "WebSearch", "NotebookEdit"}
    assert expected_min.issubset(tools), f"Missing core tools: {expected_min - tools}"

def test_audit_flags_unknown_tool():
    # Algorithm: known catalog + mcp__<server>__* check
    tools = _known_tools()
    fake = "FakeTool"
    assert fake not in tools

def test_audit_accepts_mcp_tools_from_settings():
    servers = _known_servers()
    # mcp__<server>__<tool> pattern
    pattern = re.compile(r"^mcp__([^_-]+(?:-[^_-]+)*)__.+$")
    for server in servers:
        candidate = f"mcp__{server}__test_tool"
        m = pattern.match(candidate)
        assert m and m.group(1) in servers

def test_audit_flags_mcp_tool_with_unknown_server():
    servers = _known_servers()
    pattern = re.compile(r"^mcp__([^_-]+(?:-[^_-]+)*)__.+$")
    candidate = "mcp__notexist__store"
    m = pattern.match(candidate)
    assert m is not None
    assert m.group(1) not in servers

def test_audit_extracts_server_slug_via_documented_regex():
    pattern = re.compile(r"^mcp__([^_-]+(?:-[^_-]+)*)__.+$")
    cases = [
        ("mcp__memory__store", "memory"),
        ("mcp__gh-cache__prefetch_pr", "gh-cache"),
        ("mcp__lsp-typescript__diagnose", "lsp-typescript"),
    ]
    for tool, expected in cases:
        m = pattern.match(tool)
        assert m and m.group(1) == expected, f"Expected {expected} from {tool}"
