"""Contract tests for Step 7d: Promote Durable Memories to Repo-Tracked Proposals.

Step 7d of `/harness:learn` scans both the instinct store and the durable-memory
store for promotion candidates, classifies them via a heuristic ladder, and emits
one DRAFT intake prompt per candidate to `pipeline-state/{task-id}/
memory-promotion-drafts/`. It surfaces drafts in the Step 9 Report.

It NEVER auto-applies changes; the human is the gate.

ACs covered: A1-A9 (§7d prose), B1-B3 (Step 9 report), C1-C2 (reflection-protocol
§ 6b wire-in). 13 assertions total.

Pattern mirrors tests/test_learn_step7b_anti_pattern_skip.py.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "learn" / "SKILL.md"
REFLECTION_PROTOCOL_PATH = REPO_ROOT / "protocols" / "reflection-protocol.md"

# ---------------------------------------------------------------------------
# Section extractors
# ---------------------------------------------------------------------------

def _extract_step_7d(text: str) -> str:
    """Extract the §7d section body from SKILL.md.

    Uses a defensive lookahead: if a future §7e is ever added it will not
    bleed into the §7d capture, matching the plan's SE-LOW advisory.
    """
    m = re.search(
        r"### 7d\..*?(?=\n### 7e\.|\n### 8\.|\Z)",
        text,
        re.DOTALL,
    )
    return m.group(0) if m else ""


def _extract_step_9(text: str) -> str:
    """Extract the §9 Report section body from SKILL.md."""
    m = re.search(
        r"### 9\..*?(?=\n### 10\.|\Z)",
        text,
        re.DOTALL,
    )
    return m.group(0) if m else ""


def _extract_section_6b(text: str) -> str:
    """Extract the § 6b Auto-Learn Gate Check section from reflection-protocol.md."""
    m = re.search(
        r"### 6b\..*?(?=\n### 6b-bis\.|\n### 6c\.|\Z)",
        text,
        re.DOTALL,
    )
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# Slice A: §7d prose contract tests (AC-A1 through AC-A9)
# ---------------------------------------------------------------------------

class Step7dRecurrenceBases(unittest.TestCase):
    """AC-A1: §7d documents both recurrence bases with N=3."""

    def test_step_7d_documents_both_recurrence_bases(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        # Instinct basis: evidence_count and confidence
        self.assertIn("evidence_count", section,
                      "§7d must mention 'evidence_count' (instinct recurrence basis)")
        self.assertIn("confidence", section,
                      "§7d must mention 'confidence' (instinct recurrence basis)")
        # Memory basis: backlink / [[ notation and durable: true
        backlink_present = "backlink" in section.lower() or "[[" in section
        self.assertTrue(backlink_present,
                        "§7d must mention backlink or [[ (memory recurrence basis)")
        self.assertIn("durable: true", section,
                      "§7d must mention 'durable: true' (secondary override)")
        # Threshold N=3 — match the token in context, not a bare digit.
        # The prose uses ">= 3" for both the instinct evidence_count gate and
        # the memory backlink gate.  A bare "3" appears 5+ times in the section
        # (list lengths, step references, etc.) so assertIn("3") is trivially
        # green even if the threshold were corrupted to "N=9".
        self.assertRegex(section, r">=\s*3",
                         "§7d must state the default threshold as '>= 3'")


class Step7dDraftDirectory(unittest.TestCase):
    """AC-A2: §7d names pipeline-state/ as the draft directory."""

    def test_step_7d_names_pipeline_state_draft_dir(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        self.assertIn("pipeline-state/", section,
                      "§7d must name 'pipeline-state/' as the draft output dir")
        self.assertIn("memory-promotion-drafts", section,
                      "§7d must name the 'memory-promotion-drafts' subdirectory")


class Step7dGateSafetyAndAutoApply(unittest.TestCase):
    """AC-A3 (part 1): §7d states 'never auto-applies'/'the human is the gate'
    AND 'never modifies a security/correctness gate'.
    """

    def test_step_7d_states_never_auto_apply_and_gate_safety(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        human_gate = (
            "never auto-applies" in section.lower()
            or "the human is the gate" in section.lower()
        )
        self.assertTrue(human_gate,
                        "§7d must state 'never auto-applies' or 'the human is the gate'")
        self.assertIn("never modifies a security/correctness gate", section.lower(),
                      "§7d must state 'never modifies a security/correctness gate'")


class Step7dAdvisoryVerbsOnly(unittest.TestCase):
    """AC-A3 (part 2): bespoke verb-scan — §7d must not contain unqualified
    enforcing verbs. This is a bespoke scan inside this test file; it does NOT
    delegate to test_advisory_controls_doc_honesty.py (§7d is not on that
    curated 5-item watch-list).
    """

    # Verbs that indicate enforcement; must be absent unless suppressed.
    BANNED_VERBS = re.compile(
        r"\b(blocks?|prevents?|rejects?|enforces?|enforcing|denies?|deny)\b",
        re.IGNORECASE,
    )
    # Any of these adjacent qualifiers suppress a hit.
    ADVISORY_QUALIFIER = re.compile(
        r"advisory|ADVISORY — NOT ENFORCED|log-only",
        re.IGNORECASE,
    )

    def test_step_7d_uses_advisory_verbs_only(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")

        # Split into sentences so the qualifier must appear in the SAME sentence
        # as the banned verb.  A fixed ±100-char window allowed an "advisory" in
        # a neighbouring sentence to suppress a banned verb in a different one,
        # producing false-greens (e.g. "It is advisory.  Step 7d enforces the
        # gate." — 76 chars apart but two distinct sentences).
        sentences = re.split(r"(?<=[.!?])\s+|\n", section)

        violations = []
        for sentence in sentences:
            m = self.BANNED_VERBS.search(sentence)
            if m and not self.ADVISORY_QUALIFIER.search(sentence):
                violations.append(
                    f"Unqualified enforcing verb '{m.group()}' in sentence: "
                    f"{sentence.strip()!r}"
                )
        self.assertEqual(
            violations, [],
            "§7d must use only advisory verbs (proposes/surfaces/emits). "
            "Violations:\n" + "\n".join(violations),
        )


class Step7dClassificationLadder(unittest.TestCase):
    """AC-A4: §7d contains the classification-ladder mapping."""

    def test_step_7d_contains_classification_ladder(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        # Bucket 1: trap → test/guard
        trap_bucket = "trap" in section.lower() or "fail-open" in section.lower()
        self.assertTrue(trap_bucket,
                        "§7d ladder must include the trap/fail-open bucket")
        # Bucket 2: always X → hook/checklist
        always_bucket = (
            ("always" in section.lower() or "must" in section.lower())
            and ("hook" in section.lower() or "checklist" in section.lower())
        )
        self.assertTrue(always_bucket,
                        "§7d ladder must include the 'always X' → hook/checklist bucket")
        # Bucket 3: factual correction → protocol one-liner
        protocol_bucket = (
            "protocol" in section.lower()
            and ("one-liner" in section.lower() or "correction" in section.lower())
        )
        self.assertTrue(protocol_bucket,
                        "§7d ladder must include the factual correction → protocol one-liner bucket")


class Step7dPromotedMarker(unittest.TestCase):
    """AC-A5: §7d documents the `promoted:` marker as a MANUAL operator step
    after PR ship, and states memory dir is code-ban-exempt.
    """

    def test_step_7d_documents_promoted_marker(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        self.assertIn("promoted", section,
                      "§7d must mention the 'promoted:' marker")
        manual_present = (
            "manually" in section.lower()
            or "manual" in section.lower()
            or "operator" in section.lower()
        )
        self.assertTrue(manual_present,
                        "§7d must describe the promoted: marker as a MANUAL operator step")
        exempt_present = (
            "code-ban" in section.lower()
            or "exempt" in section.lower()
            or "excluded from the orchestrator code ban" in section.lower()
        )
        self.assertTrue(exempt_present,
                        "§7d must state that the memory dir is excluded from the orchestrator code ban")


class Step7dSkipsOnAbsence(unittest.TestCase):
    """AC-A6: §7d states it skips (does not raise) when no durable items clear the gate."""

    def test_step_7d_skips_not_raises_on_absence(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        skip_clause = (
            "skip" in section.lower()
            and ("absence" in section.lower() or "zero" in section.lower() or "no durable" in section.lower())
        )
        self.assertTrue(skip_clause,
                        "§7d must state a skip-not-raise absence clause "
                        "(e.g. 'skip … when no durable items clear the gate')")
        # The prose may say "MUST NOT raise" (correct), but must not contain
        # an unqualified "raise".  Accept patterns like "MUST NOT raise" —
        # these confirm skip behaviour.
        import re as _re
        unguarded_raise = _re.search(r"\braise\b", section, _re.IGNORECASE) and not _re.search(
            r"must not raise|MUST NOT raise|not raise", section, _re.IGNORECASE
        )
        if unguarded_raise:
            self.fail("§7d absence handling must skip, not raise")


class Step7dSkipsAlreadyPromoted(unittest.TestCase):
    """AC-A7 (HIGH-1 loop-closure): §7d states it skips items already carrying
    a `promoted:` key.
    """

    def test_step_7d_skips_already_promoted(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        # Require 'promoted:' and a no-emit/skip phrase to co-occur in the
        # SAME sentence — loose two-presence check is a false-green risk (a prose
        # that names 'promoted:' only in the write-contract and 'skip' only in
        # absence handling would still pass the loose form).
        sentences = re.split(r"(?<=[.!?])\s+|\n", section)
        no_emit_patterns = re.compile(
            r"does not emit|no draft|skipped|skip.*promoted|not.*emit.*draft",
            re.IGNORECASE,
        )
        found = any(
            "promoted:" in s and no_emit_patterns.search(s)
            for s in sentences
        )
        self.assertTrue(
            found,
            "§7d must contain a sentence stating that items carrying a "
            "'promoted:' key are skipped / do not emit a draft",
        )


class Step7dMemoryMdExclusion(unittest.TestCase):
    """AC-A8 (HIGH-2 over-count guard): §7d states the backlink count EXCLUDES
    the MEMORY.md index and self-references.
    """

    def test_step_7d_documents_memory_md_exclusion(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        memory_md_excluded = "MEMORY.md" in section and (
            "exclud" in section.lower()
            or "except" in section.lower()
            or "not count" in section.lower()
        )
        self.assertTrue(memory_md_excluded,
                        "§7d must explicitly state that MEMORY.md is excluded from the backlink count")
        self_ref_excluded = (
            "self-reference" in section.lower()
            or "self reference" in section.lower()
            or "self-citing" in section.lower()
        )
        self.assertTrue(self_ref_excluded,
                        "§7d must explicitly state that self-references are excluded from the backlink count")


class Step7dDismissPromotion(unittest.TestCase):
    """AC-A9 (MEDIUM-3 dismissal): §7d states it does NOT emit a draft for
    items carrying `dismiss_promotion: true`.
    """

    def test_step_7d_honors_dismiss_promotion(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        # Require 'dismiss_promotion' and a no-emit phrase to co-occur in the
        # SAME sentence — assertIn alone is a false-green (the key could appear
        # only in the write-contract note without the no-emit contract).
        sentences = re.split(r"(?<=[.!?])\s+|\n", section)
        no_emit_patterns = re.compile(
            r"does not emit|no draft|skip|not.*emit|silences",
            re.IGNORECASE,
        )
        found = any(
            "dismiss_promotion" in s and no_emit_patterns.search(s)
            for s in sentences
        )
        self.assertTrue(
            found,
            "§7d must contain a sentence stating that items carrying "
            "'dismiss_promotion: true' do not emit a draft",
        )


# ---------------------------------------------------------------------------
# Slice B: Step 9 Report tests (AC-B1, AC-B2, AC-B3)
# ---------------------------------------------------------------------------

class Step9ReportMemoryPromotionSubsection(unittest.TestCase):
    """AC-B1: Step 9 report block contains the Memory Promotion Proposals subsection."""

    def test_step_9_report_has_memory_promotion_subsection(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_9(text)
        self.assertNotEqual(section, "", "Could not locate §9 in skills/learn/SKILL.md")
        self.assertIn("Memory Promotion Proposals", section,
                      "§9 report must contain 'Memory Promotion Proposals' subsection")
        self.assertIn("awaiting human approval", section,
                      "§9 report memory-promotion subsection must state 'awaiting human approval'")


class Step9SubsectionRecurrenceEvidence(unittest.TestCase):
    """AC-B2: The subsection template shows a recurrence-evidence placeholder."""

    def test_step_9_subsection_shows_recurrence_evidence(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_9(text)
        self.assertNotEqual(section, "", "Could not locate §9 in skills/learn/SKILL.md")
        recurrence_evidence = (
            "backlinks" in section.lower()
            or "evidence_count" in section.lower()
        )
        self.assertTrue(recurrence_evidence,
                        "§9 memory-promotion subsection must show a recurrence-evidence "
                        "placeholder ('backlinks' or 'evidence_count')")


class Step7dDraftBodyLeadsWithDescription(unittest.TestCase):
    """AC-B3 (MEDIUM-4 description-first): §7d prose specifies the draft body
    BEGINS with the source memory's `description` verbatim, before bucket +
    recurrence evidence.
    """

    def test_draft_body_leads_with_description(self):
        text = SKILL_PATH.read_text()
        section = _extract_step_7d(text)
        self.assertNotEqual(section, "", "Could not locate §7d in skills/learn/SKILL.md")
        description_first = (
            "description" in section.lower()
            and (
                "begin" in section.lower()
                or "leads" in section.lower()
                or "first" in section.lower()
                or "verbatim" in section.lower()
            )
        )
        self.assertTrue(description_first,
                        "§7d must state that the draft body begins with the source memory's "
                        "'description' verbatim (description-first ordering)")


# ---------------------------------------------------------------------------
# Slice C: reflection-protocol.md § 6b wire-in (AC-C1, AC-C2)
# ---------------------------------------------------------------------------

class ReflectionProtocol6bReferencesStep7d(unittest.TestCase):
    """AC-C1: reflection-protocol § 6b references Step 7d."""

    def test_reflection_protocol_6b_references_step_7d(self):
        text = REFLECTION_PROTOCOL_PATH.read_text()
        section = _extract_section_6b(text)
        self.assertNotEqual(section, "", "Could not locate § 6b in protocols/reflection-protocol.md")
        step_7d_ref = "7d" in section
        self.assertTrue(step_7d_ref,
                        "§ 6b must reference 'Step 7d'")
        memory_ref = (
            "memory promotion" in section.lower()
            or "durable memor" in section.lower()
            or "durable-memory" in section.lower()
        )
        self.assertTrue(memory_ref,
                        "§ 6b Step 7d mention must include 'memory promotion' or 'durable memories'")


class ReflectionProtocol6bReferenceIsAdvisory(unittest.TestCase):
    """AC-C2: § 6b Step 7d mention uses advisory/non-blocking framing."""

    def test_reflection_6b_reference_is_advisory(self):
        text = REFLECTION_PROTOCOL_PATH.read_text()
        section = _extract_section_6b(text)
        self.assertNotEqual(section, "", "Could not locate § 6b in protocols/reflection-protocol.md")
        # Find the paragraph that contains the 7d reference.
        # It must use advisory framing.
        idx = section.find("7d")
        self.assertNotEqual(idx, -1, "§ 6b must reference '7d'")
        window_start = max(0, idx - 200)
        window_end = min(len(section), idx + 400)
        window = section[window_start:window_end]
        advisory_present = (
            "advisory" in window.lower()
            or "non-blocking" in window.lower()
            or "does not block" in window.lower()
            or "not block" in window.lower()
        )
        self.assertTrue(advisory_present,
                        "§ 6b's Step 7d mention must use advisory/non-blocking framing. "
                        f"Window around '7d': {window!r}")


if __name__ == "__main__":
    unittest.main()
