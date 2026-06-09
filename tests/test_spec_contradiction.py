"""Tests for spec-contradiction detector (GP-P2-07).

Covers AC1 (antonym/negation detection), AC2 (precision gates — no false positives),
AC3 (robustness / never-raises), AC4 (fixtures), AC5 (wire-in doc/catalog audit).
"""
import sys
from pathlib import Path

# Unconditionally inject skills/ onto sys.path — conftest only injects hooks/_lib.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))


# ---------------------------------------------------------------------------
# AC3 — module import + robustness
# ---------------------------------------------------------------------------

def test_module_imports_cleanly():
    """import detect_contradictions, Contradiction succeeds; Contradiction is frozen."""
    from spec_grounding._lib.contradiction import detect_contradictions, Contradiction
    import dataclasses
    assert dataclasses.is_dataclass(Contradiction)
    # Frozen — assigning an attribute must raise FrozenInstanceError
    c = Contradiction(
        ac_a_index=0,
        ac_b_index=1,
        ac_a_text="a",
        ac_b_text="b",
        shared_subject="subject",
        category="antonym",
        reason="AC1 and AC2 oppose on something",
    )
    try:
        c.ac_a_index = 99
        assert False, "Expected FrozenInstanceError"
    except Exception:
        pass  # correct — frozen dataclass raised


def test_empty_input_returns_empty():
    """detect_contradictions([]) == []."""
    from spec_grounding._lib.contradiction import detect_contradictions
    assert detect_contradictions([]) == []


def test_malformed_input_returns_empty():
    """None, 'not a list', [None, 42, 'x'] → [], never raises."""
    from spec_grounding._lib.contradiction import detect_contradictions
    assert detect_contradictions(None) == []  # type: ignore[arg-type]
    assert detect_contradictions("not a list") == []  # type: ignore[arg-type]
    assert detect_contradictions([None, 42, "x"]) == []  # type: ignore[arg-type]


def test_deterministic_same_input_same_output():
    """Two calls with the same list return equal results."""
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = ["X enabled by default", "X disabled by default"]
    assert detect_contradictions(acs) == detect_contradictions(acs)


def test_oversized_input_bounded():
    """Cap observable: contradictory pair beyond _MAX_ACS is NOT flagged."""
    from spec_grounding._lib.contradiction import detect_contradictions, _coerce, _MAX_ACS
    # Pad with _MAX_ACS benign unique ACs (no antonyms, no shared subjects)
    benign = [f"widget_{i} loads immediately" for i in range(_MAX_ACS)]
    # Append a contradictory pair BEYOND the cap — should be truncated
    contradictory_pair = [
        "telemetry enabled by default",
        "telemetry disabled by default",
    ]
    big_list = benign + contradictory_pair
    assert len(big_list) == _MAX_ACS + 2
    # _coerce must truncate to exactly _MAX_ACS
    assert len(_coerce(big_list)) == _MAX_ACS
    # detect_contradictions must NOT flag the out-of-range pair
    result = detect_contradictions(big_list)
    assert isinstance(result, list)
    flagged_pairs = {(c.ac_a_index, c.ac_b_index) for c in result}
    # The contradictory pair was at original indices _MAX_ACS and _MAX_ACS+1 — must be absent
    assert (_MAX_ACS, _MAX_ACS + 1) not in flagged_pairs


# ---------------------------------------------------------------------------
# AC1 — antonym detection
# ---------------------------------------------------------------------------

def test_antonym_self_toggle_not_flagged():
    """Single AC describing a toggle ('enabled or disabled') must NOT fire against another AC.

    Repro from Finding 1: when ONE AC contains both poles of an antonym pair (a toggle
    description), _antonym_hit must NOT flag a contradiction with a second AC that
    mentions only one pole.
    """
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = [
        "telemetry can be enabled or disabled by the operator",
        "telemetry is enabled in staging",
    ]
    result = detect_contradictions(acs)
    assert result == [], (
        f"Antonym-self false positive: expected [], got {result}"
    )


def test_cross_ac_antonym_still_fires():
    """True cross-AC antonym opposition still fires after the guard.

    'X enabled by default' vs 'X disabled by default' — each AC contains only
    one pole, so the contradiction is genuine and must be flagged.
    """
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = ["telemetry enabled by default", "telemetry disabled by default"]
    result = detect_contradictions(acs)
    assert len(result) == 1, (
        f"Over-correction guard: expected 1 contradiction, got {result}"
    )
    assert result[0].category == "antonym"


