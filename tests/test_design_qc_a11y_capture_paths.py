"""AC3 + AC4 — capture path resolver records correct fallback states.

Capture path is owned by Node (a11y_capture.js / a11y_probe.js); the
boundary is the JSON index file. These tests cover the Python side of
the contract: given probe + library-capture invokers as DI hooks, the
resolver reports the correct `a11y_global.capture_path` and reason.
"""
import json
import tempfile
import unittest
from pathlib import Path

import a11y_capture_resolver
from a11y_capture_resolver import resolve_capture


def _ok_invoker(*_args, **_kwargs):
    return {"ok": True, "payload": {"role": "WebArea", "children": []}}


def _fail_invoker(*_args, **_kwargs):
    raise RuntimeError("simulated failure")


class LibraryFallbackPath(unittest.TestCase):
    """AC3 — MCP probe fails, library succeeds => captured=true, path=library."""

    def test_library_fallback_records_captured_true(self):
        result = resolve_capture(
            mcp_probe=_fail_invoker,
            mcp_capture=_fail_invoker,
            library_capture=_ok_invoker,
        )
        self.assertTrue(result["captured"])
        self.assertEqual(result["capture_path"], "library")


class McpPath(unittest.TestCase):
    """MCP probe succeeds => captured=true, path=mcp."""

    def test_mcp_probe_success_records_capture_path_mcp(self):
        result = resolve_capture(
            mcp_probe=_ok_invoker,
            mcp_capture=_ok_invoker,
            library_capture=_fail_invoker,
        )
        self.assertTrue(result["captured"])
        self.assertEqual(result["capture_path"], "mcp")


class NoCapturePath(unittest.TestCase):
    """AC4 — both paths fail => captured=false, reason=mcp-unavailable."""

    def test_no_capture_path_records_mcp_unavailable(self):
        result = resolve_capture(
            mcp_probe=_fail_invoker,
            mcp_capture=_fail_invoker,
            library_capture=_fail_invoker,
        )
        self.assertFalse(result["captured"])
        self.assertEqual(result["reason"], "mcp-unavailable")
        self.assertIsNone(result["capture_path"])


class ScratchpadWarning(unittest.TestCase):
    """AC4 — scratchpad warning written when capture unavailable."""

    def test_warning_text_contains_mcp_unavailable_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratchpad = Path(tmp) / "design-qc-build.md"
            a11y_capture_resolver.write_warning(
                scratchpad, reason="mcp-unavailable")
            text = scratchpad.read_text()
            self.assertIn("mcp-unavailable", text)
            self.assertIn("category: warning", text)


if __name__ == "__main__":
    unittest.main()
