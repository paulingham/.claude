"""AC3 — secrets allowlist forwarding for sandbox-verify.

`hooks/_lib/sandbox_secrets_allowlist.py:forward_env(allowlist) -> dict`:

- Empty allowlist → empty dict (default-deny is the safety property).
- Non-empty allowlist → only keys present in BOTH allowlist AND os.environ
  are returned. All other host env vars (`GITHUB_PERSONAL_ACCESS_TOKEN`,
  `ANTHROPIC_API_KEY`, ...) are stripped.
- Allowlist entries naming env vars that are unset → silently dropped.

Additive whitelist (not subtractive strip) per architect-context Finding A3
and code-archaeology recommendation: more auditable.

Env-var test hygiene per `learning/instincts/instinct-env-var-test-hygiene.md`:
use `patch.dict(os.environ, {}, clear=False)` + inner pop. Never bare
`os.environ.pop()`.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _load():
    from sandbox_secrets_allowlist import forward_env
    return forward_env


class EmptyAllowlistReturnsEmptyDict(unittest.TestCase):
    """C3 contract: empty allowlist → empty dict (default-deny)."""

    def test_empty_allowlist_returns_empty_dict(self):
        forward_env = _load()
        with patch.dict(os.environ, {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_x",
                                     "ANTHROPIC_API_KEY": "sk-ant-x"},
                        clear=False):
            result = forward_env([])
        self.assertEqual(result, {},
                         "empty allowlist must yield zero forwarded env vars")


class AllowlistStripsNonListedKeys(unittest.TestCase):
    """AC3: only allowlisted keys forwarded; non-listed keys stripped."""

    def test_forward_env_strips_non_allowlisted_keys(self):
        forward_env = _load()
        env_inject = {
            "DB_URL": "postgres://localhost/test",
            "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_secret",
            "ANTHROPIC_API_KEY": "sk-ant-secret",
        }
        with patch.dict(os.environ, env_inject, clear=False):
            result = forward_env(["DB_URL"])

        self.assertEqual(result, {"DB_URL": "postgres://localhost/test"})
        self.assertNotIn("GITHUB_PERSONAL_ACCESS_TOKEN", result)
        self.assertNotIn("ANTHROPIC_API_KEY", result)

    def test_unset_allowlisted_keys_silently_dropped(self):
        """Allowlist names DB_URL but it's not in env → not in result."""
        forward_env = _load()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DB_URL", None)
            result = forward_env(["DB_URL"])
        self.assertNotIn("DB_URL", result)

    def test_forward_env_returns_dict_type(self):
        """C3 contract shape: return type is dict[str, str]."""
        forward_env = _load()
        with patch.dict(os.environ, {"FOO": "bar"}, clear=False):
            result = forward_env(["FOO"])
        self.assertIsInstance(result, dict)
        for k, v in result.items():
            self.assertIsInstance(k, str)
            self.assertIsInstance(v, str)


if __name__ == "__main__":
    unittest.main()
