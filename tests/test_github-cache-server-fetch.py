"""Tests for the urllib + cache-write module."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
FETCH_PATH = REPO / "hooks" / "_lib" / "github-cache-server-fetch.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _Resp:
    def __init__(self, body):
        self._body = body.encode("utf-8") if isinstance(body, str) else body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class TestFetchEnvGuards(unittest.TestCase):
    def setUp(self):
        self.fetch = _load("gh_cache_fetch", FETCH_PATH)

    def test_no_token_returns_ok_false_without_network(self):
        os.environ.pop("GITHUB_PERSONAL_ACCESS_TOKEN", None)
        with mock.patch("urllib.request.urlopen") as opener:
            result = self.fetch.fetch_pr_data("o", "r", 1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no token")
        opener.assert_not_called()


class TestFetchHttpPaths(unittest.TestCase):
    def setUp(self):
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "t"
        self.fetch = _load("gh_cache_fetch", FETCH_PATH)

    def tearDown(self):
        os.environ.pop("_TEST_GH_API_BASE", None)

    def test_success(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=lambda req, timeout=None: _Resp("{}")):
            result = self.fetch.fetch_pr_data("o", "r", 1)
        self.assertTrue(result["ok"])
        # view goes through JSON reshape; result is canonical gh-CLI shape JSON.
        self.assertEqual(json.loads(result["view"]),
                         {"mergedAt": None,
                          "mergeCommit": {"oid": ""},
                          "labels": []})

    def test_timeout(self):
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError()):
            result = self.fetch.fetch_pr_data("o", "r", 1)
        self.assertEqual(result["reason"], "timeout")

    def test_url_error(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("nope")):
            result = self.fetch.fetch_pr_data("o", "r", 1)
        self.assertEqual(result["reason"], "http error")

    def test_api_base_via_module_constant_patch(self):
        seen = []

        def capture(req, timeout=None):
            seen.append(req.get_full_url())
            return _Resp("{}")

        with mock.patch.object(self.fetch, "_API_BASE", "http://localhost:9999"), \
             mock.patch("urllib.request.urlopen", side_effect=capture):
            self.fetch.fetch_pr_data("o", "r", 5)
        self.assertTrue(seen and all(u.startswith("http://localhost:9999") for u in seen))

    def test_test_env_var_does_not_redirect_url(self):
        """SSRF guard: _TEST_GH_API_BASE env override is removed."""
        os.environ["_TEST_GH_API_BASE"] = "http://attacker.example"
        seen = []

        def capture(req, timeout=None):
            seen.append(req.get_full_url())
            return _Resp("{}")

        with mock.patch("urllib.request.urlopen", side_effect=capture):
            self.fetch.fetch_pr_data("o", "r", 5)
        for url in seen:
            self.assertFalse(url.startswith("http://attacker.example"),
                             f"env var redirected to attacker host: {url}")
            self.assertTrue(url.startswith("https://api.github.com"),
                            f"expected api.github.com, got {url}")


class TestWriteCache(unittest.TestCase):
    def test_writes_four_files_complete_last(self):
        fetch = _load("gh_cache_fetch", FETCH_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "x"
            fetch.write_cache(str(target), "v", "d", "f")
            self.assertEqual((target / "view.json").read_text(), "v")
            self.assertEqual((target / "diff.patch").read_text(), "d")
            self.assertEqual((target / "files.txt").read_text(), "f")
            self.assertTrue((target / ".complete").exists())


def _rest_view_body():
    return json.dumps({
        "number": 47,
        "title": "T",
        "body": "B",
        "merged_at": "2026-04-15T12:34:56Z",
        "merge_commit_sha": "deadbeef00",
        "labels": [{"name": "bug", "color": "f00", "description": "bug"}],
    })


class TestRestToGhShapeReshape(unittest.TestCase):
    """C1: Server reshapes REST API responses into gh-CLI shape."""

    def setUp(self):
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "t"
        self.fetch = _load("gh_cache_fetch", FETCH_PATH)

    def _opener(self, payloads_by_accept):
        def opener(req, timeout=None):
            accept = req.headers.get("Accept", "")
            return _Resp(payloads_by_accept.get(accept, "{}"))
        return opener

    def test_view_reshaped_mergedAt_camelCase(self):
        opener = self._opener({"application/vnd.github+json": _rest_view_body(),
                               "application/vnd.github.v3.diff": "diff body"})
        with mock.patch("urllib.request.urlopen", side_effect=opener):
            result = self.fetch.fetch_pr_data("o", "r", 47)
        view = json.loads(result["view"])
        self.assertEqual(view["mergedAt"], "2026-04-15T12:34:56Z")
        self.assertNotIn("merged_at", view)

    def test_view_reshaped_mergeCommit_oid(self):
        opener = self._opener({"application/vnd.github+json": _rest_view_body(),
                               "application/vnd.github.v3.diff": "diff body"})
        with mock.patch("urllib.request.urlopen", side_effect=opener):
            result = self.fetch.fetch_pr_data("o", "r", 47)
        view = json.loads(result["view"])
        self.assertEqual(view["mergeCommit"], {"oid": "deadbeef00"})
        self.assertNotIn("merge_commit_sha", view)


if __name__ == "__main__":
    unittest.main()
