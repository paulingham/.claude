"""AC1 + AC4 — E2B microVM HTTP client (stdlib urllib, NOT the e2b PyPI SDK).

Mirrors `hooks/_lib/github-cache-server-fetch.py` byte-shape (the only
external-HTTP precedent in `hooks/_lib/`):

- `_API_BASE = "https://api.e2b.dev"` — hardcoded SSRF guard; no env override.
- `_open(url, accept, body, timeout=8)` — stdlib `urllib.request`.
- Token from `os.environ["E2B_API_KEY"]`; missing → fast-fail `{"ok": False,
  "reason": "no-e2b-token"}` (matches github-cache token-missing precedent).
- Narrow exception catch: `(TimeoutError, urllib.error.URLError,
  E2BProvisionError)` — per the subprocess-timeout-expired instinct.
- `{"ok": bool, "reason": str?, ...}` return envelope.

AC4 retry-once: `provision_microvm` catches the narrow tuple, sleeps 2s,
retries once. Second failure → `{"ok": False, "reason": "e2b-unavailable",
"attempts": 2}`. With max retries=1, "exponential backoff" degenerates to a
single sleep — base delay 2s, documented per architect-context Finding A4.

Wire-format parsing is confined to `_parse_provision_response` so the
single piece of `<unverified>` E2B-wire knowledge lives in one place.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

_API_BASE = "https://api.e2b.dev"  # SSRF guard: no env override.
_JSON = "application/json"
_DEFAULT_TIMEOUT_S = 8
_RETRY_BACKOFF_S = 2.0


class E2BProvisionError(Exception):
    """Raised when E2B returns a non-2xx status the wrapper cannot recover."""


def _open(url: str, accept: str, body: bytes | None = None,
          method: str | None = None, timeout: int = _DEFAULT_TIMEOUT_S) -> str:
    """Issue a single HTTP request with token auth + narrow timeout.

    Mirrors `github-cache-server-fetch.py:_open` byte-for-byte; the only
    delta is the second positional `body` argument for POST/DELETE calls
    that E2B requires (github-cache is GET-only).
    """
    token = os.environ["E2B_API_KEY"]
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Authorization": f"Bearer {token}", "Accept": accept,
                 "Content-Type": _JSON})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _classify(exc: Exception) -> str:
    """Map a caught exception to the SANDBOX_SKIPPED reason enum.

    Narrow per the instinct: timeouts vs URLErrors both map to
    `e2b-unavailable` (the skip-reason consumer doesn't distinguish), so
    the function exists to lock the catch surface.
    """
    if isinstance(exc, (TimeoutError, urllib.error.URLError,
                        E2BProvisionError)):
        return "e2b-unavailable"
    return "unknown"


def _parse_provision_response(payload: str) -> dict:
    """Extract `microvm_id` from the E2B provision response body.

    <unverified> Wire format: `{"sandboxID": "...", "templateID": "..."}`.
    All `<unverified>` E2B-API knowledge is confined to this function so
    Story 4's canary (CLAUDE_E2B_LIVE_PROBE=1) can flip a single shape
    when the real wire format diverges.
    """
    data = json.loads(payload)
    microvm_id = data.get("sandboxID") or data.get("id") or ""
    return {"microvm_id": microvm_id}


def provision_microvm(template: str = "default") -> dict:
    """Provision a microVM with one-retry-then-skip.

    Returns C1 envelope: `{"ok": bool, "reason": str?, "microvm_id": str?,
    "started_at": float?, "attempts": int}`.
    """
    if not os.environ.get("E2B_API_KEY"):
        return {"ok": False, "reason": "no-e2b-token", "attempts": 0}

    return _provision_with_one_retry(template)


def _provision_with_one_retry(template: str) -> dict:
    """Inner retry-once loop. Extracted for cohesion (CC ≤ 5)."""
    body = json.dumps({"templateID": template}).encode("utf-8")
    url = f"{_API_BASE}/sandboxes"
    last_reason = "e2b-unavailable"

    for attempt in (1, 2):
        try:
            payload = _open(url, _JSON, body=body, method="POST")
            parsed = _parse_provision_response(payload)
            return {"ok": True, "microvm_id": parsed["microvm_id"],
                    "started_at": time.time(), "attempts": attempt}
        except (TimeoutError, urllib.error.URLError,
                E2BProvisionError) as exc:
            last_reason = _classify(exc)
            if attempt == 1:
                time.sleep(_RETRY_BACKOFF_S)
    return {"ok": False, "reason": last_reason, "attempts": 2}


def exec_in_microvm(microvm_id: str, command: str,
                    env: dict[str, str] | None = None) -> dict:
    """Execute `command` inside the microVM with allowlisted env.

    Returns `{"ok": bool, "stdout": str, "stderr": str, "exit_code": int}`.
    Network errors → `{"ok": False, "stdout": "", "stderr": str(exc),
    "exit_code": -1}` so the caller can route to teardown without raising.
    """
    body = json.dumps({"cmd": command, "envs": env or {}}).encode("utf-8")
    url = f"{_API_BASE}/sandboxes/{microvm_id}/exec"
    try:
        payload = _open(url, _JSON, body=body, method="POST")
        data = json.loads(payload)
        return {"ok": True, "stdout": data.get("stdout", ""),
                "stderr": data.get("stderr", ""),
                "exit_code": int(data.get("exitCode", 0))}
    except (TimeoutError, urllib.error.URLError) as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc),
                "exit_code": -1}


def destroy_microvm(microvm_id: str) -> dict:
    """Tear down the microVM. Always returns `{"ok": bool, "reason": str?}`.

    Teardown failures are non-fatal — the caller MUST still emit verdict
    and write the teardown JSONL line; this function's job is to attempt
    the delete and report what happened.
    """
    url = f"{_API_BASE}/sandboxes/{microvm_id}"
    try:
        _open(url, _JSON, method="DELETE")
        return {"ok": True}
    except (TimeoutError, urllib.error.URLError) as exc:
        return {"ok": False, "reason": _classify(exc)}
