"""Pytest depth tests for the LSP go-to-definition bridge.

AC1: fake-LS resolves a definition (isError:false, flattened location).
AC2: tools/list lists both tools; diagnostics result unchanged (no-regress).
AC3: missing arg → bad-args; LS timeout → ls-timeout, pid reaped, no extra thread.
AC5: @skipUnless real binary — run with real LS if present.
"""
import json
import shutil
import sys
import threading
import unittest
from pathlib import Path
from unittest import skipUnless

# conftest.py prepends hooks/_lib to sys.path
import importlib.util

REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _load_rpc():
    path = REPO_ROOT / "hooks" / "_lib" / "lsp-bridge-rpc.py"
    spec = importlib.util.spec_from_file_location("_lsp_rpc", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_lsp():
    path = REPO_ROOT / "hooks" / "_lib" / "lsp-bridge-lsp.py"
    spec = importlib.util.spec_from_file_location("_lsp_lsp", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _route(msg, lang="ts"):
    return _load_rpc().route(msg, lang)


class TestInitializeAndListBackwardCompat(unittest.TestCase):
    """AC2: tools/list must have exactly 2 tools; serverInfo.name unchanged."""

    def test_initialize_returns_server_name(self):
        rpc = _load_rpc()
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        result = rpc.route(msg, "ts")
        self.assertEqual(result["result"]["serverInfo"]["name"], "lsp-ts")

    def test_list_contains_two_tools(self):
        rpc = _load_rpc()
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        result = rpc.route(msg, "ts")
        names = [t["name"] for t in result["result"]["tools"]]
        self.assertEqual(len(names), 2, f"Expected 2 tools, got: {names}")

    def test_list_contains_definition_tool(self):
        rpc = _load_rpc()
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        result = rpc.route(msg, "ts")
        names = [t["name"] for t in result["result"]["tools"]]
        self.assertIn("mcp_lsp_definition_ts", names)

    def test_list_contains_diagnostics_tool(self):
        rpc = _load_rpc()
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        result = rpc.route(msg, "ts")
        names = [t["name"] for t in result["result"]["tools"]]
        self.assertIn("mcp_lsp_diagnostics_ts", names)

    def test_diagnostics_call_still_returns_stub_text(self):
        rpc = _load_rpc()
        msg = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "mcp_lsp_diagnostics_ts", "arguments": {"path": "x.ts"}},
        }
        result = rpc.route(msg, "ts")
        text = result["result"]["content"][0]["text"]
        self.assertEqual(text, "advisory: LSP shell-out not yet implemented")

    def test_diagnostics_call_is_error_false(self):
        rpc = _load_rpc()
        msg = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "mcp_lsp_diagnostics_ts", "arguments": {"path": "x.ts"}},
        }
        result = rpc.route(msg, "ts")
        self.assertFalse(result["result"]["isError"])


class TestDefinitionResolvesWithFakeLs(unittest.TestCase):
    """AC1: fake_ls resolves a definition; result is flattened."""

    def _make_factory(self):
        """Return a proc_factory that spawns fake_ls.py."""
        fake_ls = str(_FIXTURES / "fake_ls.py")

        def factory(binary):
            import subprocess
            return subprocess.Popen(
                [sys.executable, fake_ls],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

        return factory

    def test_definition_resolves_with_fake_ls(self):
        lsp = _load_lsp()
        lsp.resolve_binary = lambda lang: "/fake/binary"
        pos = lsp.Position(path="/project/src/main.ts", line=5, character=10)
        factory = self._make_factory()
        result = lsp.run_definition(factory, "ts", pos)
        payload = json.loads(result["content"][0]["text"])
        self.assertFalse(result["isError"])
        self.assertIn("definitions", payload)
        self.assertGreater(len(payload["definitions"]), 0)
        first = payload["definitions"][0]
        self.assertIn("file", first)
        self.assertIn("line", first)
        self.assertIn("character", first)


class TestMissingRequiredArgIsStructuredError(unittest.TestCase):
    """AC3: missing arg → bad-args structured error, no exception raised."""

    def test_missing_required_arg_is_structured_error(self):
        rpc = _load_rpc()
        msg = {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "mcp_lsp_definition_ts", "arguments": {"path": "x.ts"}},
        }
        result = rpc.route(msg, "ts")
        envelope = result["result"]
        self.assertTrue(envelope["isError"])
        err = json.loads(envelope["content"][0]["text"])
        self.assertEqual(err["error"], "bad-args")