def test_antonym_pair_flagged_with_indices_and_reason():
    """'telemetry enabled by default'+'telemetry disabled by default' → 1 Contradiction.

    Asserts: ac_a_index==0, ac_b_index==1, reason non-empty mentions both ACs,
    category=='antonym'. (The plan uses "X" as a placeholder for any salient noun ≥4 chars;
    "telemetry" is used here as the concrete shared subject.)
    """
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = ["telemetry enabled by default", "telemetry disabled by default"]
    result = detect_contradictions(acs)
    assert len(result) == 1
    c = result[0]
    assert c.ac_a_index == 0
    assert c.ac_b_index == 1
    assert c.category == "antonym"
    assert c.shared_subject == "telemetry"
    assert c.reason  # non-empty
    assert "AC1" in c.reason
    assert "AC2" in c.reason


def test_negation_asymmetry_flagged():
    """'feature SHALL be cached'+'feature SHALL NOT be cached' → 1 Contradiction.

    category=='negation', shared_subject contains 'cached'.
    """
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = ["feature SHALL be cached", "feature SHALL NOT be cached"]
    result = detect_contradictions(acs)
    assert len(result) == 1
    c = result[0]
    assert c.category == "negation"
    assert "cached" in c.shared_subject


def test_non_blocking_tokenises_whole():
    """'request processing blocking'+'request processing non-blocking' → 1 Contradiction.

    category=='antonym'. Asserts that 'non-blocking' tokenises as a SINGLE token
    (hyphen retained), NOT split into 'non'+'blocking'. (The plan uses "X" as a
    placeholder; "request processing" provides a shared subject ≥4 chars.)
    """
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = ["request processing shall be blocking", "request processing shall be non-blocking"]
    result = detect_contradictions(acs)
    assert len(result) == 1
    assert result[0].category == "antonym"
    # The antonym rule must match 'blocking' vs 'non-blocking' as whole tokens.
    # If the tokeniser split 'non-blocking' into 'non'+'blocking', the antonym
    # pair frozenset({'blocking','non-blocking'}) would NOT match — the result
    # would be a negation hit instead, or zero hits (no shared subject without
    # 'blocking' being in AC B's token list for antonym purposes).
    # We verify category is 'antonym' (not 'negation'), confirming whole-token match.


# ---------------------------------------------------------------------------
# AC4 — fixtures
# ---------------------------------------------------------------------------

def test_contradictory_fixture_is_flagged():
    """4-AC fixture with one opposed pair → len≥1, opposed indices present.

    The shared subject for the (1,3) pair is 'production telemetry' — two terms
    in sorted (alphabetical) order. This assertion kills the list()-instead-of-sorted()
    mutant: list(set) order is non-deterministic across PYTHONHASHSEED values, so
    replacing sorted() with list() would yield 'telemetry production' on some runs.
    """
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = [
        "The system should support batch processing",
        "telemetry enabled by default in production",
        "All errors shall be logged immediately",
        "telemetry disabled by default in production",
    ]
    result = detect_contradictions(acs)
    assert len(result) >= 1
    # The opposed pair is (index 1, index 3)
    pairs = {(c.ac_a_index, c.ac_b_index) for c in result}
    assert (1, 3) in pairs
    # Pin the shared_subject value: 'production telemetry' (alphabetical/sorted order).
    # Both ACs share 'telemetry' and 'production' as salient terms (len≥4, not stopword).
    # The list() mutant produces non-deterministic order across PYTHONHASHSEED values,
    # so this assertion kills it.
    contradiction_1_3 = next(c for c in result if (c.ac_a_index, c.ac_b_index) == (1, 3))
    assert contradiction_1_3.shared_subject == "production telemetry"


def test_compatible_fixture_not_flagged():
    """4-AC compatible fixture (shared words, no antonym/negation) → []."""
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = [
        "The system shall store user preferences",
        "User preferences shall be persisted across sessions",
        "Preferences shall load within 200ms",
        "The system shall validate preference keys",
    ]
    result = detect_contradictions(acs)
    assert result == []


# ---------------------------------------------------------------------------
# AC2 — precision gates (no false positives)
# ---------------------------------------------------------------------------

def test_no_contradictions_returns_empty():
    """Two unrelated ACs (disjoint subjects) → []."""
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = [
        "The payment gateway shall process transactions",
        "User profile avatars shall be resized on upload",
    ]
    assert detect_contradictions(acs) == []


def test_antonym_without_shared_subject_not_flagged():
    """'enable logging'+'disable telemetry' → [] (precision gate: no shared subject)."""
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = ["enable logging", "disable telemetry"]
    assert detect_contradictions(acs) == []


def test_shared_subject_without_polarity_not_flagged():
    """'X cached by default'+'Y cached by default' → [] (precision gate: no polarity opposition)."""
    from spec_grounding._lib.contradiction import detect_contradictions
    acs = ["requests cached by default", "responses cached by default"]
    assert detect_contradictions(acs) == []


