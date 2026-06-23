"""Guard: no real secret tokens committed to settings.json.

Defense-in-depth regression guard added after a HuggingFace token was
previously committed in the settings.json env block (secret-scanning alert #1,
now revoked and removed from HEAD). This test prevents re-introduction.

WHY: settings.json is version-controlled and ships with the harness; a
real secret committed here leaks publicly and triggers GitHub secret-scanning.
The guard walks ALL string values recursively (env block included) and asserts
none match high-confidence secret patterns.
"""
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# WHY: high-confidence patterns only — specific prefixes that have no
# legitimate non-secret use in a config file.
SECRET_PATTERNS = {
    "HuggingFace user token": re.compile(r"hf_[A-Za-z0-9]{34,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"gh[pos]_[A-Za-z0-9]{36,}"),
    "Stripe live secret key": re.compile(r"sk_live_[A-Za-z0-9]{16,}"),
    "Slack bot token": re.compile(r"xoxb-[0-9A-Za-z-]{16,}"),
    "Private key PEM header": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def _collect_string_values(obj, path=""):
    """Yield (json_key_path, string_value) for every string in obj."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for key, val in obj.items():
            child_path = f"{path}.{key}" if path else key
            yield from _collect_string_values(val, child_path)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from _collect_string_values(item, f"{path}[{index}]")


class SettingsNoCommittedSecrets(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads(
            (REPO_ROOT / "settings.json").read_text()
        )

    def test_no_secret_patterns_in_any_string_value(self):
        """Walk all string values in settings.json; assert none match secret regexes."""
        violations = []
        for key_path, value in _collect_string_values(self.settings):
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(value):
                    # WHY: report key path only — never print the matched value
                    violations.append(f"  {label} pattern matched at key: {key_path!r}")
        self.assertEqual(
            violations,
            [],
            "Committed secret detected in settings.json — revoke immediately!\n"
            + "\n".join(violations),
        )

    def test_hf_regex_fires_on_synthetic_sample(self):
        """Self-check: the HuggingFace detector actually fires on a fake token.

        WHY: proves the guard is live and would catch a real token — a regex
        that never matches defeats the purpose of the guard.
        """
        fake_token = "hf_" + "X" * 40
        self.assertRegex(
            fake_token,
            SECRET_PATTERNS["HuggingFace user token"],
            "HuggingFace pattern must match a synthetic fake token (guard self-check)",
        )

    def test_aws_regex_fires_on_synthetic_sample(self):
        """Self-check: AWS access key detector fires on a fake key."""
        fake_key = "AKIA" + "A" * 16
        self.assertRegex(
            fake_key,
            SECRET_PATTERNS["AWS access key"],
            "AWS pattern must match a synthetic fake key (guard self-check)",
        )

    def test_github_token_regex_fires_on_synthetic_sample(self):
        """Self-check: GitHub token detector fires on a fake token."""
        fake_token = "ghp_" + "A" * 36
        self.assertRegex(
            fake_token,
            SECRET_PATTERNS["GitHub token"],
            "GitHub token pattern must match a synthetic fake token (guard self-check)",
        )


if __name__ == "__main__":
    unittest.main()
