"""AC-A5h: AST scan confirms no bare os.environ.pop without restore in CA8 test files."""
import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CA8_FILES = [
    "tests/test_pre_agent_allowlist.py",
    "tests/test_allowlist_concurrency.py",
    "tests/test_thinking_defaults.py",
    "tests/test_tool_timing_capture.py",
    "tests/test_hook_injection_schema.py",
    "tests/test_runtime_guard_respawn.py",
    "tests/test_instinct_hook.py",
    "tests/test_pre_agent_allowlist_flip.py",
    "tests/test_named_deviation_token.py",
    "tests/test_advisor_resolver.py",
    "tests/test_freshness_guard.py",
    "tests/test_advisor_disable_envvar.py",
    "tests/test_thinking_disable_envvar.py",
    "tests/test_codebase_map_budget_forensics.py",
    "tests/test_codebase_map_integration.py",
    "tests/hooks/test_intake_fingerprint_emit_gap_fills.py",
    "tests/test_hook_self_test_rate_limit.py",
]


def _has_bare_environ_pop(filepath):
    """Return True if file has os.environ.pop() call not inside a with patch.dict block."""
    try:
        tree = ast.parse(Path(filepath).read_text())
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "pop"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "environ"):
                return True
    return False


class TestAllEnvCoupledTestsUsePatchDictNotBarePop(unittest.TestCase):
    def test_all_env_coupled_tests_use_patch_dict_not_bare_pop(self):
        violations = []
        for rel in CA8_FILES:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            if _has_bare_environ_pop(str(path)):
                violations.append(rel)
        self.assertEqual(
            violations, [],
            f"Files with bare os.environ.pop (use patch.dict instead): {violations}",
        )


if __name__ == "__main__":
    unittest.main()
