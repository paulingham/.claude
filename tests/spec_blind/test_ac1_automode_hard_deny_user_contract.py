"""Spec-blind tests for AC1.

AC1 (verbatim from plan):
    settings.json carries a top-level autoMode.hard_deny array of length 6:
    index [0] is the literal string "$defaults", indices [1..5] are 5 prose
    rules covering destructive-verb categories (volume/cloud-storage,
    DROP TABLE/TRUNCATE, force-push to protected branches, rm -rf $HOME/~,
    kubectl delete namespace prod).

These tests were authored WITHOUT reading the build agent's tests at
tests/test_settings_automode_hard_deny.py.  They derive from the AC literal
treated as the user-facing contract:

  * Auto-mode operator opens a session; their classifier consumes
    settings.json.  If autoMode.hard_deny is malformed, the session fails.
  * The classifier interprets prose rules.  Each rule must be
    user-interpretable (a meaningful string discussing the category).
  * The "$defaults" sentinel preserves Anthropic's built-in coverage;
    omitting or misspelling it shadows curated defaults.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


# Each category has a list of independent indicators.  A prose rule covers a
# category if it matches ANY indicator (case-insensitive).  Multiple
# indicators per category make the test resilient to small wording changes
# without falling back to the build agent's exact regex anchors.
CATEGORY_INDICATORS: dict[str, list[str]] = {
    "volume_cloud_storage": [
        "volumedelete",
        "aws s3 rb",
        "gcloud sql",
        "fly destroy",
        "railway down",
        "volume",
        "cloud storage",
        "cloud volume",
    ],
    "database_destruction": [
        "drop table",
        "truncate",
    ],
    "force_push_protected": [
        "force-push",
        "force push",
        "--force",
        "--force-with-lease",
    ],
    "filesystem_destruction_home": [
        "rm -rf $home",
        "rm -rf ~",
        "rm -rf home",  # tolerate "home directory"
        "home directory",
    ],
    "kubectl_prod_namespace": [
        "kubectl delete namespace prod",
        "kubectl delete namespace production",
        "kubernetes namespace",
    ],
}


def _load_settings(settings_json_path: Path) -> dict:
    """Parse settings.json.  Raises on malformed JSON (which is AC1's first failure mode)."""
    return json.loads(settings_json_path.read_text(encoding="utf-8"))


def test_settings_json_parses_as_valid_json(settings_json_path: Path) -> None:
    """If settings.json is malformed, every subsequent Claude Code session fails to load."""
    _load_settings(settings_json_path)


def test_automode_block_present_at_top_level(settings_json_path: Path) -> None:
    """AC1: 'top-level autoMode' — must be a direct child of the JSON root."""
    settings = _load_settings(settings_json_path)
    assert "autoMode" in settings, (
        "spec-blind: AC1 violated — settings.json has no top-level autoMode key"
    )
    assert isinstance(settings["autoMode"], dict), (
        "spec-blind: AC1 violated — autoMode must be a JSON object"
    )


def test_hard_deny_is_array_of_length_six(settings_json_path: Path) -> None:
    """AC1: 'array of length 6: 1 sentinel + 5 rules'."""
    settings = _load_settings(settings_json_path)
    hard_deny = settings["autoMode"]["hard_deny"]
    assert isinstance(hard_deny, list), (
        "spec-blind: AC1 violated — autoMode.hard_deny must be a JSON array"
    )
    assert len(hard_deny) == 6, (
        f"spec-blind: AC1 violated — autoMode.hard_deny has {len(hard_deny)} elements, "
        f"AC requires exactly 6 (1 $defaults sentinel + 5 category rules)"
    )


def test_first_element_is_literal_defaults_sentinel(settings_json_path: Path) -> None:
    """AC1: 'index [0] is the literal string "$defaults"'.

    The leading "$" is load-bearing: omitting it would shadow Anthropic's
    built-in hard_deny rules silently — auto-mode users lose curated coverage.
    """
    settings = _load_settings(settings_json_path)
    first = settings["autoMode"]["hard_deny"][0]
    assert first == "$defaults", (
        f"spec-blind: AC1 violated — autoMode.hard_deny[0] is {first!r}, "
        f'AC requires the literal string "$defaults". Missing "$" silently '
        f"shadows Anthropic's built-in rules."
    )


def test_remaining_five_elements_are_non_empty_strings(settings_json_path: Path) -> None:
    """AC1: 'indices [1..5] are 5 prose rules'.

    Prose rules MUST be non-empty strings — the auto-mode classifier needs
    something to interpret.
    """
    settings = _load_settings(settings_json_path)
    rules = settings["autoMode"]["hard_deny"][1:]
    for idx, rule in enumerate(rules, start=1):
        assert isinstance(rule, str), (
            f"spec-blind: AC1 violated — autoMode.hard_deny[{idx}] is "
            f"{type(rule).__name__}, AC requires a prose string"
        )
        assert rule.strip(), (
            f"spec-blind: AC1 violated — autoMode.hard_deny[{idx}] is empty/whitespace"
        )


def _find_rule_for_category(rules: list[str], indicators: list[str]) -> int | None:
    """Return the index (relative to rules list) of the first rule that
    mentions any indicator for this category."""
    for idx, rule in enumerate(rules):
        lower = rule.lower()
        for indicator in indicators:
            if indicator in lower:
                return idx
    return None


def test_each_destructive_category_has_at_least_one_rule(settings_json_path: Path) -> None:
    """AC1: prose rules cover 5 named destructive-verb categories.

    Each of the 5 named categories MUST appear in at least one prose rule.
    """
    settings = _load_settings(settings_json_path)
    rules = settings["autoMode"]["hard_deny"][1:]  # skip $defaults sentinel

    missing: list[str] = []
    for category, indicators in CATEGORY_INDICATORS.items():
        if _find_rule_for_category(rules, indicators) is None:
            missing.append(category)
    assert not missing, (
        f"spec-blind: AC1 violated — the following destructive-verb categories "
        f"have no matching prose rule in autoMode.hard_deny: {missing}. "
        f"Auto-mode users lose belt-and-braces coverage for these."
    )


def test_all_five_categories_covered_with_unique_rules(settings_json_path: Path) -> None:
    """AC1: '5 prose rules covering five categories'.

    Each rule should cover a different category — five categories, five
    rules.  A single rule covering two categories would mean another category
    is missing.
    """
    settings = _load_settings(settings_json_path)
    rules = settings["autoMode"]["hard_deny"][1:]
    assert len(rules) == 5, "preflight: AC requires exactly 5 prose rules"

    # Map: rule_index -> set of categories matched
    rule_to_categories: dict[int, set[str]] = {i: set() for i in range(len(rules))}
    for category, indicators in CATEGORY_INDICATORS.items():
        for idx, rule in enumerate(rules):
            lower = rule.lower()
            if any(ind in lower for ind in indicators):
                rule_to_categories[idx].add(category)

    # Every rule must match at least one category (no junk rules).
    orphan_rules = [i for i, cats in rule_to_categories.items() if not cats]
    assert not orphan_rules, (
        f"spec-blind: AC1 violated — rules at indices {orphan_rules} (in the "
        f"[1..5] slice) don't mention any of the 5 named destructive-verb "
        f"categories.  Each rule must be category-attributable."
    )

    # Every category must be matched by at least one rule.
    matched_categories: set[str] = set()
    for cats in rule_to_categories.values():
        matched_categories.update(cats)
    missing = set(CATEGORY_INDICATORS) - matched_categories
    assert not missing, (
        f"spec-blind: AC1 violated — categories with NO matching rule: {missing}"
    )


def test_rules_mention_specific_destructive_tokens(settings_json_path: Path) -> None:
    """AC1: rules must be 'user-interpretable' (per spike-findings / plan).

    Each rule should mention at least one concrete destructive token the
    auto-mode classifier could pattern-match against operator intent — not
    just a vague phrase like "be careful with deletes".
    """
    settings = _load_settings(settings_json_path)
    rules = settings["autoMode"]["hard_deny"][1:]

    # Tokens that signal a rule references a real destructive verb.
    # Use individual fragments to keep the test resilient to phrasing.
    concrete_tokens = [
        "volumedelete",
        "aws s3 rb",
        "gcloud sql",
        "fly destroy",
        "railway down",
        "drop table",
        "truncate",
        "--force",
        "force-push",
        "rm -rf",
        "kubectl",
    ]
    vague_rules: list[int] = []
    for idx, rule in enumerate(rules, start=1):
        lower = rule.lower()
        if not any(tok in lower for tok in concrete_tokens):
            vague_rules.append(idx)
    assert not vague_rules, (
        f"spec-blind: AC1 violated — rules at hard_deny indices {vague_rules} "
        f"contain no concrete destructive token; classifier cannot match them "
        f"against operator commands"
    )


def test_protected_branch_rule_lists_each_protected_branch(settings_json_path: Path) -> None:
    """AC1 explicitly names the protected branches: main, master, release, production,
    staging, develop.  The force-push rule must enumerate them (or a strict superset).
    """
    settings = _load_settings(settings_json_path)
    rules = settings["autoMode"]["hard_deny"][1:]
    expected_branches = {"main", "master", "release", "production", "staging", "develop"}

    # Find the rule that talks about force-push.
    force_push_rules = [
        r for r in rules if "force" in r.lower() and "push" in r.lower()
    ]
    assert force_push_rules, (
        "spec-blind: AC1 violated — no force-push rule found in autoMode.hard_deny"
    )

    # At least one of those rules should name every expected branch.
    # (We accept that wording may differ — accept "branches: main, master, ..." or
    # similar, just check word-boundary presence.)
    for rule in force_push_rules:
        lower = rule.lower()
        # Use word-boundary matching to avoid e.g. "main" matching "remaining".
        present = {b for b in expected_branches if re.search(rf"\b{b}\b", lower)}
        if present == expected_branches:
            return
    assert False, (
        "spec-blind: AC1 violated — no single force-push rule names all six "
        f"protected branches {sorted(expected_branches)}; the AC literally "
        "enumerates main/master/release/production/staging/develop."
    )
