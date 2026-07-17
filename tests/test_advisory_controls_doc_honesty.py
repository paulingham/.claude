"""Guard test: advisory controls must not be documented using enforcing
language (blocks/prevents/rejects/enforces/exit 2) without an adjacent
advisory qualifier in the same sentence.

Watch-list (exactly 5 advisory controls) and their first-mention docs:
  - verification-freshness-guard -> rules/safety.md (Iron Law 2 moved here in
    the Phase B gear-tier split; rules/core.md is now a thin @-include index)
  - pre-agent-thinking           -> CLAUDE.md, protocols/thinking-defaults.md
  - pre-agent-advisor            -> CLAUDE.md (token: "Opus-advisor pairing"),
                                    protocols/advisor-mode.md
  - instinct-injector            -> CLAUDE.md, protocols/autonomous-intelligence.md
  - cache-breakpoint-injector    -> protocols/cost-discipline.md

Each watch-list entry is a list of (search_token, doc_path) pairs.  The
search_token is the literal string used to locate the first mention in that
doc — it MAY differ from the control's display name when the doc uses a
different identifying string (e.g. CLAUDE.md references pre-agent-advisor
via "Opus-advisor pairing", not the bare hook name).

Maintenance trade-off: the watch-list is a curated list of the 5 currently-
advisory controls and MUST be updated if a control flips to enforcing (the
test would otherwise silently miss a new enforcement claim). When a control
flips, remove it from the watch-list.

The corpus test (test_all_watchlist_docs_clean) is a REGRESSION GUARD that is
GREEN on the un-edited corpus and stays GREEN after edits. It proves no NEW
false-enforcement claim was introduced. It is NOT a RED-first stub.

A stale (search_token, doc) mapping — where the token is absent from the doc —
causes an IMMEDIATE FAILURE (assertNotEqual) so drift is surfaced loudly rather
than silently skipped.

The RED-first proof for the violation-detection logic lives in the three
matcher fixtures (test_violation_detected_without_qualifier,
test_no_violation_with_advisory_qualifier,
test_same_sentence_log_only_suppresses_violation).

Hermetic: stdlib only (unittest, re, pathlib). No subprocess, no network,
no file writes, no process spawning.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Verb-set and advisory-qualifier definitions
# ---------------------------------------------------------------------------

# Closed enforcing verb set. "exit 2" matched as literal substring (case-
# insensitive). The others matched as \b<verb>\b word-boundary regex (case-
# insensitive) so "blocked" does NOT match \bblock\b, and "blocks" matches
# only as a whole word.
_ENFORCING_VERBS = frozenset({
    "blocks", "block", "prevents", "prevent", "rejects", "reject",
    "enforces", "enforce", "enforcing", "denies", "deny",
})
_ENFORCING_LITERAL = "exit 2"

# Advisory qualifier tokens (any one suffices, case-insensitive).
# Uses the real em-dash — (U+2014).
_ADVISORY_QUALIFIERS = frozenset({
    "ADVISORY — NOT ENFORCED",
    "advisory",
    "log-only",
})


def _violates(text: str) -> bool:
    """Return True iff an enforcing verb appears in ``text`` AND no advisory-
    qualifier token appears in ``text``.

    For unit fixtures, ``text`` is a single sentence; no sentence-splitting
    is performed inside this function. The corpus test
    (test_all_watchlist_docs_clean) splits into sentences externally and calls
    this function per sentence.

    Enforcing-verb matching:
    - ``exit 2``: case-insensitive literal substring.
    - All others: ``\\b<verb>\\b`` word-boundary regex, case-insensitive.
      This means ``block`` does NOT match ``blocked``, and ``blocks`` matches
      only as the complete token ``blocks``.

    Advisory-qualifier matching: case-insensitive substring.
    """
    has_enforcing = False

    # Check literal "exit 2" first.
    if _ENFORCING_LITERAL.lower() in text.lower():
        has_enforcing = True

    # Check word-boundary verbs.
    if not has_enforcing:
        for verb in _ENFORCING_VERBS:
            if re.search(rf"\b{re.escape(verb)}\b", text, re.IGNORECASE):
                has_enforcing = True
                break

    if not has_enforcing:
        return False

    # Has an enforcing verb — now check for an advisory qualifier.
    text_lower = text.lower()
    for qualifier in _ADVISORY_QUALIFIERS:
        if qualifier.lower() in text_lower:
            return False  # qualifier suppresses the violation

    return True  # enforcing verb + no qualifier = violation


# ---------------------------------------------------------------------------
# Sentence boundary helper (for corpus test)
# ---------------------------------------------------------------------------

_SENTENCE_BOUNDARIES = re.compile(r'\. |\n\n|\n')


def _enclosing_sentence(text: str, start: int) -> str:
    """Return the sentence enclosing position ``start`` in ``text``.

    A sentence is the span between the nearest preceding boundary ('. ',
    '\\n\\n', '\\n', or start-of-file) and the nearest following boundary
    ('. ', '\\n', or EOF). This mirrors the same-sentence adjacency window
    specified in the Tier-0 contract.
    """
    # Find the nearest preceding boundary.
    preceding_end = 0
    for m in _SENTENCE_BOUNDARIES.finditer(text[:start]):
        preceding_end = m.end()

    # Find the nearest following boundary.
    following_match = _SENTENCE_BOUNDARIES.search(text, start)
    following_start = len(text) if following_match is None else following_match.start()

    return text[preceding_end:following_start]


# ---------------------------------------------------------------------------
# Watch-list: control name -> list of (search_token, doc_path) pairs
#
# search_token: the literal string used to find the first mention in that doc.
# It may differ from the control name when the doc uses a different identifier
# (e.g. CLAUDE.md refers to pre-agent-advisor via "Opus-advisor pairing").
# doc_path: path relative to REPO_ROOT.
# ---------------------------------------------------------------------------

_WATCH_LIST = {
    "verification-freshness-guard": [
        ("verification-freshness-guard", "rules/safety.md"),
    ],
    "pre-agent-thinking": [
        ("pre-agent-thinking", "CLAUDE.md"),
        ("pre-agent-thinking", "protocols/thinking-defaults.md"),
    ],
    "pre-agent-advisor": [
        # CLAUDE.md references the advisor hook via the pairing description,
        # not the bare hook name — use the token that actually appears there.
        ("Opus-advisor pairing", "CLAUDE.md"),
        ("pre-agent-advisor", "protocols/advisor-mode.md"),
    ],
    "instinct-injector": [
        ("instinct-injector", "CLAUDE.md"),
        ("instinct-injector", "protocols/autonomous-intelligence.md"),
    ],
    "cache-breakpoint-injector": [
        ("cache-breakpoint-injector", "protocols/cost-discipline.md"),
    ],
}


# ---------------------------------------------------------------------------
# Matcher-fixture unit tests (RED-first: these fail because _violates absent)
# ---------------------------------------------------------------------------


class ViolationMatcherFixtures(unittest.TestCase):
    """Unit tests for _violates(). These three fixtures are the RED-first
    proof of the violation-detection logic — they are RED purely because
    _violates / the test module does not exist yet, then GREEN once the
    function is implemented correctly.
    """

    def test_violation_detected_without_qualifier(self):
        """Enforcing verb with no advisory qualifier must return True."""
        self.assertTrue(
            _violates("pre-agent-thinking blocks the spawn"),
            "_violates must return True when an enforcing verb appears "
            "without an advisory qualifier",
        )

    def test_no_violation_with_advisory_qualifier(self):
        """Enforcing verb suppressed by ADVISORY — NOT ENFORCED must return False."""
        self.assertFalse(
            _violates(
                "pre-agent-thinking blocks the spawn "
                "(ADVISORY — NOT ENFORCED)"
            ),
            "_violates must return False when the advisory qualifier is present",
        )

    def test_same_sentence_log_only_suppresses_violation(self):
        """log-only qualifier in the same sentence suppresses the violation.

        This pins the exact rules/core.md:10 suppression behaviour: the
        sentence contains both the enforcing verb 'blocks' and the
        advisory qualifier 'log-only', so _violates must return False.
        """
        self.assertFalse(
            _violates(
                "verification-freshness-guard blocks once permissionDecision "
                "ships (log-only at v2.1.141)"
            ),
            "_violates must return False when 'log-only' qualifies the "
            "enforcing verb in the same sentence",
        )


# ---------------------------------------------------------------------------
# Corpus regression guard (GREEN before AND after edits)
# ---------------------------------------------------------------------------


class CorpusRegressionGuard(unittest.TestCase):
    """Regression guard: for each of the 5 watch-list controls, in each of
    its mapped docs, find the control's FIRST occurrence, extract the
    enclosing sentence, and assert _violates(sentence) is False.

    This test is GREEN on the un-edited corpus (every current first-mention
    sentence either has no enforcing verb, or already carries an advisory
    qualifier in the same sentence). It stays GREEN after our edits.

    Its job is to PROVE no NEW false-enforcement claim is introduced by our
    own edits — and to catch future drift. It is NOT a RED-first stub.
    """

    def test_all_watchlist_docs_clean(self):
        """No first-mention sentence violates the advisory-honesty invariant.

        Each (search_token, doc_path) pair in _WATCH_LIST MUST resolve: if
        search_token is absent from the doc the mapping is stale and the test
        fails loudly (assertNotEqual) rather than silently skipping.
        """
        violations = []
        for control, token_doc_pairs in _WATCH_LIST.items():
            for search_token, rel_path in token_doc_pairs:
                full_path = REPO_ROOT / rel_path
                text = full_path.read_text(encoding="utf-8")
                idx = text.find(search_token)
                self.assertNotEqual(
                    idx,
                    -1,
                    f"stale watch-list mapping: '{search_token}' not found in "
                    f"{rel_path} — update the watch-list",
                )
                sentence = _enclosing_sentence(text, idx)
                if _violates(sentence):
                    violations.append(
                        f"{rel_path}: first-mention sentence for "
                        f"'{control}' (token: '{search_token}') violates "
                        f"advisory-honesty invariant.\n"
                        f"  sentence: {sentence!r}"
                    )
        self.assertEqual(
            violations,
            [],
            "Watch-list docs have advisory-honesty violations in first-mention "
            "sentences:\n" + "\n".join(violations),
        )


# ---------------------------------------------------------------------------
# Label-presence tests (AC1/AC2 — file-level assertIn, NOT proximity)
# ---------------------------------------------------------------------------

_ADVISORY_LABEL = "ADVISORY — NOT ENFORCED"


class LabelPresenceCLAUDEMd(unittest.TestCase):
    """AC1: CLAUDE.md body must contain 'ADVISORY — NOT ENFORCED' for each
    of the thinking / advisor / instinct mentions.

    This is a file-level assertIn, NOT a proximity or co-location check.
    Semantic intent: 'the file carries the qualifier for this control.'
    """

    def test_claude_md_advisory_controls_labelled(self):
        body = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(
            _ADVISORY_LABEL,
            body,
            "CLAUDE.md must contain 'ADVISORY — NOT ENFORCED' "
            "(expected for thinking/advisor/instinct mentions)",
        )
        # Optionally assert at least 3 occurrences (one per advisory mention).
        count = body.count(_ADVISORY_LABEL)
        self.assertGreaterEqual(
            count,
            3,
            f"CLAUDE.md must contain at least 3 occurrences of "
            f"'ADVISORY — NOT ENFORCED' (thinking + advisor + instinct); "
            f"found {count}",
        )


class LabelPresenceProtocols(unittest.TestCase):
    """AC2: each of the scanned protocol files must contain
    'ADVISORY — NOT ENFORCED' at the file level.

    File-level assertIn per file — NOT a proximity or same-sentence check.
    """

    PROTOCOL_FILES = [
        "protocols/thinking-defaults.md",
        "protocols/advisor-mode.md",
        "protocols/autonomous-intelligence.md",
        "protocols/cost-discipline.md",
        # Iron Law 2 (verification-freshness-guard) carries the label; it
        # lives in rules/safety.md after the Phase B gear-tier split.
        "rules/safety.md",
    ]

    def test_protocols_advisory_controls_labelled(self):
        missing = []
        for rel_path in self.PROTOCOL_FILES:
            body = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
            if _ADVISORY_LABEL not in body:
                missing.append(rel_path)
        self.assertEqual(
            missing,
            [],
            f"The following files are missing 'ADVISORY — NOT ENFORCED': "
            f"{missing}",
        )


# ---------------------------------------------------------------------------
# Iron-Law tag tests (AC3)
# ---------------------------------------------------------------------------


class IronLawTags(unittest.TestCase):
    """AC3: the Iron Laws (now split across rules/safety.md and
    rules/pipeline-rigour.md per the Phase B gear-tier split) must carry
    [ENFORCED] or [ASPIRATIONAL] tags per the following mapping:
      1 -> [ASPIRATIONAL]  (pipeline-rigour.md)
      2 -> [ASPIRATIONAL]  (safety.md)
      3 -> [ENFORCED]      (safety.md)
      4 -> [ENFORCED]      (safety.md)
      5 -> [ASPIRATIONAL]  (pipeline-rigour.md)
      6 -> [ASPIRATIONAL]  (safety.md)
      7 -> [ASPIRATIONAL]  (pipeline-rigour.md)
      8 -> [ASPIRATIONAL]  (safety.md)

    Each tag is asserted via a multiline regex of the form
    '^N. [TAG]' to be strict enough to catch a flipped tag while
    lenient enough to survive markdown formatting. The body checked is the
    concatenation of both law-tier files, since the split is non-contiguous
    by design (see rules/core.md's index note).
    """

    def _body(self) -> str:
        safety = (REPO_ROOT / "rules" / "safety.md").read_text(encoding="utf-8")
        rigour = (REPO_ROOT / "rules" / "pipeline-rigour.md").read_text(encoding="utf-8")
        return safety + "\n" + rigour

    def test_iron_laws_enforced_aspirational_tags(self):
        body = self._body()
        expected = {
            1: "ASPIRATIONAL",
            2: "ASPIRATIONAL",
            3: "ENFORCED",
            4: "ENFORCED",
            5: "ASPIRATIONAL",
            6: "ASPIRATIONAL",
            7: "ASPIRATIONAL",
            8: "ASPIRATIONAL",
        }
        failures = []
        for law_num, tag in expected.items():
            pattern = rf"(?m)^{law_num}\. \[{tag}\]"
            if not re.search(pattern, body):
                failures.append(
                    f"Law {law_num}: expected '[{tag}]' tag matching "
                    f"'^{law_num}. [{tag}]' — not found"
                )
        self.assertEqual(
            failures,
            [],
            "Iron Law tag mismatches across rules/safety.md + "
            "rules/pipeline-rigour.md:\n" + "\n".join(failures),
        )


if __name__ == "__main__":
    unittest.main()
