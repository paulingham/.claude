import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "hooks" / "_lib" / "harness-audit-fast.sh"

def test_harness_audit_fast_lib_exists():
    assert LIB.exists()

def test_harness_audit_fast_lib_has_required_functions():
    body = LIB.read_text()
    for fn in ["_haf_check_settings_json", "_haf_count_orphan_hooks", "_haf_check_agents_frontmatter", "_haf_run_all"]:
        assert fn in body, f"Missing function: {fn}"

def test_harness_audit_fast_lib_functions_under_8_lines():
    # Loose check: each function body ≤8 lines (counted between { and })
    body = LIB.read_text()
    fns = re.findall(r'(_haf_\w+)\(\)\s*\{(.*?)\n\}', body, re.DOTALL)
    for name, fn_body in fns:
        lines = [l for l in fn_body.split('\n') if l.strip()]
        assert len(lines) <= 8, f"{name} has {len(lines)} lines (limit 8)"
