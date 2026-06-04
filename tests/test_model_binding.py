"""Model-binding helper tests (Slice A, TDD RED phase).

Tests for hooks/_lib/model_binding.py: should_emit_model + build_hook_output.
Pure functions only — no I/O, no subprocess.
"""
import inspect
import json
import unittest

try:
    import model_binding
    from model_binding import should_emit_model, build_hook_output
except ImportError:
    model_binding = None
    should_emit_model = None
    build_hook_output = None


class ShouldEmitModelReturnsTrueOnRuleMatch(unittest.TestCase):
    """A1: rule-match source + non-empty model → emit."""

    def test_rule_match_with_non_empty_model(self):
        result = should_emit_model({"source": "rule-match:budget_lt:6", "model": "sonnet"})
        self.assertTrue(result)


class ShouldEmitModelReturnsFalseOnDefaultArm(unittest.TestCase):
    """A2: default-arm source → no emit."""

    def test_default_arm_no_emit(self):
        result = should_emit_model({"source": "default-arm", "model": "opus"})
        self.assertFalse(result)


class ShouldEmitModelReturnsFalseOnNoConditional(unittest.TestCase):
    """A3: no-conditional source → no emit."""

    def test_no_conditional_no_emit(self):
        result = should_emit_model({"source": "no-conditional", "model": "opus"})
        self.assertFalse(result)


class ShouldEmitModelReturnsFalseOnNoBudget(unittest.TestCase):
    """A4: no-budget source → no emit (conservative: budget unavailable)."""

    def test_no_budget_no_emit(self):
        result = should_emit_model({"source": "no-budget", "model": "opus"})
        self.assertFalse(result)


class ShouldEmitModelReturnsFalseWhenModelEmpty(unittest.TestCase):
    """A5: rule-match source but empty model string → no emit."""

    def test_rule_match_empty_model_no_emit(self):
        result = should_emit_model({"source": "rule-match:budget_lt:6", "model": ""})
        self.assertFalse(result)


class ShouldEmitModelReturnsFalseWhenModelNone(unittest.TestCase):
    """A6: rule-match source but model is None → no emit."""

    def test_rule_match_none_model_no_emit(self):
        result = should_emit_model({"source": "rule-match:budget_lt:6", "model": None})
        self.assertFalse(result)


class ShouldEmitModelReturnsFalseWhenModelIsDict(unittest.TestCase):
    """A9: rule-match source but model is a dict (malformed YAML mapping) → no emit."""

    def test_rule_match_dict_model_no_emit(self):
        result = should_emit_model({"source": "rule-match:budget_lt:6", "model": {"injected": "x"}})
        self.assertFalse(result)


class ShouldEmitModelReturnsFalseWhenModelIsList(unittest.TestCase):
    """A10: rule-match source but model is a list → no emit."""

    def test_rule_match_list_model_no_emit(self):
        result = should_emit_model({"source": "rule-match:budget_lt:6", "model": ["sonnet"]})
        self.assertFalse(result)


class ShouldEmitModelReturnsFalseWhenModelIsInt(unittest.TestCase):
    """A11: rule-match source but model is an int → no emit."""

    def test_rule_match_int_model_no_emit(self):
        result = should_emit_model({"source": "rule-match:budget_lt:6", "model": 42})
        self.assertFalse(result)


class BuildHookOutputEmitsValidHookSpecificOutputJSON(unittest.TestCase):
    """A7: build_hook_output returns valid hookSpecificOutput JSON."""

    def test_valid_json_structure(self):
        raw = build_hook_output("sonnet")
        parsed = json.loads(raw)
        hso = parsed["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "allow")
        self.assertEqual(hso["updatedInput"]["model"], "sonnet")


class ModelBindingModuleIsPure(unittest.TestCase):
    """A8: module has no open(, subprocess, or os.environ."""

    def test_no_io_in_module_source(self):
        if model_binding is None:
            self.skipTest("model_binding not yet importable")
        source = inspect.getsource(model_binding)
        self.assertNotIn("open(", source, "model_binding must not call open()")
        self.assertNotIn("subprocess", source, "model_binding must not use subprocess")
        self.assertNotIn("os.environ", source, "model_binding must not read os.environ")


if __name__ == "__main__":
    unittest.main()