# ---------------------------------------------------------------------------
# AC5 — wire-in doc / catalog audit
# ---------------------------------------------------------------------------

def test_skill_frontmatter_declares_verdicts():
    """SKILL.md frontmatter verdict: field includes both contradiction verdicts."""
    import re
    skill_md = REPO_ROOT / "skills" / "spec-grounding" / "SKILL.md"
    text = skill_md.read_text()
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert fm_match, "spec-grounding/SKILL.md has no frontmatter"
    frontmatter = fm_match.group(1)
    verdict_line = next(
        (ln for ln in frontmatter.splitlines() if ln.strip().startswith("verdict:")),
        None,
    )
    assert verdict_line, "No verdict: field in spec-grounding/SKILL.md frontmatter"
    assert "SPEC_CONTRADICTIONS_FOUND" in verdict_line, (
        "verdict: field must declare SPEC_CONTRADICTIONS_FOUND"
    )
    assert "SPEC_CONTRADICTIONS_NONE" in verdict_line, (
        "verdict: field must declare SPEC_CONTRADICTIONS_NONE"
    )


def test_skill_documents_contradiction_verdicts():
    """SKILL.md § Verdict table (3-col) has both verdict rows marked non-blocking.

    Also checks that the body references the new contradiction step (Step 2.5).
    """
    import re as _re
    skill_md = REPO_ROOT / "skills" / "spec-grounding" / "SKILL.md"
    text = skill_md.read_text()
    assert "SPEC_CONTRADICTIONS_FOUND" in text, (
        "spec-grounding/SKILL.md must document SPEC_CONTRADICTIONS_FOUND"
    )
    assert "SPEC_CONTRADICTIONS_NONE" in text, (
        "spec-grounding/SKILL.md must document SPEC_CONTRADICTIONS_NONE"
    )
    # Find the verdict table rows specifically (after the frontmatter ends)
    body = text[text.index("---", 4) + 3:]  # skip frontmatter (2nd "---")
    # Both verdict verdicts must appear somewhere in the body
    assert "SPEC_CONTRADICTIONS_FOUND" in body, (
        "SPEC_CONTRADICTIONS_FOUND must be in SKILL.md body (not just frontmatter)"
    )
    assert "SPEC_CONTRADICTIONS_NONE" in body, (
        "SPEC_CONTRADICTIONS_NONE must be in SKILL.md body (not just frontmatter)"
    )
    # The § Verdict section (3-col table) must contain non-blocking annotation
    # Locate the "## Verdict" section and check for non-blocking there
    verdict_section_idx = body.lower().index("## verdict")
    verdict_section = body[verdict_section_idx:]
    assert "non-blocking" in verdict_section.lower(), (
        "SKILL.md § Verdict section must contain 'non-blocking' annotation"
    )
    assert "SPEC_CONTRADICTIONS_FOUND" in verdict_section, (
        "§ Verdict section must list SPEC_CONTRADICTIONS_FOUND"
    )
    assert "SPEC_CONTRADICTIONS_NONE" in verdict_section, (
        "§ Verdict section must list SPEC_CONTRADICTIONS_NONE"
    )
    # Body must reference the contradiction step
    assert "detect_contradictions" in body or "Step 2.5" in body, (
        "spec-grounding/SKILL.md body must reference detect_contradictions or Step 2.5"
    )


def test_contradiction_verdicts_in_catalog():
    """Both verdicts in verdict-catalog.md: polarity info, emitter spec-grounding, phase plan."""
    import re
    catalog = REPO_ROOT / "protocols" / "verdict-catalog.md"
    text = catalog.read_text()
    pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*([a-z]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )
    rows = {}
    for m in pattern.finditer(text):
        rows[m.group(1)] = {
            "polarity": m.group(2),
            "emitters": m.group(3),
            "phase": m.group(4).strip(),
        }

    assert "SPEC_CONTRADICTIONS_FOUND" in rows, (
        "protocols/verdict-catalog.md must contain SPEC_CONTRADICTIONS_FOUND"
    )
    assert "SPEC_CONTRADICTIONS_NONE" in rows, (
        "protocols/verdict-catalog.md must contain SPEC_CONTRADICTIONS_NONE"
    )
    for verdict in ("SPEC_CONTRADICTIONS_FOUND", "SPEC_CONTRADICTIONS_NONE"):
        row = rows[verdict]
        assert row["polarity"] == "info", f"{verdict} must be polarity=info"
        assert "spec-grounding" in row["emitters"], (
            f"{verdict} emitter must include spec-grounding"
        )
        assert row["phase"] == "plan", f"{verdict} phase must be plan"
