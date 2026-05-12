"""AC1: settings.json carries autoMode.hard_deny with $defaults sentinel + 5 rules.

The autoMode.hard_deny array is the v2.1.139 auto-mode classifier surface that
mirrors hooks/_lib/destructive-verbs.txt at prose level. Belt-and-braces additive
protection for auto-mode sessions, NOT a replacement for the PreToolUse path
in hooks/main-branch-guard.sh which fires in every session mode.

Plan source: pipeline-state/harness-native-v2140-migration/plan.md § AC1.
Convention: tests/test_settings_registers_allowlist_hook.py:8-39.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class SettingsAutoModeHardDeny(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((REPO_ROOT / "settings.json").read_text())

    def test_automode_hard_deny_block_present_and_parses(self):
        self.assertIn("autoMode", self.settings,
                      "settings.json must declare a top-level autoMode block")
        self.assertIsInstance(self.settings["autoMode"], dict,
                              "autoMode must be a JSON object")
        self.assertIn("hard_deny", self.settings["autoMode"],
                      "autoMode must declare a hard_deny key")
        self.assertIsInstance(self.settings["autoMode"]["hard_deny"], list,
                              "autoMode.hard_deny must be a JSON array")

    def test_automode_hard_deny_first_element_is_defaults_sentinel(self):
        hard_deny = self.settings["autoMode"]["hard_deny"]
        self.assertGreaterEqual(len(hard_deny), 1,
                                "autoMode.hard_deny must have at least one element")
        self.assertEqual(hard_deny[0], "$defaults",
                         "first element must be the literal '$defaults' sentinel "
                         "so Anthropic's built-in rules are inherited, not shadowed")

    def test_automode_hard_deny_has_five_category_rules_after_sentinel(self):
        hard_deny = self.settings["autoMode"]["hard_deny"]
        self.assertEqual(len(hard_deny), 6,
                         "autoMode.hard_deny must be exactly 6 elements: "
                         "1 sentinel + 5 destructive-category prose rules")
        rules_after_sentinel = hard_deny[1:]
        for index, rule in enumerate(rules_after_sentinel, start=1):
            self.assertIsInstance(rule, str,
                                  f"hard_deny[{index}] must be a string")
            self.assertGreater(len(rule.strip()), 0,
                               f"hard_deny[{index}] must be a non-empty string")

    def test_automode_hard_deny_rules_cover_five_categories(self):
        hard_deny = self.settings["autoMode"]["hard_deny"]
        joined = " ".join(hard_deny[1:]).lower()
        anchors = {
            "volume / cloud-storage deletion": r"volume|cloud storage",
            "database destruction (DROP TABLE / TRUNCATE)": r"drop table|truncate",
            "force-push to protected branches": r"force.*push.*main|force.*push.*master",
            "filesystem destruction (rm -rf $HOME)": r"rm -rf .*home",
            "Kubernetes namespace deletion": r"kubectl.*namespace.*prod",
        }
        for category, pattern in anchors.items():
            self.assertRegex(joined, pattern,
                             f"hard_deny rules must cover {category}; "
                             f"pattern {pattern!r} not found in joined prose")


if __name__ == "__main__":
    unittest.main()
