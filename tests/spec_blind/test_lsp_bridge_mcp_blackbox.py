"""Spec-blind black-box behavioural tests for the LSP go-to-definition bridge.

These tests drive  python3 hooks/_lib/lsp-bridge-server.py --language {ts,py}
over stdin/stdout exactly as an MCP client would.  They import NO internal
modules (no lsp-bridge-rpc.py, no lsp-bridge-lsp.py).

ACs under test
--------------
AC-LIST: tools/list returns BOTH a definition tool AND a diagnostics tool.
AC-NOBIN: tools/call mcp_lsp_definition_{ts,py} with no LS binary on PATH
           → isError:true, error "ls-unavailable".
AC-BADARGS: missing or non-int args → isError:true, error "bad-args".
AC-UNSUP: unknown tool name → isError:true, error "unsupported".
AC-DIAG: diagnostics tools/call → isError:false (advisory stub, no crash).
AC-ENV: All replies carry {content:[{type:text,text}], isError} envelope.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Locate the server entry-point — the PUBLIC surface.
# Walk up from this file until we find lsp-bridge-server.py.
# Never import any internal module.
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "settings.json").is_file() and (parent / "rules").is_dir():
            return parent
    raise RuntimeError("spec-blind: cannot locate repo root")


_REPO_ROOT = _find_repo_root()
_SERVER = _REPO_ROOT / "hooks" / "_lib" / "lsp-bridge-server.py"


# ---------------------------------------------------------------------------
# Helper: send one JSON-RPC request to the server process, return parsed reply.
# The server reads newline-delimited JSON from stdin; we feed one request,
# close stdin, and read one response line from stdout.
# ---------------------------------------------------------------------------

def _rpc(lang: str, request: dict[str, Any]) -> dict[str, Any]:
    """Spawn the server, send one request, return the parsed reply."""
    proc = subprocess.run(
        [sys.executable, str(_SERVER), "--language", lang],
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        timeout=10,
    )
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    if not lines:
        raise AssertionError(
            f"Server produced no output for lang={lang!r} request={request!r}.\n"
            f"stderr: {proc.stderr!r}"
        )
    return json.loads(lines[0])


# ---------------------------------------------------------------------------
# Shared helper for the MCP content-envelope contract (AC-ENV).
# ---------------------------------------------------------------------------

def _assert_mcp_envelope(result: dict[str, Any], *, label: str) -> None:
    """Assert {content:[{type:text,text:...}], isError:bool} shape."""
    assert "content" in result, f"{label}: missing 'content' key"
    assert isinstance(result["content"], list), f"{label}: 'content' must be a list"
    assert len(result["content"]) >= 1, f"{label}: 'content' must be non-empty"
    item = result["content"][0]
    assert item.get("type") == "text", (
        f"{label}: content[0].type must be 'text', got {item.get('type')!r}"
    )
    assert isinstance(item.get("text"), str), f"{label}: content[0].text must be a str"
    assert "isError" in result, f"{label}: missing 'isError' key"
    assert isinstance(result["isError"], bool), f"{label}: 'isError' must be bool"


# ---------------------------------------------------------------------------
# AC-LIST — tools/list for TypeScript
# ---------------------------------------------------------------------------

class TestToolsListTs:
    """tools/list must expose both definition and diagnostics tools for TS."""

    def _list_tools(self) -> list[dict]:
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        reply = _rpc("ts", req)
        return reply["result"]["tools"]

    def test_tools_list_contains_exactly_two_tools_ts(self):
        tools = self._list_tools()
        names = [t["name"] for t in tools]
        assert len(names) == 2, f"Expected 2 tools, got {len(names)}: {names}"

    def test_tools_list_contains_definition_tool_ts(self):
        names = [t["name"] for t in self._list_tools()]
        assert "mcp_lsp_definition_ts" in names, (
            f"mcp_lsp_definition_ts absent from tools/list; got: {names}"
        )

    def test_tools_list_contains_diagnostics_tool_ts(self):
        names = [t["name"] for t in self._list_tools()]
        assert "mcp_lsp_diagnostics_ts" in names, (
            f"mcp_lsp_diagnostics_ts absent from tools/list; got: {names}"
        )


# ---------------------------------------------------------------------------
# AC-LIST — tools/list for Python
# ---------------------------------------------------------------------------

class TestToolsListPy:
    """tools/list must expose both definition and diagnostics tools for Python."""

    def _list_tools(self) -> list[dict]:
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        reply = _rpc("py", req)
        return reply["result"]["tools"]

    def test_tools_list_contains_exactly_two_tools_py(self):
        tools = self._list_tools()
        names = [t["name"] for t in tools]
        assert len(names) == 2, f"Expected 2 tools, got {len(names)}: {names}"

    def test_tools_list_contains_definition_tool_py(self):
        names = [t["name"] for t in self._list_tools()]
        assert "mcp_lsp_definition_py" in names, (
            f"mcp_lsp_definition_py absent from tools/list; got: {names}"
        )

    def test_tools_list_contains_diagnostics_tool_py(self):
        names = [t["name"] for t in self._list_tools()]
        assert "mcp_lsp_diagnostics_py" in names, (
            f"mcp_lsp_diagnostics_py absent from tools/list; got: {names}"
        )


# ---------------------------------------------------------------------------
# AC-BADARGS — missing required arguments
# ---------------------------------------------------------------------------

class TestBadArgs:
    """Missing or non-int args must return isError:true, error:'bad-args'."""

    def test_missing_line_arg_ts(self):
        """Missing 'line' arg → bad-args (TS)."""
        req = {
            "jsonrpc": "2.0", "id": 10, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_ts",
                "arguments": {"path": "/x.ts", "character": 0},  # line missing
            },
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="bad-args/missing-line/ts")
        assert result["isError"] is True, (
            "Expected isError:true for missing 'line' arg"
        )
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "bad-args", (
            f"Expected error:'bad-args', got: {err}"
        )

    def test_missing_character_arg_ts(self):
        """Missing 'character' arg → bad-args (TS)."""
        req = {
            "jsonrpc": "2.0", "id": 11, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_ts",
                "arguments": {"path": "/x.ts", "line": 0},  # character missing
            },
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="bad-args/missing-character/ts")
        assert result["isError"] is True
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "bad-args", f"Expected error:'bad-args', got: {err}"

    def test_missing_path_arg_ts(self):
        """Missing 'path' arg → bad-args (TS)."""
        req = {
            "jsonrpc": "2.0", "id": 12, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_ts",
                "arguments": {"line": 0, "character": 0},  # path missing
            },
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="bad-args/missing-path/ts")
        assert result["isError"] is True
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "bad-args", f"Expected error:'bad-args', got: {err}"

    def test_string_line_returns_bad_args_ts(self):
        """Non-int 'line' (string) → bad-args (TS)."""
        req = {
            "jsonrpc": "2.0", "id": 13, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_ts",
                "arguments": {"path": "/x.ts", "line": "0", "character": 0},
            },
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="bad-args/string-line/ts")
        assert result["isError"] is True
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "bad-args", f"Expected error:'bad-args', got: {err}"

    def test_bool_line_returns_bad_args_ts(self):
        """Non-int 'line' (bool) → bad-args (TS).

        In Python, bool is a subclass of int.  The AC says non-int → bad-args.
        Both True/False must be rejected because bool is not a numeric position.
        """
        req = {
            "jsonrpc": "2.0", "id": 14, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_ts",
                "arguments": {"path": "/x.ts", "line": True, "character": 0},
            },
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="bad-args/bool-line/ts")
        assert result["isError"] is True
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "bad-args", f"Expected error:'bad-args', got: {err}"

    def test_missing_line_arg_py(self):
        """Missing 'line' arg → bad-args (Python)."""
        req = {
            "jsonrpc": "2.0", "id": 20, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_py",
                "arguments": {"path": "/x.py", "character": 0},
            },
        }
        reply = _rpc("py", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="bad-args/missing-line/py")
        assert result["isError"] is True
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "bad-args", f"Expected error:'bad-args', got: {err}"


# ---------------------------------------------------------------------------
# AC-UNSUP — unknown tool name
# ---------------------------------------------------------------------------

class TestUnsupportedToolName:
    """Calling an unrecognised tool name must return isError:true, error:'unsupported'."""

    def test_unknown_tool_name_ts_server(self):
        """Completely unknown tool → unsupported (TS server)."""
        req = {
            "jsonrpc": "2.0", "id": 30, "method": "tools/call",
            "params": {"name": "mcp_lsp_unknown_tool", "arguments": {}},
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="unsupported/unknown-tool/ts")
        assert result["isError"] is True
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "unsupported", (
            f"Expected error:'unsupported', got: {err}"
        )

    def test_wrong_language_tool_ts_server(self):
        """Calling mcp_lsp_definition_rb on TS server → unsupported."""
        req = {
            "jsonrpc": "2.0", "id": 31, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_rb",   # Ruby — not a known lang
                "arguments": {"path": "/x.rb", "line": 0, "character": 0},
            },
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="unsupported/wrong-lang-rb/ts")
        assert result["isError"] is True
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "unsupported", (
            f"Expected error:'unsupported', got: {err}"
        )

    def test_py_tool_on_ts_server(self):
        """Calling mcp_lsp_definition_py on the TS server → unsupported.

        The server is started with --language ts; it should not serve the py tool.
        """
        req = {
            "jsonrpc": "2.0", "id": 32, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_py",
                "arguments": {"path": "/x.py", "line": 0, "character": 0},
            },
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="unsupported/py-on-ts-server/ts")
        assert result["isError"] is True
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "unsupported", (
            f"Expected error:'unsupported', got: {err}"
        )


# ---------------------------------------------------------------------------
# AC-NOBIN — no LS binary on PATH → ls-unavailable
# ---------------------------------------------------------------------------

class TestLsUnavailable:
    """When no LS binary is on PATH, definition call → isError:true, error:'ls-unavailable'."""

    def _rpc_no_path(self, lang: str, request: dict[str, Any]) -> dict[str, Any]:
        """Spawn the server with an empty PATH to guarantee no LS binary."""
        proc = subprocess.run(
            [sys.executable, str(_SERVER), "--language", lang],
            input=json.dumps(request) + "\n",
            capture_output=True,
            text=True,
            timeout=10,
            env={"PATH": ""},  # strip PATH — no binaries available
        )
        lines = [l for l in proc.stdout.splitlines() if l.strip()]
        if not lines:
            raise AssertionError(
                f"Server produced no output (no-PATH, lang={lang!r}).\n"
                f"stderr: {proc.stderr!r}"
            )
        return json.loads(lines[0])

    def test_definition_ts_no_binary_returns_ls_unavailable(self):
        """No LS binary on PATH → ls-unavailable for TS definition."""
        req = {
            "jsonrpc": "2.0", "id": 40, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_ts",
                "arguments": {"path": "/x.ts", "line": 0, "character": 0},
            },
        }
        result = self._rpc_no_path("ts", req)["result"]
        _assert_mcp_envelope(result, label="ls-unavailable/ts")
        assert result["isError"] is True, (
            f"Expected isError:true (no LS binary), got: {result}"
        )
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "ls-unavailable", (
            f"Expected error:'ls-unavailable', got: {err}"
        )

    def test_definition_py_no_binary_returns_ls_unavailable(self):
        """No LS binary on PATH → ls-unavailable for Python definition."""
        req = {
            "jsonrpc": "2.0", "id": 41, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_py",
                "arguments": {"path": "/x.py", "line": 0, "character": 0},
            },
        }
        result = self._rpc_no_path("py", req)["result"]
        _assert_mcp_envelope(result, label="ls-unavailable/py")
        assert result["isError"] is True
        err = json.loads(result["content"][0]["text"])
        assert err.get("error") == "ls-unavailable", (
            f"Expected error:'ls-unavailable', got: {err}"
        )


# ---------------------------------------------------------------------------
# AC-DIAG — diagnostics stub remains advisory (isError:false)
# ---------------------------------------------------------------------------

class TestDiagnosticsAdvisoryStub:
    """Diagnostics tool/call must return isError:false (advisory stub — no crash)."""

    def test_diagnostics_ts_is_not_error(self):
        req = {
            "jsonrpc": "2.0", "id": 50, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_diagnostics_ts",
                "arguments": {"path": "/x.ts"},
            },
        }
        result = _rpc("ts", req)["result"]
        _assert_mcp_envelope(result, label="diagnostics/ts")
        assert result["isError"] is False, (
            f"diagnostics_ts must be advisory (isError:false), got: {result}"
        )

    def test_diagnostics_py_is_not_error(self):
        req = {
            "jsonrpc": "2.0", "id": 51, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_diagnostics_py",
                "arguments": {"path": "/x.py"},
            },
        }
        result = _rpc("py", req)["result"]
        _assert_mcp_envelope(result, label="diagnostics/py")
        assert result["isError"] is False, (
            f"diagnostics_py must be advisory (isError:false), got: {result}"
        )

    def test_diagnostics_ts_returns_text_content(self):
        """Diagnostics content[0].text must be a non-empty string."""
        req = {
            "jsonrpc": "2.0", "id": 52, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_diagnostics_ts",
                "arguments": {"path": "/x.ts"},
            },
        }
        result = _rpc("ts", req)["result"]
        text = result["content"][0]["text"]
        assert text, "diagnostics_ts content[0].text must be non-empty"


# ---------------------------------------------------------------------------
# AC-ENV — envelope contract for all reply types
# ---------------------------------------------------------------------------

class TestMcpEnvelopeContract:
    """Every reply from tools/call must be {content:[{type:text,text}], isError:bool}."""

    def test_initialize_has_result_key(self):
        """initialize must return a JSON object with a 'result' key."""
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        reply = _rpc("ts", req)
        assert "result" in reply, f"initialize reply missing 'result': {reply}"

    def test_tools_list_reply_has_result_tools_key(self):
        """tools/list reply must have result.tools list."""
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        reply = _rpc("ts", req)
        assert "result" in reply
        assert "tools" in reply["result"], (
            f"tools/list result missing 'tools': {reply['result']}"
        )

    def test_tools_call_result_envelope_unsupported(self):
        """Even error replies for tools/call must use the content envelope."""
        req = {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "mcp_lsp_something_invalid", "arguments": {}},
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="envelope/unsupported")

    def test_tools_call_result_envelope_bad_args(self):
        """bad-args replies must also carry the content envelope."""
        req = {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_ts",
                "arguments": {},  # missing path, line, character
            },
        }
        reply = _rpc("ts", req)
        result = reply["result"]
        _assert_mcp_envelope(result, label="envelope/bad-args")
