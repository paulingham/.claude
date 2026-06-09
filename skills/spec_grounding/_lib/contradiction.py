"""Deterministic spec-contradiction detector for AC lists.

Public surface
--------------
Contradiction       — frozen dataclass: ac_a_index, ac_b_index, ac_a_text,
                       ac_b_text, shared_subject, category, reason
detect_contradictions(acs: list[str]) -> list[Contradiction]
                    — flag structurally-opposed AC pairs; deterministic, never raises.
                      Empty/None/non-list/non-str-element input → [].
                      No I/O, no model call.

Algorithm (conjunctive AND-gate — high precision)
--------------------------------------------------
For each unordered pair (i, j), i < j:
1. Tokenise both ACs (lowercase, hyphen-aware regex, capped at _MAX_AC_CHARS).
2. Shared subject = intersection of salient noun terms (len≥4, ¬stopword,
   ¬antonym/negation token). Empty → skip (precision gate).
3. Polarity opposition: antonym pair OR negation asymmetry on a shared term.
4. Flag only when BOTH shared-subject AND polarity hold.
"""
import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Bounded constants (mirror grounding.py:38-51 style)
# ---------------------------------------------------------------------------
_MAX_ACS = 200          # cap pairs at C(200,2) — bounds the O(n^2) scan
_MAX_AC_CHARS = 2000    # cap each AC before tokenising
_MIN_TERM_LEN = 4       # salient-term length floor

_STOPWORDS = frozenset({
    # From grounding.py:46-51
    "when", "while", "then", "shall", "should", "that", "with",
    "this", "from", "have", "will", "been", "were", "they",
    "system", "the", "and", "for", "not", "are", "its",
    "also", "must", "each", "some", "any", "all",
    # EARS / AC keywords: high-frequency syntax words that carry no subject meaning
    "default", "where", "upon", "given", "after", "before",
})

_ANTONYM_PAIRS = frozenset({
    frozenset({"enabled", "disabled"}),
    frozenset({"enable", "disable"}),
    frozenset({"allow", "deny"}),
    frozenset({"allowed", "denied"}),
    frozenset({"required", "optional"}),
    frozenset({"sync", "async"}),
    frozenset({"synchronous", "asynchronous"}),
    frozenset({"true", "false"}),
    frozenset({"blocking", "non-blocking"}),
    frozenset({"on", "off"}),
})

# Flat set of all antonym tokens (for filtering from subject terms)
_ANTONYM_TOKENS = frozenset(t for pair in _ANTONYM_PAIRS for t in pair)

_NEGATION_MARKERS = frozenset({"not", "never", "no", "without", "non"})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Contradiction:
    """A structurally-opposed AC pair detected by the deterministic rule engine."""

    ac_a_index: int      # 0-based index of the first AC in the flagged pair
    ac_b_index: int      # 0-based index of the second AC (ac_a_index < ac_b_index)
    ac_a_text: str       # full text of the first AC
    ac_b_text: str       # full text of the second AC
    shared_subject: str  # the salient term(s) the two ACs share, space-joined
    category: str        # "antonym" | "negation" — which rule fired
    reason: str          # human-readable, renders 1-based AC labels


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect_contradictions(acs: list) -> list:
    """Flag structurally-opposed AC pairs. Deterministic, never raises.

    Returns one Contradiction per opposed pair, ascending (ac_a_index, ac_b_index).
    Empty/None/non-list/non-str-element input → []. No I/O, no model call.
    """
    clean = _coerce(acs)
    results = []
    for i in range(len(clean)):
        for j in range(i + 1, len(clean)):
            contradiction = _check_pair(i, j, clean)
            if contradiction is not None:
                results.append(contradiction)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _coerce(acs: object) -> list:
    """Return a clean list[str] bounded to _MAX_ACS, or [] for malformed input."""
    if not isinstance(acs, list):
        return []
    cleaned = [a for a in acs if isinstance(a, str)]
    return cleaned[:_MAX_ACS]


def _tokenise(text: str) -> list:
    """Lowercase + hyphen-aware regex tokens, capped at _MAX_AC_CHARS chars."""
    capped = text[:_MAX_AC_CHARS].lower()
    return re.findall(r"[a-z][a-z0-9-]*", capped)


