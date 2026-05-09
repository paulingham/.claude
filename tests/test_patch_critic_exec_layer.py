"""patch-critic-exec Slice 1: documentation contract + spawn-prompt
wiring tests.

Each test slices the relevant section of a live `.md` file via
`_section(text, header_pattern, until_pattern)` and asserts
substring/regex presence inline. Mirrors the established convention
from `tests/test_autonomous_intelligence_doc_anti_pattern.py:22-60`.

These tests guard against silent doc drift on the optional
execution-evidence path:
  AC1.1 — orchestrator/parallel-dispatch-details.md gains an
          "Execution Evidence (optional, default off)" sub-section
          under § Multi-Persona Patch Critic Dispatch, naming the
          env var, default-off semantics, and three silent skip
          points.
  AC1.2 — same sub-section explicitly states once-per-slice and
          shared-across-personas semantics.
  AC1.3 — rules/_detail/autonomous-intelligence.md field-reference
          row for `phases.patch_critic` documents the OPTIONAL
          `evidence_mode` field with values
          `"diff-only" | "diff+execution"` and a backward-compat
          clause stating readers MUST tolerate absence.
  AC1.4 — agents/patch-critic.md § Inputs gains a one-paragraph note
          about the optional `## Execution Evidence` block AND
          § Rubric still contains the #93 dimension headings
          (substring presence — rubric unchanged).
  AC1.5 — execution-evidence sub-section is purely additive when
          flag off: pre-#93 step headings still present, the new
          sub-section heading appears exactly once, and the doc
          explicitly states "when flag unset → skip the entire
          sub-section, dispatch personas exactly as #93 specifies".
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DISPATCH_DOC = REPO_ROOT / "orchestrator" / "parallel-dispatch-details.md"
OBSERVATION_DOC = REPO_ROOT / "rules" / "_detail" / "autonomous-intelligence.md"
PATCH_CRITIC_DOC = REPO_ROOT / "agents" / "patch-critic.md"


def _section(text, header_pattern, until_pattern):
    """Slice `text` between the next match of header_pattern and the
    next line beginning with until_pattern (search begins on the line
    AFTER the header). Returns the section body (incl. header line).
    """
    m = re.search(header_pattern, text, re.MULTILINE)
    if not m:
        return None
    body_start = text.find("\n", m.end())
    if body_start == -1:
        return text[m.start():]
    body = text[body_start:]
    end = re.search(until_pattern, body, re.MULTILINE)
    if end is None:
        return text[m.start():]
    return text[m.start():body_start + end.start()]


class DispatchDocHasExecutionEvidenceSubsection(unittest.TestCase):
    """AC1.1 — § Multi-Persona Patch Critic Dispatch contains an
    "Execution Evidence (optional, default off)" sub-section that
    names CLAUDE_PATCH_CRITIC_EXEC_LAYER, declares default-off, and
    lists three silent skip points.
    """

    def test_dispatch_doc_has_execution_evidence_subsection(self):
        text = DISPATCH_DOC.read_text()
        section = _section(
            text,
            r"^## Multi-Persona Patch Critic Dispatch",
            r"^## ")
        self.assertIsNotNone(
            section,
            "Could not locate § Multi-Persona Patch Critic Dispatch in "
            "orchestrator/parallel-dispatch-details.md")

        # Sub-section heading
        self.assertIn(
            "### Execution Evidence (optional, default off)",
            section,
            "Multi-Persona Patch Critic Dispatch must contain "
            "'### Execution Evidence (optional, default off)' sub-section")

        # Env-var name
        self.assertIn(
            "CLAUDE_PATCH_CRITIC_EXEC_LAYER",
            section,
            "Sub-section must name the env var "
            "CLAUDE_PATCH_CRITIC_EXEC_LAYER")

        # Default-off wording (any of these phrasings is acceptable)
        lower = section.lower()
        self.assertTrue(
            "default off" in lower
            or "defaults unset" in lower
            or "default unset" in lower
            or "unset" in lower and "off" in lower,
            "Sub-section must declare the env var defaults to "
            "unset / off")

        # Three silent skip points (flag off, generator failure,
        # run/execution failure — any phrasing that names all three)
        # All three should be present as distinct skip triggers.
        self.assertIn("flag", lower,
                      "Skip-point list must mention the flag-off case")
        self.assertTrue(
            "generator" in lower or "test-input" in lower,
            "Skip-point list must mention generator/test-input failure")
        self.assertTrue(
            "run" in lower or "execution" in lower or "sandbox" in lower,
            "Skip-point list must mention run/execution failure")
        # The literal phrase "silent skip" or equivalent ("silently
        # skip") must appear in the sub-section.
        self.assertTrue(
            "silent skip" in lower or "silently skip" in lower
            or "silent fallback" in lower,
            "Sub-section must use silent-skip / silent-fallback wording")


class ExecutionEvidenceIsOncePerSlice(unittest.TestCase):
    """AC1.2 — sub-section explicitly states once-per-slice and
    that the same evidence is shared across all three personas.
    """

    def test_execution_evidence_is_once_per_slice(self):
        text = DISPATCH_DOC.read_text()
        section = _section(
            text,
            r"^### Execution Evidence \(optional, default off\)",
            r"^### |^## ")
        self.assertIsNotNone(
            section,
            "Could not locate the Execution Evidence sub-section in "
            "orchestrator/parallel-dispatch-details.md")

        self.assertIn(
            "once-per-slice",
            section,
            "Sub-section must use the literal phrase 'once-per-slice'")

        lower = section.lower()
        # "shared" near "personas" — substring match for both, AND
        # confirm at least one occurrence of "shared" sits within
        # 200 chars of an occurrence of "personas".
        self.assertIn("shared", lower,
                      "Sub-section must state evidence is shared")
        self.assertIn("personas", lower,
                      "Sub-section must reference the personas")
        positions_shared = [
            m.start() for m in re.finditer(r"shared", lower)]
        positions_personas = [
            m.start() for m in re.finditer(r"personas", lower)]
        within_window = any(
            abs(p - s) <= 200
            for s in positions_shared for p in positions_personas)
        self.assertTrue(
            within_window,
            "'shared' must appear within 200 chars of 'personas' to "
            "convey shared-across-personas semantics")


class ObservationSchemaDocumentsEvidenceModeOptional(unittest.TestCase):
    """AC1.3 — phases.patch_critic field-reference row documents
    the OPTIONAL evidence_mode field with values
    "diff-only" | "diff+execution" and a backward-compat clause
    stating readers MUST tolerate absence.
    """

    def test_observation_schema_documents_evidence_mode_optional(self):
        text = OBSERVATION_DOC.read_text()
        # Slice the Field reference table region so the search is
        # bounded to the relevant row + immediate prose. The
        # backward-compat clause sits in the prose immediately after
        # the table.
        section = _section(
            text,
            r"^#### Field reference",
            r"^### Consolidation Gate")
        self.assertIsNotNone(
            section,
            "Could not locate § Field reference in "
            "rules/_detail/autonomous-intelligence.md")

        # Field name
        self.assertIn(
            "evidence_mode",
            section,
            "phases.patch_critic row / following prose must document "
            "evidence_mode field")

        # Values — both literal strings must appear
        self.assertIn(
            '"diff-only"',
            section,
            "evidence_mode must document the value \"diff-only\"")
        self.assertIn(
            '"diff+execution"',
            section,
            "evidence_mode must document the value \"diff+execution\"")

        # Optionality
        lower = section.lower()
        self.assertTrue(
            "optional" in lower,
            "evidence_mode field must be documented as optional")

        # Backward-compat clause: "readers MUST tolerate absence"
        # (or close paraphrase). The existing pattern in the file is
        # "MUST tolerate absence" / "tolerate absence as legacy".
        self.assertTrue(
            "tolerate absence" in lower,
            "Backward-compat clause must say readers MUST tolerate "
            "absence (legacy / pre-exec-layer record)")
        self.assertTrue(
            "legacy" in lower or "pre-exec-layer" in lower,
            "Backward-compat clause must mark absence as legacy / "
            "pre-exec-layer")


class PatchCriticAgentInputsHasOptionalEvidenceNoteAndRubricUnchanged(
        unittest.TestCase):
    """AC1.4 — agents/patch-critic.md § Inputs gains a one-paragraph
    note about the optional ## Execution Evidence block, AND § Rubric
    still contains the #93 rubric dimension headings (substring
    presence — rubric unchanged).
    """

    def test_inputs_section_has_optional_evidence_note(self):
        text = PATCH_CRITIC_DOC.read_text()
        inputs = _section(
            text,
            r"^## Inputs$",
            r"^## ")
        self.assertIsNotNone(
            inputs,
            "Could not locate § Inputs in agents/patch-critic.md")

        # The new paragraph must mention the optional ## Execution
        # Evidence block AND that absence is the default.
        self.assertIn(
            "## Execution Evidence",
            inputs,
            "§ Inputs must mention the optional `## Execution "
            "Evidence` section by name")

        lower = inputs.lower()
        self.assertTrue(
            "optional" in lower,
            "§ Inputs note must call the Execution Evidence block "
            "OPTIONAL")
        self.assertTrue(
            "absence" in lower or "default" in lower,
            "§ Inputs note must state absence is the default")

        # The note must clarify the rubric is UNCHANGED — personas
        # treat the evidence as additional context for existing
        # rubric dimensions.
        self.assertTrue(
            "rubric" in lower,
            "§ Inputs note must reference the existing rubric")
        self.assertTrue(
            "unchanged" in lower
            or "additional" in lower or "context" in lower,
            "§ Inputs note must state the rubric dimensions are "
            "unchanged / evidence is additional context")

    def test_rubric_section_dimensions_unchanged(self):
        text = PATCH_CRITIC_DOC.read_text()
        rubric = _section(
            text,
            r"^## Rubric \(the four dimensions you score\)",
            r"^## ")
        self.assertIsNotNone(
            rubric,
            "Could not locate § Rubric in agents/patch-critic.md")

        # The four #93 rubric dimension headings must still be
        # present verbatim.
        for heading in (
                "### 1. Tests cover the change",
                "### 2. Diff is minimal vs intake spec",
                "### 3. No obvious regressions visible from the diff",
                "### 4. No incidental refactor",
        ):
            with self.subTest(heading=heading):
                self.assertIn(
                    heading, rubric,
                    f"§ Rubric must still contain '{heading}' "
                    "(rubric unchanged from #93)")

        # The accessibility dimension from #93 must also remain.
        self.assertIn(
            "### § 5. Accessibility",
            rubric,
            "§ Rubric must still contain the § 5 Accessibility "
            "dimension heading from #93")

        # Severity scheme heading is its own ## section — verify it
        # still exists ABOVE the rubric (slice from § Severity Scheme
        # to next ## header).
        sev = _section(
            text,
            r"^## Severity Scheme$",
            r"^## ")
        self.assertIsNotNone(
            sev,
            "agents/patch-critic.md must still contain the "
            "## Severity Scheme heading from #93")


class ExecutionEvidenceSubsectionIsPurelyAdditiveWhenFlagOff(
        unittest.TestCase):
    """AC1.5 — pre-#93 step headings in § Multi-Persona Patch Critic
    Dispatch are still present (substring match), the new sub-section
    heading appears exactly once in the file, and the doc states the
    flag-unset path dispatches personas exactly as #93 specifies.
    """

    def test_execution_evidence_subsection_is_purely_additive_when_flag_off(
            self):
        text = DISPATCH_DOC.read_text()

        # (1) Pre-#93 step headings / numbered steps still present.
        # The #93 dispatch procedure's identifying anchors:
        #   - "**Procedure (variant mode):**" intro
        #   - "1. **Gate check**" first step
        #   - "2. **Spawn three personas in a single message**"
        #   - "3. **Aggregation rule (OR)**"
        #   - "4. **Audit artifact**"
        #   - "**Composition with C8 anti-pattern mining"
        section = _section(
            text,
            r"^## Multi-Persona Patch Critic Dispatch",
            r"^## ")
        self.assertIsNotNone(
            section,
            "Could not locate § Multi-Persona Patch Critic Dispatch")

        for anchor in (
                "**Procedure (variant mode):**",
                "1. **Gate check**",
                "2. **Spawn three personas in a single message**",
                "3. **Aggregation rule (OR)**",
                "4. **Audit artifact**",
                "**Composition with C8 anti-pattern mining",
        ):
            with self.subTest(anchor=anchor):
                self.assertIn(
                    anchor, section,
                    f"Pre-#93 anchor '{anchor}' must still be present "
                    "in § Multi-Persona Patch Critic Dispatch "
                    "(additive change only)")

        # (2) New sub-section heading appears EXACTLY ONCE in the file.
        new_heading_re = (
            r"^### Execution Evidence \(optional, default off\)$")
        match_count = len(
            re.findall(new_heading_re, text, flags=re.MULTILINE))
        self.assertEqual(
            match_count, 1,
            f"'### Execution Evidence (optional, default off)' must "
            f"appear exactly once in the file; found {match_count}")

        # (3) The sub-section explicitly states the flag-unset
        # procedure: skip the entire sub-section, dispatch personas
        # exactly as #93 specifies. Substring match for the
        # signature phrasing.
        sub = _section(
            text,
            r"^### Execution Evidence \(optional, default off\)",
            r"^### |^## ")
        self.assertIsNotNone(sub)
        lower = sub.lower()
        # Combined assertion: the sub-section must say "skip" AND
        # reference dispatching personas "as #93 specifies" or
        # equivalent ("dispatch personas exactly", "fall through to
        # the existing dispatch", "no change to existing").
        self.assertTrue(
            "skip" in lower,
            "Sub-section must describe the flag-unset path as a "
            "skip")
        self.assertTrue(
            "as #93" in lower
            or "exactly as #93" in lower
            or "existing" in lower
            or "fall through" in lower
            or "fall-through" in lower
            or "purely additive" in lower
            or "additive" in lower,
            "Sub-section must state the flag-unset path dispatches "
            "personas exactly as #93 / falls through to the existing "
            "dispatch")


if __name__ == "__main__":
    unittest.main()
