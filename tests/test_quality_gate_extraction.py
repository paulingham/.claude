import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QG = ROOT / "hooks" / "quality-gate.sh"
QG_LIB = ROOT / "hooks" / "_lib" / "quality-gate-checks.sh"

def test_quality_gate_main_under_50_lines():
    assert QG.exists()
    line_count = sum(1 for _ in QG.read_text().splitlines())
    assert line_count <= 50, f"quality-gate.sh has {line_count} lines (limit 50)"

def test_quality_gate_lib_no_set_e():
    body = QG_LIB.read_text()
    assert not re.search(r'^set -e\b', body, re.MULTILINE), "lib must not use set -e"

def test_quality_gate_orchestrator_no_set_e():
    body = QG.read_text()
    assert not re.search(r'^set -e\b', body, re.MULTILINE), "orchestrator must use set -uo pipefail not set -e"

def test_quality_gate_lib_functions_return_not_exit():
    body = QG_LIB.read_text()
    assert not re.search(r'^\s*exit\s+\d', body, re.MULTILINE), "lib functions must use return, never exit"

def test_quality_gate_header_documents_extraction():
    body = QG.read_text()
    assert "extracted" in body.lower() or "extraction" in body.lower(), "header should document the extraction"
