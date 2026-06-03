from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "protocols" / "verdict-catalog.md"

def test_tools_valid_in_verdict_catalog():
    body = CATALOG.read_text()
    assert "TOOLS_VALID" in body
    # Verify it's in a row with info polarity and harness-audit emitter
    lines = [l for l in body.splitlines() if "TOOLS_VALID" in l]
    assert lines, "TOOLS_VALID not found"
    line = lines[0]
    assert "info" in line
    assert "harness-audit" in line
    assert "utility" in line
