"""Helpers for instinct_loader: parse, validate, normalize, log."""
import os
import unittest

from instinct_loader_helpers import extract_summary, log_warning, validate


class _MaliciousPath:
    """Stand-in for pathlib.Path whose str() injects shell metacharacters."""
    def __init__(self, payload):
        self._payload = payload

    def __str__(self):
        return self._payload


class ExtractSummary(unittest.TestCase):
    def test_skips_blank_lines_within_pattern_section(self):
        body = "## Pattern\n   \n\t\n\n## Why\nReason.\n"
        self.assertEqual(extract_summary(body), "")


class ValidateRequiresAllFields(unittest.TestCase):
    def test_returns_malformed_yaml_when_fm_is_none(self):
        self.assertEqual(validate(None, "## Pattern\nx\n"), "malformed-yaml")


class LogWarningResistsShellInjection(unittest.TestCase):
    """Path-derived strings must NOT be interpreted as shell commands."""

    SENTINEL = "/tmp/INSTINCT_PWN"

    def setUp(self):
        self._cleanup_sentinel()
        self.addCleanup(self._cleanup_sentinel)

    def _cleanup_sentinel(self):
        try:
            os.unlink(self.SENTINEL)
        except FileNotFoundError:
            pass

    def test_filename_with_quote_breakout_does_not_execute(self):
        evil = _MaliciousPath(f"a';touch {self.SENTINEL};'.md")
        log_warning(evil, "missing-id-field")
        self.assertFalse(os.path.exists(self.SENTINEL),
                         "log_warning must not execute injected shell payload")


# ---------------- B63: prefer_opus instinct field (Wave 5/B6.3) ----------------


from instinct_loader_helpers import normalize


_MIN_FM = {"id": "x1", "confidence": 0.5, "roles": ["software-engineer"]}
_MIN_BODY = "## Pattern\nfoo\n"


class NormalizeReturnsPreferOpusFalseByDefault(unittest.TestCase):
    def test_absent_prefer_opus_normalises_to_false(self):
        result = normalize(dict(_MIN_FM), _MIN_BODY, "global")
        self.assertEqual(result["prefer_opus"], False)


class NormalizeReturnsPreferOpusTrueWhenSet(unittest.TestCase):
    def test_explicit_prefer_opus_true_normalises_to_true(self):
        fm = dict(_MIN_FM, prefer_opus=True)
        result = normalize(fm, _MIN_BODY, "global")
        self.assertEqual(result["prefer_opus"], True)


class NonBoolPreferOpusLogsWarningAndCoercesFalse(unittest.TestCase):
    def test_non_bool_prefer_opus_warns_and_falsifies(self):
        fm = dict(_MIN_FM, prefer_opus="yes")
        self.assertEqual(validate(fm, _MIN_BODY), "non-bool-prefer-opus")
        self.assertEqual(normalize(fm, _MIN_BODY, "global")["prefer_opus"],
                         False)


class NormalizeReturnDictHasSevenKeys(unittest.TestCase):
    def test_normalize_keys_include_prefer_opus(self):
        keys = set(normalize(dict(_MIN_FM), _MIN_BODY, "global").keys())
        expected = {"id", "confidence", "roles", "domain", "scope",
                    "pattern_summary", "prefer_opus"}
        self.assertEqual(keys, expected)


class ValidatePreferOpusReturnsCodeNotMessage(unittest.TestCase):
    def test_validate_returns_code_for_non_bool_prefer_opus(self):
        fm = dict(_MIN_FM, prefer_opus=42)  # non-bool, non-string
        self.assertEqual(validate(fm, _MIN_BODY), "non-bool-prefer-opus")
