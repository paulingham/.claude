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
