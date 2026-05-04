from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "harness-audit" / "SKILL.md"

def test_skill_md_contains_step_3b_tool_catalog_validation():
    body = SKILL.read_text()
    assert "### 3b. Tool Catalog Validation" in body or "### 3b Tool Catalog" in body

def test_step_3b_documents_mcp_tool_pattern():
    body = SKILL.read_text()
    assert "mcp__" in body
    assert "mcpServers" in body

def test_step_3b_documents_three_step_algorithm():
    body = SKILL.read_text()
    body_lower = body.lower()
    assert "3-step" in body_lower or "step 1" in body_lower

def test_step_3b_emits_tools_valid_verdict():
    body = SKILL.read_text()
    assert "TOOLS_VALID" in body