def _subject_terms(tokens: list) -> set:
    """Filter tokens to salient nouns: len≥4, not stopword, not antonym/negation."""
    result = set()
    for tok in tokens:
        if len(tok) < _MIN_TERM_LEN:
            continue
        if tok in _STOPWORDS:
            continue
        if tok in _ANTONYM_TOKENS:
            continue
        if tok in _NEGATION_MARKERS:
            continue
        result.add(tok)
    return result


def _shared_subject(a_terms: set, b_terms: set) -> list:
    """Return sorted list of terms in the intersection of a_terms and b_terms."""
    return sorted(a_terms & b_terms)


def _ac_is_toggle(token_set: set, pair: frozenset) -> bool:
    """True when token_set contains BOTH poles of pair (the AC describes a toggle)."""
    items = list(pair)
    return items[0] in token_set and items[1] in token_set


def _antonym_hit(a_tokens: list, b_tokens: list) -> Optional[tuple]:
    """Return (a_tok, b_tok) if a firing antonym pair spans the two token lists.

    Skips any pair where either AC contains both poles — that AC is describing a
    toggle, not asserting one side. Returns None when no antonym pair fires.
    """
    a_set = set(a_tokens)
    b_set = set(b_tokens)
    for pair in _ANTONYM_PAIRS:
        if _ac_is_toggle(a_set, pair) or _ac_is_toggle(b_set, pair):
            continue
        items = list(pair)
        if items[0] in a_set and items[1] in b_set:
            return (items[0], items[1])
        if items[1] in a_set and items[0] in b_set:
            return (items[1], items[0])
    return None


def _has_negation_near(tokens: list, term: str) -> bool:
    """True if any negation marker appears in the 3-token window before 'term'.

    Scans ALL occurrences of term in tokens; returns True on first hit.
    Window: tokens[max(0, i-3):i] (the three immediately-preceding tokens).
    """
    for i, tok in enumerate(tokens):
        if tok == term:
            window = tokens[max(0, i - 3):i]
            if any(marker in window for marker in _NEGATION_MARKERS):
                return True
    return False


def _negation_asymmetry(a_tokens: list, b_tokens: list, subject: list) -> bool:
    """True iff exactly one AC negates a shared subject term.

    XOR semantics: fires when _has_negation_near differs for some shared term t.
    """
    for term in subject:
        a_negated = _has_negation_near(a_tokens, term)
        b_negated = _has_negation_near(b_tokens, term)
        if a_negated != b_negated:
            return True
    return False


def _build_contradiction(
    i: int,
    j: int,
    acs: list,
    subject: list,
    category: str,
    antonym_tokens: Optional[tuple],
) -> Contradiction:
    """Assemble a frozen Contradiction dataclass with a human-readable reason."""
    shared_str = " ".join(subject)
    ac_label_a = f"AC{i + 1}"
    ac_label_b = f"AC{j + 1}"
    if category == "antonym" and antonym_tokens is not None:
        a_tok, b_tok = antonym_tokens
        reason = (
            f'{ac_label_a} and {ac_label_b} oppose on "{shared_str}": '
            f'"{a_tok}" vs "{b_tok}"'
        )
    else:
        reason = (
            f'{ac_label_a} and {ac_label_b} oppose on "{shared_str}": '
            f"negation asymmetry"
        )
    return Contradiction(
        ac_a_index=i,
        ac_b_index=j,
        ac_a_text=acs[i],
        ac_b_text=acs[j],
        shared_subject=shared_str,
        category=category,
        reason=reason,
    )


def _check_pair(i: int, j: int, acs: list) -> Optional[Contradiction]:
    """Return a Contradiction if pair (i, j) is structurally opposed, else None."""
    a_tokens = _tokenise(acs[i])
    b_tokens = _tokenise(acs[j])

    a_terms = _subject_terms(a_tokens)
    b_terms = _subject_terms(b_tokens)

    subject = _shared_subject(a_terms, b_terms)
    if not subject:
        return None  # precision gate: no shared subject → skip

    antonym = _antonym_hit(a_tokens, b_tokens)
    if antonym is not None:
        return _build_contradiction(i, j, acs, subject, "antonym", antonym)

    if _negation_asymmetry(a_tokens, b_tokens, subject):
        return _build_contradiction(i, j, acs, subject, "negation", None)

    return None
