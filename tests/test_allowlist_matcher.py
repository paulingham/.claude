"""AC3, AC4: allowlist matcher — file-glob + content-regex detection."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))

from capture._lib import allowlist_loader, allowlist_matcher  # noqa: E402


def _allow(globs=(), regexes=()):
    return allowlist_loader.Allowlist(
        file_globs=tuple(globs),
        content_regexes=tuple(re.compile(r) for r in regexes))


class FileGlobMatchesBasename(unittest.TestCase):
    """AC3: *.env pattern matches .env, .env.local, prod.env."""
    def test_env_glob_matches_dotenv(self):
        allow = _allow(globs=("*.env", ".env", ".env.*"))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": ".env"}, allow=allow))

    def test_env_glob_matches_env_local(self):
        allow = _allow(globs=(".env.*",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": ".env.local"}, allow=allow))

    def test_env_glob_matches_nested_path(self):
        allow = _allow(globs=("*.env",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": "config/prod.env"}, allow=allow))


class FileGlobMatchesFullPath(unittest.TestCase):
    """Paths like .aws/credentials matched by full-path pattern."""
    def test_aws_credentials_matches(self):
        allow = _allow(globs=(".aws/credentials",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": "home/user/.aws/credentials"}, allow=allow))


class FileGlobWithSlashMatchesAnywhere(unittest.TestCase):
    """H1 regression: globs containing `/` and `*` must match nested paths."""
    def test_ssh_glob_matches_absolute_home_path(self):
        allow = _allow(globs=(".ssh/*",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": "/Users/someone/.ssh/id_rsa"}, allow=allow))

    def test_ssh_glob_matches_home_config(self):
        allow = _allow(globs=(".ssh/*",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": "/home/bar/.ssh/config"}, allow=allow))

    def test_aws_sso_cache_matches_nested_json(self):
        allow = _allow(globs=(".aws/sso/cache/*.json",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": "/Users/x/.aws/sso/cache/abc123.json"}, allow=allow))

    def test_secrets_pem_matches_nested(self):
        allow = _allow(globs=("secrets/*.pem",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": "/repo/secrets/key.pem"}, allow=allow))

    def test_ssh_glob_does_not_match_unrelated_dir(self):
        allow = _allow(globs=(".ssh/*",))
        self.assertFalse(allowlist_matcher.is_private(
            obj={"file": "/tmp/notssh/file"}, allow=allow))


class NormalizedPathStillMatches(unittest.TestCase):
    """Gap 10: matcher must normalize the path before fnmatch checks.

    `./x/.env`, `x/./.env`, and `x/y/../.env` are all equivalent to a
    path ending in `.env` and must match a basename glob. Without
    normalization, a caller passing a non-canonical path could bypass
    the allowlist.
    """
    def test_dot_slash_prefix_still_matches(self):
        allow = _allow(globs=(".env",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": "./x/.env"}, allow=allow))

    def test_parent_traversal_still_matches(self):
        allow = _allow(globs=(".env",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": "x/../.env"}, allow=allow))


class SlashlessGlobMatchesFullPathBranch(unittest.TestCase):
    """Mutation kill: slashless glob must try full path as a fallback.

    `_glob_hits` for a glob without `/` returns
        fnmatch(basename, glob) or fnmatch(path, glob)
    Verifier flagged the second fnmatch as a surviving mutation. This
    test exercises a glob that only matches via the full-path branch —
    basename fails, full path succeeds — so dropping that branch
    regresses match behaviour and fails the test.
    """
    def test_slashless_glob_matches_via_full_path(self):
        allow = _allow(globs=("[a]*b",))
        # basename='b' does NOT match '[a]*b' (first char must be 'a');
        # full path 'a/c/b' DOES match ('[a]' eats 'a', '*' eats '/c/').
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": "a/c/b"}, allow=allow))


class NullBytePathDoesNotCrashOrLeak(unittest.TestCase):
    """Gap 11: null-byte in file path must not crash or spuriously match.

    Defense-in-depth: crafted tool output containing \\x00 should never
    raise in the matcher nor cause a wildcard glob to latch onto the
    payload in unexpected ways.
    """
    def test_null_byte_does_not_raise(self):
        allow = _allow(globs=(".env",))
        result = allowlist_matcher.is_private(
            obj={"file": "x\x00.env"}, allow=allow)
        self.assertIsInstance(result, bool)

    def test_null_byte_does_not_match_simple_glob(self):
        allow = _allow(globs=("*.py",))
        self.assertFalse(allowlist_matcher.is_private(
            obj={"file": "safe.py\x00.env"}, allow=allow))


class FileGlobIsCaseSensitive(unittest.TestCase):
    """Gap 9: fnmatch on macOS/Linux is case-sensitive by default.

    A `.env` glob MUST NOT match `.ENV`. Locks current behaviour so a
    future "fix" using fnmatchcase doesn't silently widen matches.
    """
    def test_lowercase_env_glob_does_not_match_upper(self):
        allow = _allow(globs=(".env",))
        self.assertFalse(allowlist_matcher.is_private(
            obj={"file": ".ENV"}, allow=allow))


class NonMatchingFileReturnsFalse(unittest.TestCase):
    def test_ordinary_source_file_not_flagged(self):
        allow = _allow(globs=("*.env", "*secret*"))
        self.assertFalse(allowlist_matcher.is_private(
            obj={"file": "src/app/components/Header.tsx"}, allow=allow))


class MissingFileFieldNotFlagged(unittest.TestCase):
    def test_obj_without_file_returns_false_on_glob_only(self):
        allow = _allow(globs=("*.env",))
        self.assertFalse(allowlist_matcher.is_private(
            obj={"tool": "Bash"}, allow=allow))


class ContentRegexMatchesCommand(unittest.TestCase):
    """AC4: AWS key in bash command output triggers match."""
    def test_aws_key_in_command_flags_private(self):
        allow = _allow(regexes=(r"AKIA[0-9A-Z]{16}\b",))
        obj = {"tool": "Bash", "command": "export KEY=AKIAIOSFODNN7EXAMPLE"}
        self.assertTrue(allowlist_matcher.is_private(
            obj=obj, allow=allow))


class ContentRegexMatchesInSearchableText(unittest.TestCase):
    def test_jwt_in_searchable_text_flags_private(self):
        allow = _allow(regexes=(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",))
        obj = {"searchable_text":
               "token=eyJhbGciOi.eyJzdWIiOi.abc123"}
        self.assertTrue(allowlist_matcher.is_private(
            obj=obj, allow=allow))


class NoContentMatchReturnsFalse(unittest.TestCase):
    def test_benign_content_not_flagged(self):
        allow = _allow(regexes=(r"AKIA[0-9A-Z]{16}\b",))
        obj = {"command": "ls -la", "searchable_text": "file listing"}
        self.assertFalse(allowlist_matcher.is_private(
            obj=obj, allow=allow))


class EmptyAllowlistReturnsFalse(unittest.TestCase):
    """AC7 corollary: empty allowlist = nothing flagged."""
    def test_empty_allowlist_never_matches(self):
        allow = allowlist_loader.Allowlist(file_globs=(), content_regexes=())
        obj = {"file": ".env", "command": "AKIAIOSFODNN7EXAMPLE"}
        self.assertFalse(allowlist_matcher.is_private(
            obj=obj, allow=allow))


class GlobMatchShortCircuitsRegex(unittest.TestCase):
    """File-glob match returns True without scanning content regexes."""
    def test_file_match_returns_true_immediately(self):
        allow = _allow(globs=(".env",), regexes=(r"NEVER_MATCHES_XYZ",))
        self.assertTrue(allowlist_matcher.is_private(
            obj={"file": ".env", "command": "hello"}, allow=allow))


if __name__ == "__main__":
    unittest.main()
