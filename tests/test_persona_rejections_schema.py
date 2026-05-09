"""AC6 + AC8: producer-contract schema validator + legacy-absence regression.

Pure-Python validator that mirrors the consumer's accepted shape but
declares the allowed sets INLINE — does NOT import from
`hooks/_lib/learn_persona_roles.py`. Mirroring is intentional;
coupling is not. Per challenger Finding 1: the producer contract is
documented separately from the consumer, and any drift between them
is itself a regression.

Schema (per `rules/_detail/autonomous-intelligence.md` § Field reference):

- `persona ∈ {correctness, regression-risk, scope-creep}`
- `dimension: int`
- `severity ∈ {CRITICAL, HIGH, MEDIUM}` — LOW/INFO excluded.
- All three keys required.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from learn_anti_pattern_mining import mine_anti_patterns  # noqa: E402


# Allowed sets declared INLINE — independent producer-contract.
# Mirrors `_PERSONA_TO_ROLE` keys in
# `hooks/_lib/learn_persona_roles.py:31-35` but is deliberately
# not imported, per challenger Finding 1.
_ALLOWED_PERSONAS = frozenset({
    "correctness", "regression-risk", "scope-creep"})

_ALLOWED_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM"})

_REQUIRED_KEYS = frozenset({"persona", "dimension", "severity"})


def validate_persona_rejection(entry: dict) -> bool:
    """Return True iff `entry` is a producer-valid persona-rejection.

    Pure function — contract assertion, no I/O. Used by the schema
    test suite below.
    """
    if not isinstance(entry, dict):
        return False
    if set(entry.keys()) < _REQUIRED_KEYS:
        return False
    if entry["persona"] not in _ALLOWED_PERSONAS:
        return False
    if not isinstance(entry["dimension"], int):
        return False
    if entry["severity"] not in _ALLOWED_SEVERITIES:
        return False
    return True


# ---------------------------------------------------------------------------
# AC6: schema validator accepts valid + rejects invalid shapes
# ---------------------------------------------------------------------------
class TestPersonaRejectionsSchema(unittest.TestCase):
    """AC6: pure validator accepts well-formed entries and rejects every
    variant the consumer rejects (unknown persona, severity == LOW,
    missing keys).
    """

    def test_valid_entry_passes(self):
        for persona in _ALLOWED_PERSONAS:
            for severity in _ALLOWED_SEVERITIES:
                entry = {"persona": persona, "dimension": 1,
                         "severity": severity}
                self.assertTrue(
                    validate_persona_rejection(entry),
                    f"valid entry rejected: {entry!r}")

    def test_invalid_persona_rejected(self):
        bad_personas = [
            "accessibility-strict",  # consumer-unknown
            "correctness ",           # whitespace
            "Correctness",            # case-sensitive
            "",
            None,
            42,
        ]
        for bad in bad_personas:
            entry = {"persona": bad, "dimension": 1, "severity": "HIGH"}
            self.assertFalse(
                validate_persona_rejection(entry),
                f"invalid persona accepted: {bad!r}")

    def test_invalid_severity_rejected(self):
        # LOW + INFO are documented as EXCLUDED from the producer's
        # writes (per `agents/patch-critic.md:74`); validator must
        # reject.
        bad_severities = ["LOW", "INFO", "low", "high", "critical", "",
                          None, 1]
        for bad in bad_severities:
            entry = {"persona": "correctness", "dimension": 1,
                     "severity": bad}
            self.assertFalse(
                validate_persona_rejection(entry),
                f"invalid severity accepted: {bad!r}")

    def test_missing_field_rejected(self):
        # Each required key must be enforced.
        for missing in _REQUIRED_KEYS:
            entry = {"persona": "correctness", "dimension": 1,
                     "severity": "HIGH"}
            del entry[missing]
            self.assertFalse(
                validate_persona_rejection(entry),
                f"entry missing {missing!r} accepted")

    def test_dimension_must_be_int(self):
        for bad in ["1", 1.5, None, "one"]:
            entry = {"persona": "correctness", "dimension": bad,
                     "severity": "HIGH"}
            self.assertFalse(
                validate_persona_rejection(entry),
                f"non-int dimension accepted: {bad!r}")

    def test_non_dict_rejected(self):
        for bad in [None, [], "", 42, "not-a-dict"]:
            self.assertFalse(
                validate_persona_rejection(bad),
                f"non-dict accepted: {bad!r}")


# ---------------------------------------------------------------------------
# AC8: backward-compat — legacy observations without phases.patch_critic
# block are silently skipped by mine_anti_patterns; no exception, no file.
# ---------------------------------------------------------------------------
class TestLegacyAbsence(unittest.TestCase):
    """AC8: legacy observations lacking `phases.patch_critic` entirely
    pass through the consumer cleanly. Mirrors B2's
    `test_legacy_record_missing_both_rounds_skipped` invariant.
    """

    def test_legacy_record_without_patch_critic_block_skipped(self):
        """Three legacy records (no phases.patch_critic, no
        phases.review.rounds) are silently skipped: `_passes_gate`
        rejects them, no file emitted, no exception.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            findings = ["warning: legacy absent patch_critic block"]
            records = []
            for n in range(4):
                records.append({
                    "record_type": "pipeline",
                    "pipeline_id": f"legacy-{n}",
                    "scratchpad_findings": findings,
                    "phases": {},  # no review, no patch_critic
                })
            obs = tmp_path / "observations.jsonl"
            with obs.open("w") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
            written = mine_anti_patterns(
                observations_path=obs,
                instincts_dir=tmp_path / "instincts")
            self.assertEqual(written, [])


if __name__ == "__main__":
    unittest.main()
