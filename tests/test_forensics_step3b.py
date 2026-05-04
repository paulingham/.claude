from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "forensics" / "SKILL.md"

def test_skill_md_contains_step_3b_hook_protection_lookup():
    body = SKILL.read_text()
    assert "Step 3b: Hook Protection Lookup" in body or "### Step 3b" in body

def test_step_3b_documents_extraction_procedure():
    body = SKILL.read_text()
    assert "# enforces:" in body
    assert "# protects:" in body

def test_anomalies_table_schema_includes_rule_protected_column():
    body = SKILL.read_text()
    assert "Rule Protected" in body