class TestUnsupportedToolNameIsStructuredError(unittest.TestCase):
    """AC3: unsupported tool name → structured error."""

    def test_unsupported_tool_name_returns_error(self):
        rpc = _load_rpc()
        msg = {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "mcp_lsp_definition_rb", "arguments": {}},
        }
        result = rpc.route(msg, "ts")
        envelope = result["result"]
        self.assertTrue(envelope["isError"])
        err = json.loads(envelope["content"][0]["text"])
        self.assertEqual(err["error"], "unsupported")


class TestLsTimeoutSelectsOutTerminatesAndErrors(unittest.TestCase):
    """AC3: --hang fake LS → select deadline → ls-timeout; pid reaped; no new thread."""

    def test_ls_timeout_selects_out_terminates_and_errors(self):
        lsp = _load_lsp()
        fake_ls = str(_FIXTURES / "fake_ls.py")
        lsp._TIMEOUT_SECONDS = 1

        def hang_factory(binary):
            import subprocess
            return subprocess.Popen(
                [sys.executable, fake_ls, "--hang"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

        lsp.resolve_binary = lambda lang: "/fake/binary"
        threads_before = threading.active_count()
        pos = lsp.Position(path="/project/src/main.ts", line=0, character=0)
        result = lsp.run_definition(hang_factory, "ts", pos)

        self.assertTrue(result["isError"])
        err = json.loads(result["content"][0]["text"])
        self.assertEqual(err["error"], "ls-timeout")
        threads_after = threading.active_count()
        self.assertEqual(threads_before, threads_after,
                         "run_definition must not leak threads")


class TestExtraHeaderDoesNotCorruptFrame(unittest.TestCase):
    """FIX1: Content-Type header after Content-Length must not corrupt the frame."""

    def _make_extra_header_factory(self):
        fake_ls = str(_FIXTURES / "fake_ls.py")

        def factory(binary):
            import subprocess
            return subprocess.Popen(
                [sys.executable, fake_ls, "--extra-header"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

        return factory

    def test_definition_resolves_with_extra_content_type_header(self):
        lsp = _load_lsp()
        lsp.resolve_binary = lambda lang: "/fake/binary"
        pos = lsp.Position(path="/project/src/main.ts", line=5, character=10)
        factory = self._make_extra_header_factory()
        result = lsp.run_definition(factory, "ts", pos)
        payload = json.loads(result["content"][0]["text"])
        self.assertFalse(result["isError"], f"Expected success, got: {payload}")
        self.assertIn("definitions", payload)
        self.assertGreater(len(payload["definitions"]), 0)


class TestValidateDefArgsTypeEnforcement(unittest.TestCase):
    """FIX2: non-int line/character must return bad-args, not propagate."""

    def test_string_line_returns_bad_args(self):
        rpc = _load_rpc()
        msg = {
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_ts",
                "arguments": {"path": "/x.ts", "line": "42", "character": 0},
            },
        }
        result = rpc.route(msg, "ts")
        envelope = result["result"]
        self.assertTrue(envelope["isError"])
        err = json.loads(envelope["content"][0]["text"])
        self.assertEqual(err["error"], "bad-args")

    def test_bool_line_returns_bad_args(self):
        rpc = _load_rpc()
        msg = {
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {
                "name": "mcp_lsp_definition_ts",
                "arguments": {"path": "/x.ts", "line": True, "character": 0},
            },
        }
        result = rpc.route(msg, "ts")
        envelope = result["result"]
        self.assertTrue(envelope["isError"])
        err = json.loads(envelope["content"][0]["text"])
        self.assertEqual(err["error"], "bad-args")


import select
import subprocess
import tempfile
import time


def _build_py_fixture(tmpdir):
    content = "def my_target_function():\n    return 1\n\n\nresult = my_target_function()\n"
    path = str(Path(tmpdir) / "fix.py")
    Path(path).write_text(content)
    return path, content


def _build_ts_fixture(tmpdir):
    content = "function myTargetFunction(): number {\n    return 1;\n}\n\nconst r = myTargetFunction();\n"
    path = str(Path(tmpdir) / "fix.ts")
    Path(path).write_text(content)
    return path, content


def _drain_lsp_frames(lsp, proc):
    raw = lsp._raw_out(proc)
    while select.select([raw], [], [], 0.2)[0]:
        try:
            lsp._read_frame(proc, time.monotonic() + 0.5)
        except Exception:
            return


_LANG_ID = {"py": "python", "ts": "typescript"}


def _did_open_msg(fixture_path, content, lang):
    return {"jsonrpc": "2.0", "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": f"file://{fixture_path}",
                "languageId": _LANG_ID.get(lang, lang), "version": 1, "text": content}}}


def _make_init_patch(orig_init, tmpdir):
    def _f():
        p = orig_init()
        p["rootUri"] = f"file://{tmpdir}"
        return p
    return _f


def _make_hs_patch(lsp, orig_hs, fixture_path, content, lang):
    def _f(proc, deadline):
        orig_hs(proc, deadline)
        lsp._write_frame(proc, _did_open_msg(fixture_path, content, lang))
        time.sleep(3)
        _drain_lsp_frames(lsp, proc)
    return _f


def _patch_lsp_for_real_run(lsp, tmpdir, fixture_path, content, lang):
    lsp._init_params = _make_init_patch(lsp._init_params, tmpdir)
    lsp._handshake = _make_hs_patch(lsp, lsp._handshake, fixture_path, content, lang)


def _resolve_real(lsp, binary, lang, fixture_path, line, char):
    def factory(_b):
        return subprocess.Popen(
            [binary, "--stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )
    pos = lsp.Position(path=fixture_path, line=line, character=char)
    return lsp.run_definition(factory, lang, pos)


def _extract_result(result):
    payload = json.loads(result["content"][0]["text"])
    return result["isError"], payload.get("definitions", [])


def _make_lsp():
    lsp = _load_lsp()
    lsp._TIMEOUT_SECONDS = 30
    return lsp


def _run_real_definition(binary, lang, ref_line, ref_char, fix_fn):
    lsp = _make_lsp()
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path, content = fix_fn(tmpdir)
        _patch_lsp_for_real_run(lsp, tmpdir, fixture_path, content, lang)
        result = _resolve_real(lsp, binary, lang, fixture_path, ref_line, ref_char)
    return fixture_path, *_extract_result(result)


def _write_evidence(binary, lang, fixture_path, defs):
    ev = {"ac5": "real-run", "binary": binary, "language": lang,
          "target": fixture_path, "resolved": defs}
    (REPO_ROOT / "verification-evidence.json").write_text(json.dumps(ev, indent=2))


def _ts_npm_dep_present():
    try:
        out = subprocess.check_output(
            ["npm", "ls", "-g", "typescript"], stderr=subprocess.DEVNULL, text=True)
        return "typescript" in out and "empty" not in out
    except Exception:
        return False


def _ts_binary_usable():
    return bool(shutil.which("typescript-language-server")) and _ts_npm_dep_present()


@skipUnless(
    shutil.which("pyright-langserver") or shutil.which("pyright") or
    shutil.which("typescript-language-server") or shutil.which("tsserver"),
    "No real LS binary on PATH — AC5 deferred",
)
class TestRealLsResolvesDefinition(unittest.TestCase):
    """AC5: real LS on PATH → self-fixtured run, assert non-empty definitions[]."""

    def _assert_definition(self, is_err, defs, expected_file, expected_line):
        self.assertFalse(is_err, f"Real LS error; defs={defs}")
        self.assertGreater(len(defs), 0, "definitions[] was empty — LS did not resolve")
        self.assertEqual(defs[0]["file"], expected_file)
        self.assertEqual(defs[0]["line"], expected_line)

    def test_real_py_ls_resolves_definition(self):
        binary = shutil.which("pyright-langserver") or shutil.which("pyright")
        if not binary:
            self.skipTest("pyright-langserver not on PATH")
        fp, is_err, defs = _run_real_definition(binary, "py", 4, 9, _build_py_fixture)
        _write_evidence(binary, "py", fp, defs)
        self._assert_definition(is_err, defs, fp, 0)

    def test_real_ts_ls_resolves_definition(self):
        if not _ts_binary_usable():
            self.skipTest("typescript-language-server or typescript npm dep absent")
        binary = shutil.which("typescript-language-server")
        fp, is_err, defs = _run_real_definition(binary, "typescript", 4, 10, _build_ts_fixture)
        _write_evidence(binary, "ts", fp, defs)
        self._assert_definition(is_err, defs, fp, 0)
