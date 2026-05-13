"""AC1 + AC4 — E2B microVM client (urllib wrapper, NOT e2b PyPI SDK).

`hooks/_lib/sandbox_e2b_client.py`:

- `_API_BASE = "https://api.e2b.dev"` SSRF guard constant.
- `_open(url, accept, body, timeout=8)` mirrors github-cache `_open`.
- `provision_microvm(template) -> {"ok": bool, "reason": str?,
   "microvm_id": str?, "started_at": float?, "attempts": int}` — C1 contract.
- `exec_in_microvm(microvm_id, command, env) -> {"ok": bool, "stdout": str,
   "stderr": str, "exit_code": int}`.
- `destroy_microvm(microvm_id) -> {"ok": bool}`.

AC4: retry-once-then-skip on `(TimeoutError, urllib.error.URLError,
E2BProvisionError)`. Narrow catch per
`learning/{hash}/instincts/instinct-subprocess-timeout-expired.md`.

Tests mock `urllib.request.urlopen`; NO live E2B calls.
"""
import json
import os
import sys
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _load():
    import sandbox_e2b_client
    return sandbox_e2b_client


def _fake_response(payload, status=201):
    """Build a fake urlopen context-manager that yields `payload`."""
    body = json.dumps(payload).encode("utf-8")
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock(
        read=MagicMock(return_value=body),
        status=status))
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


class ProvisionHappyPathReturnsOkEnvelope(unittest.TestCase):
    """AC1: 201 from E2B → {"ok": True, "microvm_id": ..., ...}."""

    def test_provision_microvm_returns_ok_envelope_on_success(self):
        mod = _load()
        fake_payload = {"sandboxID": "vm_abc123", "templateID": "default"}

        with patch.dict(os.environ, {"E2B_API_KEY": "e2b_test_token"},
                        clear=False):
            with patch.object(mod.urllib.request, "urlopen",
                              return_value=_fake_response(fake_payload)):
                result = mod.provision_microvm(template="default")

        self.assertTrue(result["ok"])
        self.assertEqual(result["microvm_id"], "vm_abc123")
        self.assertIn("started_at", result)
        self.assertEqual(result["attempts"], 1)

    def test_provision_returns_skip_when_token_missing(self):
        """No E2B_API_KEY → fast-fail with {"ok": False,
        "reason": "no-e2b-token"} matching the github-cache token-missing
        precedent."""
        mod = _load()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("E2B_API_KEY", None)
            result = mod.provision_microvm(template="default")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no-e2b-token")


class ProvisionRetriesOnceThenSkips(unittest.TestCase):
    """AC4: transient failure → one retry → second failure → SANDBOX_SKIPPED
    with reason `e2b-unavailable`, attempts=2."""

    def test_provision_retries_once_then_skips(self):
        mod = _load()
        # urlopen raises URLError twice in a row → retry once → skip.
        call_count = {"n": 0}

        def raising_urlopen(*args, **kwargs):
            call_count["n"] += 1
            raise urllib.error.URLError("connection refused")

        with patch.dict(os.environ, {"E2B_API_KEY": "e2b_test_token"},
                        clear=False):
            with patch.object(mod.urllib.request, "urlopen",
                              side_effect=raising_urlopen):
                with patch.object(mod.time, "sleep"):  # skip backoff
                    result = mod.provision_microvm(template="default")

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "e2b-unavailable")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(call_count["n"], 2,
                         "must call urlopen exactly twice (1 try + 1 retry)")

    def test_provision_succeeds_after_one_retry(self):
        """First call URLError, second call succeeds → ok=True, attempts=2."""
        mod = _load()
        responses = [urllib.error.URLError("temp"),
                     _fake_response({"sandboxID": "vm_retry_x"})]

        def urlopen_side_effect(*args, **kwargs):
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with patch.dict(os.environ, {"E2B_API_KEY": "e2b_test_token"},
                        clear=False):
            with patch.object(mod.urllib.request, "urlopen",
                              side_effect=urlopen_side_effect):
                with patch.object(mod.time, "sleep"):
                    result = mod.provision_microvm(template="default")

        self.assertTrue(result["ok"])
        self.assertEqual(result["microvm_id"], "vm_retry_x")
        self.assertEqual(result["attempts"], 2)


class ProvisionTimeoutClassifiedNarrowly(unittest.TestCase):
    """TimeoutError → reason=e2b-unavailable (narrow catch per instinct)."""

    def test_timeout_classified_as_e2b_unavailable(self):
        mod = _load()

        with patch.dict(os.environ, {"E2B_API_KEY": "e2b_test_token"},
                        clear=False):
            with patch.object(mod.urllib.request, "urlopen",
                              side_effect=TimeoutError("timeout")):
                with patch.object(mod.time, "sleep"):
                    result = mod.provision_microvm(template="default")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "e2b-unavailable")


class DestroyMicrovmCallsApi(unittest.TestCase):
    """teardown contract: destroy_microvm calls the API once."""

    def test_destroy_microvm_returns_ok_on_success(self):
        mod = _load()
        with patch.dict(os.environ, {"E2B_API_KEY": "e2b_test_token"},
                        clear=False):
            with patch.object(mod.urllib.request, "urlopen",
                              return_value=_fake_response({}, status=204)):
                result = mod.destroy_microvm("vm_abc123")
        self.assertTrue(result["ok"])


class ApiBaseIsSsrfHardened(unittest.TestCase):
    """SSRF guard: _API_BASE is a hardcoded module constant, no env override."""

    def test_api_base_is_module_constant(self):
        mod = _load()
        self.assertEqual(mod._API_BASE, "https://api.e2b.dev",
                         "SSRF guard: API base must be hardcoded")


if __name__ == "__main__":
    unittest.main()
