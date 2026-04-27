"""Unit tests for github-cache-server (lib helpers + server module)."""
import importlib.util
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
LIB_PATH = REPO / "hooks" / "_lib" / "github-cache-server-lib.py"
SERVER_PATH = REPO / "hooks" / "_lib" / "github-cache-server.py"


def _load(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _lib():
    return _load("gh_cache_lib", LIB_PATH)


def _server():
    return _load("gh_cache_server", SERVER_PATH)


class TestExtractPr(unittest.TestCase):
    def test_merge_with_pr_number(self):
        self.assertEqual(_lib().extract_pr_from_command("gh pr merge 47 --squash"), 47)

    def test_no_pr_returns_none(self):
        self.assertIsNone(_lib().extract_pr_from_command("gh repo view"))

    def test_view_with_pr_number(self):
        self.assertEqual(_lib().extract_pr_from_command("gh pr view 123"), 123)

    def test_pr_close_with_number(self):
        self.assertEqual(_lib().extract_pr_from_command("gh pr close 9"), 9)

    def test_only_first_pr_number_returned(self):
        # First PR number after `gh pr <verb>`
        self.assertEqual(_lib().extract_pr_from_command("gh pr merge 5 --body '#10'"), 5)


class TestExtractOwnerRepo(unittest.TestCase):
    def test_https_with_dot_git(self):
        self.assertEqual(
            _lib().extract_owner_repo("https://github.com/owner/repo.git"),
            ("owner", "repo"))

    def test_https_without_dot_git(self):
        self.assertEqual(
            _lib().extract_owner_repo("https://github.com/owner/repo"),
            ("owner", "repo"))

    def test_ssh_form(self):
        self.assertEqual(
            _lib().extract_owner_repo("git@github.com:owner/repo.git"),
            ("owner", "repo"))

    def test_unsupported_remote_returns_none(self):
        self.assertIsNone(_lib().extract_owner_repo("https://gitlab.com/x/y.git"))

    def test_blank_remote_returns_none(self):
        self.assertIsNone(_lib().extract_owner_repo(""))


class TestCacheDirFor(unittest.TestCase):
    def test_default_root(self):
        path = _lib().cache_dir_for("sess-1", 47)
        self.assertIn("sess-1-47", path)
        self.assertTrue(path.endswith("sess-1-47"))

    def test_custom_root_via_env(self):
        with mock.patch.dict(os.environ, {"CLAUDE_GH_CACHE_DIR": "/custom/root"}):
            path = _lib().cache_dir_for("abc", 9)
            self.assertEqual(path, "/custom/root/abc-9")

    def test_default_root_uses_xdg_cache_home(self):
        """M1: default cache root is ${XDG_CACHE_HOME}/claude/gh-pr."""
        env = {"XDG_CACHE_HOME": "/explicit/xdg"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("CLAUDE_GH_CACHE_DIR", None)
            path = _lib().cache_dir_for("s", 1)
        self.assertEqual(path, "/explicit/xdg/claude/gh-pr/s-1")

    def test_default_root_falls_back_to_home_cache(self):
        """M1: when XDG_CACHE_HOME unset, default is ~/.cache/claude/gh-pr."""
        with mock.patch.dict(os.environ, {"HOME": "/tmp/h-test"}, clear=False):
            os.environ.pop("CLAUDE_GH_CACHE_DIR", None)
            os.environ.pop("XDG_CACHE_HOME", None)
            path = _lib().cache_dir_for("s", 2)
        self.assertEqual(path, "/tmp/h-test/.cache/claude/gh-pr/s-2")

    def test_default_root_is_not_world_readable_tmp(self):
        """M1: insecure /tmp default is removed."""
        os.environ.pop("CLAUDE_GH_CACHE_DIR", None)
        path = _lib().cache_dir_for("s", 3)
        self.assertNotIn("/tmp/gh-pr-cache", path)


def _mock_url_open(payload_map):
    """Returns a urlopen replacement that responds per-URL."""
    def opener(req, timeout=None):
        url = req.get_full_url() if hasattr(req, "get_full_url") else req
        spec = payload_map.get(url) or payload_map.get("default")
        if spec is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        if isinstance(spec, Exception):
            raise spec
        return _Resp(spec)
    return opener


class _Resp:
    def __init__(self, body):
        self._body = body if isinstance(body, bytes) else body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class TestFetchPrData(unittest.TestCase):
    def setUp(self):
        os.environ.pop("_TEST_GH_API_BASE", None)
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "test-token"

    def tearDown(self):
        os.environ.pop("GITHUB_PERSONAL_ACCESS_TOKEN", None)
        os.environ.pop("_TEST_GH_API_BASE", None)

    def test_success_returns_view_diff_files(self):
        view_body = json.dumps({"number": 47, "title": "x"})
        files_body = json.dumps([{"filename": "a.txt"}, {"filename": "b.txt"}])
        urls = {
            "https://api.github.com/repos/o/r/pulls/47": view_body,
            "https://api.github.com/repos/o/r/pulls/47/files": files_body,
            "default": "diff-content",
        }
        with mock.patch("urllib.request.urlopen", side_effect=_mock_url_open(urls)):
            result = _server()._fetch_pr_data("o", "r", 47)
        self.assertTrue(result["ok"])
        self.assertIn("view", result)
        self.assertIn("diff", result)
        self.assertIn("files", result)

    def test_404_returns_ok_false(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.HTTPError("u", 404, "x", None, None)):
            result = _server()._fetch_pr_data("o", "r", 9)
        self.assertFalse(result["ok"])
        self.assertIn("reason", result)

    def test_timeout_returns_ok_false(self):
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError()):
            result = _server()._fetch_pr_data("o", "r", 9)
        self.assertFalse(result["ok"])
        self.assertIn("reason", result)

    def test_url_error_returns_ok_false(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("dns")):
            result = _server()._fetch_pr_data("o", "r", 9)
        self.assertFalse(result["ok"])

    def test_api_base_via_module_constant_patch(self):
        """Tests can patch _API_BASE constant on the fetch module to redirect URLs.

        SSRF guard: this is the ONLY supported test seam. The previous
        _TEST_GH_API_BASE env override has been removed because it allowed
        attacker-controlled env to exfiltrate the GitHub token.
        """
        srv = _server()
        seen_urls = []

        def capturing(req, timeout=None):
            url = req.get_full_url() if hasattr(req, "get_full_url") else req
            seen_urls.append(url)
            return _Resp("[]" if url.endswith("/files") else "{}")

        with mock.patch.object(srv._fetch, "_API_BASE", "http://localhost:8080"), \
             mock.patch("urllib.request.urlopen", side_effect=capturing):
            srv._fetch_pr_data("o", "r", 1)
        self.assertTrue(any(u.startswith("http://localhost:8080") for u in seen_urls))


class TestServerEnvGuards(unittest.TestCase):
    def test_no_token_returns_ok_false(self):
        os.environ.pop("GITHUB_PERSONAL_ACCESS_TOKEN", None)
        called = []
        with mock.patch("urllib.request.urlopen",
                        side_effect=lambda *a, **k: called.append(1) or _Resp("{}")):
            result = _server()._fetch_pr_data("o", "r", 1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no token")
        self.assertEqual(called, [])


class TestJsonRpcDispatch(unittest.TestCase):
    def test_initialize_tools_list_call(self):
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "t"
        os.environ["CLAUDE_SESSION_ID"] = "sess-rpc"
        srv = _server()
        reqs = (
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n"
            + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
        stdin, stdout = io.StringIO(reqs), io.StringIO()
        srv.serve(stdin, stdout)
        lines = [json.loads(ln) for ln in stdout.getvalue().splitlines() if ln]
        self.assertEqual(lines[0]["result"]["serverInfo"]["name"], "gh-cache")
        self.assertEqual(lines[1]["result"]["tools"][0]["name"], "prefetch_pr")


class TestPrefetchToolWritesCache(unittest.TestCase):
    def test_writes_cache_files_with_complete_last(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "t"
            os.environ["CLAUDE_SESSION_ID"] = "sxx"
            os.environ["CLAUDE_GH_CACHE_DIR"] = tmp
            os.environ["_TEST_GH_OWNER_REPO"] = "o/r"
            urls = {
                "https://api.github.com/repos/o/r/pulls/47": json.dumps({"number": 47}),
                "https://api.github.com/repos/o/r/pulls/47/files": json.dumps([{"filename": "a.py"}]),
                "default": "diff-body",
            }
            with mock.patch("urllib.request.urlopen", side_effect=_mock_url_open(urls)):
                req = json.dumps({"jsonrpc": "2.0", "id": 9,
                                  "method": "tools/call",
                                  "params": {"name": "prefetch_pr",
                                             "arguments": {"command": "gh pr merge 47 --squash"}}}) + "\n"
                stdin, stdout = io.StringIO(req), io.StringIO()
                _server().serve(stdin, stdout)
            cache_dir = Path(tmp) / "sxx-47"
            self.assertTrue((cache_dir / "view.json").exists())
            self.assertTrue((cache_dir / "diff.patch").exists())
            self.assertTrue((cache_dir / "files.txt").exists())
            self.assertTrue((cache_dir / ".complete").exists())


class TestPrefetchToolNoPrNumber(unittest.TestCase):
    def test_returns_ok_false_when_no_pr(self):
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "t"
        os.environ["CLAUDE_SESSION_ID"] = "sno"
        req = json.dumps({"jsonrpc": "2.0", "id": 1,
                          "method": "tools/call",
                          "params": {"name": "prefetch_pr",
                                     "arguments": {"command": "gh repo view"}}}) + "\n"
        stdin, stdout = io.StringIO(req), io.StringIO()
        _server().serve(stdin, stdout)
        resp = json.loads(stdout.getvalue().strip())
        env = json.loads(resp["result"]["content"][0]["text"])
        self.assertFalse(env["ok"])
        self.assertIn("no PR number", env["reason"])


if __name__ == "__main__":
    unittest.main()
