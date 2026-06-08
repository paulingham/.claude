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
  AC1.3 — protocols/autonomous-intelligence.md field-reference
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
OBSERVATION_DOC = REPO_ROOT / "protocols" / "autonomous-intelligence.md"
PATCH_CRITIC_DOC = REPO_ROOT / "agents" / "patch-critic.md"
VERIFY_SKILL_DOC = REPO_ROOT / "skills" / "verify" / "SKILL.md"


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
            "protocols/autonomous-intelligence.md")

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

        # (1) The dispatch procedure headings/steps are still present. The
        # dispatch was rewritten to the uncertainty-escalated shape (persona-1
        # by default, escalate on uncertainty); these are its identifying
        # anchors. The Execution Evidence sub-section must remain purely
        # additive on top of this procedure when the flag is off.
        section = _section(
            text,
            r"^## Multi-Persona Patch Critic Dispatch",
            r"^## ")
        self.assertIsNotNone(
            section,
            "Could not locate § Multi-Persona Patch Critic Dispatch")

        for anchor in (
                "**Procedure:**",
                "1. **Spawn persona-1**",
                "2. **Read persona-1 output**",
                "3. **Escalate:",
                "4. **Aggregation rule (majority-of-3",
                "5. **Audit artifact**",
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


class GeneratorStepDocumentsTier35CostDiscipline(unittest.TestCase):
    """AC2.1 — the Step 1 generator clause inside the Execution
    Evidence sub-section documents the Tier 3.5 cost-guardrail
    pattern verbatim: ONE call, NO retry, max-N-items, silent skip,
    diff-only fallback.
    """

    def test_generator_step_documents_tier_35_cost_discipline(self):
        text = DISPATCH_DOC.read_text()
        sub = _section(
            text,
            r"^### Execution Evidence \(optional, default off\)",
            r"^### |^## ")
        self.assertIsNotNone(
            sub,
            "Could not locate the Execution Evidence sub-section")

        # Step 1 heading must exist within the sub-section.
        self.assertRegex(
            sub,
            r"\*\*Step 1 [—-] Generate discriminative test inputs\*\*",
            "Sub-section must contain a 'Step 1 — Generate "
            "discriminative test inputs' heading")

        # Slice the Step 1 body for tighter assertions.
        step1 = _section(
            sub,
            r"\*\*Step 1 [—-] Generate discriminative test inputs\*\*",
            r"^\*\*Step \d|^### |^## ")
        self.assertIsNotNone(step1, "Could not slice Step 1 body")

        # Verbatim cost-guardrail phrases inherited from Tier 3.5
        # § 4.25:
        #   - "ONE call"
        self.assertIn(
            "ONE call",
            step1,
            "Step 1 must use the verbatim phrase 'ONE call' "
            "(inherited from Tier 3.5 § 4.25 cost-guardrail)")

        #   - "NO retry"
        self.assertIn(
            "NO retry",
            step1,
            "Step 1 must use the verbatim phrase 'NO retry' "
            "(inherited from Tier 3.5 § 4.25 cost-guardrail)")

        #   - max-N-items pattern: "max 3 inputs" or equivalent regex
        self.assertRegex(
            step1,
            r"max\s+\d+\s+inputs",
            "Step 1 must document a 'max N inputs' cap "
            "(per-response upper bound; Tier 3.5 § 4.25 cost-guardrail)")

        #   - "silent skip" / "silently skip"
        lower = step1.lower()
        self.assertTrue(
            "silent skip" in lower or "silently skip" in lower,
            "Step 1 must use 'silent skip' / 'silently skip' "
            "wording for the failure-fallthrough semantics")

        #   - "diff-only" fallback name
        self.assertIn(
            "diff-only",
            step1,
            "Step 1 must reference the 'diff-only' fallback path")


class GeneratorJsonSchemaDocumented(unittest.TestCase):
    """AC2.2 — the Step 1 generator clause documents the JSON schema
    with three required fields per input: description, input,
    expected_distinction; with their types named.
    """

    def test_generator_json_schema_documented(self):
        text = DISPATCH_DOC.read_text()
        sub = _section(
            text,
            r"^### Execution Evidence \(optional, default off\)",
            r"^### |^## ")
        self.assertIsNotNone(sub)

        step1 = _section(
            sub,
            r"\*\*Step 1 [—-] Generate discriminative test inputs\*\*",
            r"^\*\*Step \d|^### |^## ")
        self.assertIsNotNone(step1, "Could not slice Step 1 body")

        # All three required field names must appear in the schema.
        for field in ("description", "input", "expected_distinction"):
            with self.subTest(field=field):
                self.assertIn(
                    field, step1,
                    f"Step 1 JSON schema must document the required "
                    f"field '{field}'")

        # Types must be documented. The plan calls for:
        #   description: string
        #   input: string|object  (any of: "string|object", "string or
        #                          object", "string/object")
        #   expected_distinction: string
        # We assert "string" appears (covers description +
        # expected_distinction) AND a marker for the input field's
        # union type appears.
        self.assertIn(
            "string", step1,
            "Step 1 JSON schema must name the 'string' type for "
            "description / expected_distinction fields")
        self.assertRegex(
            step1,
            r"string\s*[|/]\s*object|string or object",
            "Step 1 JSON schema must document the 'input' field as "
            "'string|object' (or 'string or object' / 'string/object')")


class GeneratorFailureFallsThroughToDiffOnly(unittest.TestCase):
    """AC2.3 — Step 1 failure paths (timeout / parse-failure /
    zero-non-equivalent / output-over-cap / control-char-strip) all
    fall through to diff-only dispatch via the silent-skip semantics.
    The "output-over-cap" and "control-char-strip" clauses encode the
    sanitization guidance from the security-engineer scratchpad
    warning (LLM output untrusted; cap byte length, strip control
    chars, refuse oversized JSON).

    The test enforces at least 4 of the 5 listed sanitization /
    failure clauses (treating output-over-cap + control-char-strip
    together as the sanitization concern).
    """

    def test_generator_failure_falls_through_to_diff_only(self):
        text = DISPATCH_DOC.read_text()
        sub = _section(
            text,
            r"^### Execution Evidence \(optional, default off\)",
            r"^### |^## ")
        self.assertIsNotNone(sub)

        step1 = _section(
            sub,
            r"\*\*Step 1 [—-] Generate discriminative test inputs\*\*",
            r"^\*\*Step \d|^### |^## ")
        self.assertIsNotNone(step1, "Could not slice Step 1 body")

        lower = step1.lower()

        # Five failure / sanitization clauses (≥4 of 5 required).
        clauses = {
            "timeout": "timeout" in lower or "times out" in lower,
            "parse-failure": (
                "parse failure" in lower
                or "parse-failure" in lower
                or "malformed" in lower),
            "zero-non-equivalent": (
                "zero non-equivalent" in lower
                or "zero non-equivalent inputs" in lower
                or "no non-equivalent" in lower
                or "zero inputs" in lower),
            "output-over-cap": (
                "over cap" in lower
                or "over-cap" in lower
                or "oversized" in lower
                or "exceeds" in lower
                or "byte cap" in lower
                or "size cap" in lower),
            "control-char-strip": (
                "control char" in lower
                or "control-char" in lower
                or "control character" in lower
                or "0x20" in lower),
        }
        present_count = sum(1 for v in clauses.values() if v)
        missing = [k for k, v in clauses.items() if not v]
        self.assertGreaterEqual(
            present_count, 4,
            f"Step 1 must document at least 4 of 5 failure / "
            f"sanitization clauses. Missing: {missing}")

        # "silent skip" / "silently skip" must be present (links the
        # failure clauses to the documented fallback semantics).
        self.assertTrue(
            "silent skip" in lower or "silently skip" in lower,
            "Step 1 must say the failure path triggers a silent skip")

        # Documented behavior on each failure → fall through to
        # diff-only dispatch. Cross-reference to AC1.5's flag-off
        # path is the wording: "diff-only" appears alongside the
        # fallback semantics and either "fall through" / "fall-through"
        # / "as #93" / "Step 0" / "flag off" / "flag-off" appears
        # nearby (showing the equivalence to Slice 1's flag-off
        # silent path).
        self.assertIn(
            "diff-only",
            step1,
            "Step 1 must document the fallback path as 'diff-only'")
        cross_ref_present = (
            "fall through" in lower
            or "fall-through" in lower
            or "as #93" in lower
            or "step 0" in lower
            or "flag off" in lower
            or "flag-off" in lower
            or "same path" in lower
            or "same fallback" in lower
            or "same as" in lower)
        self.assertTrue(
            cross_ref_present,
            "Step 1 must cross-reference AC1.5's flag-off path "
            "(via 'fall through' / 'as #93' / 'same as Step 0' / "
            "'same fallback' wording)")


class VerifySkillCrossReferencesPatchCriticExecLayer(unittest.TestCase):
    """AC2.4 — `skills/verify/SKILL.md` § Tier 3.5 contains a one-line
    cross-reference to `orchestrator/parallel-dispatch-details.md`
    § Multi-Persona Patch Critic Dispatch / Execution Evidence reusing
    the same call-shape pattern. The Tier 3.5 procedure body itself
    MUST remain unchanged — only the appended cross-reference line is
    new (canonical Tier 3.5 phrases must still be present).
    """

    def test_verify_skill_cross_references_patch_critic_exec_layer(self):
        text = VERIFY_SKILL_DOC.read_text()
        # Slice § Tier 3.5 (the LLM-Mutant Pass section, anchored at
        # the "### 4.25." heading).
        section = _section(
            text,
            r"^### 4\.25\. Run Tier 3\.5",
            r"^### 4\.5\.|^### 5\.|^## ")
        self.assertIsNotNone(
            section,
            "Could not locate § Tier 3.5 (### 4.25.) in "
            "skills/verify/SKILL.md")

        # The cross-reference must name the target file path AND the
        # target sub-section. Both substrings must appear.
        self.assertIn(
            "orchestrator/parallel-dispatch-details.md",
            section,
            "Tier 3.5 must contain a cross-reference to "
            "'orchestrator/parallel-dispatch-details.md'")
        self.assertIn(
            "Multi-Persona Patch Critic",
            section,
            "Tier 3.5 cross-reference must name § Multi-Persona "
            "Patch Critic (Dispatch / Execution Evidence)")
        self.assertIn(
            "Execution Evidence",
            section,
            "Tier 3.5 cross-reference must name the Execution "
            "Evidence sub-section explicitly")

        # The canonical Tier 3.5 procedure phrases MUST still be
        # present (procedure body unchanged besides the appended
        # cross-reference line).
        for phrase in (
                "ONE Claude call per slice",
                "NO retry",
                "max 10 mutants per response",
                "Equivalence filter",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(
                    phrase, section,
                    f"Tier 3.5 procedure must still contain the "
                    f"canonical phrase '{phrase}' "
                    "(procedure body unchanged besides cross-reference)")


class SandboxedRunDocumentsApplyTestRevertLoop(unittest.TestCase):
    """AC3.1 — the Step 2 run clause inside the Execution Evidence
    sub-section documents the apply-test-revert loop pattern (scratch
    worktree OR git stash, apply diff, execute against input, capture
    output, revert) AND references Tier 3.5's apply-test-revert
    pattern.
    """

    def test_sandboxed_run_documents_apply_test_revert_loop(self):
        text = DISPATCH_DOC.read_text()
        sub = _section(
            text,
            r"^### Execution Evidence \(optional, default off\)",
            r"^### |^## ")
        self.assertIsNotNone(
            sub,
            "Could not locate the Execution Evidence sub-section")

        # Step 2 heading must exist within the sub-section.
        self.assertRegex(
            sub,
            r"\*\*Step 2 [—-] Run candidate against discriminative inputs\*\*",
            "Sub-section must contain a 'Step 2 — Run candidate "
            "against discriminative inputs' heading")

        # Slice the Step 2 body for tighter assertions.
        step2 = _section(
            sub,
            r"\*\*Step 2 [—-] Run candidate against discriminative inputs\*\*",
            r"^\*\*Step \d|^### |^## ")
        self.assertIsNotNone(step2, "Could not slice Step 2 body")
        lower = step2.lower()

        # Apply-test-revert loop phrases. The plan AC3.1 stub names
        # five distinct phrases; each must be present.
        self.assertTrue(
            "scratch worktree" in lower or "git stash" in lower,
            "Step 2 must mention either a scratch worktree or "
            "git stash snapshot mechanism")
        self.assertTrue(
            "apply" in lower and ("diff" in lower or "patch" in lower
                                  or "candidate" in lower),
            "Step 2 must describe applying the diff / patch / "
            "candidate")
        self.assertTrue(
            "execute" in lower or "run" in lower,
            "Step 2 must describe executing / running against the "
            "discriminative input")
        self.assertTrue(
            "capture" in lower
            and ("stdout" in lower or "stderr" in lower
                 or "output" in lower),
            "Step 2 must describe capturing output (stdout/stderr)")
        self.assertTrue(
            "revert" in lower,
            "Step 2 must describe reverting before the next input")

        # Tier 3.5 cross-reference: must point back to Tier 3.5's
        # apply-test-revert loop. The canonical reference shape is
        # § 4.25 in skills/verify/SKILL.md.
        self.assertTrue(
            "tier 3.5" in lower or "4.25" in lower,
            "Step 2 must reference Tier 3.5 (or § 4.25) as the source "
            "of the apply-test-revert pattern")


class PerInputTimeoutDocumented(unittest.TestCase):
    """AC3.2 — Step 2 documents a per-input timeout integer (regex
    `\\b\\d+(?:s|ms| seconds)\\b`) AND uses the phrase "orchestrator-
    side" or "no new env var" to make clear the timeout is a
    documented value rather than a configurable env var.
    """

    def test_per_input_timeout_documented(self):
        text = DISPATCH_DOC.read_text()
        sub = _section(
            text,
            r"^### Execution Evidence \(optional, default off\)",
            r"^### |^## ")
        self.assertIsNotNone(sub)

        step2 = _section(
            sub,
            r"\*\*Step 2 [—-] Run candidate against discriminative inputs\*\*",
            r"^\*\*Step \d|^### |^## ")
        self.assertIsNotNone(step2, "Could not slice Step 2 body")

        # Per-input timeout integer present.
        self.assertRegex(
            step2,
            r"\b\d+(?:s|ms| seconds)\b",
            "Step 2 must document a per-input timeout integer "
            "(e.g. '30s', '500ms', '60 seconds')")

        # Documented-value, not env-var, wording.
        lower = step2.lower()
        self.assertTrue(
            "orchestrator-side" in lower or "no new env var" in lower,
            "Step 2 must use the phrase 'orchestrator-side' or "
            "'no new env var' to mark the timeout as a documented "
            "value (NOT a new operator-tunable env var)")


class RunFailureFallsThroughToDiffOnly(unittest.TestCase):
    """AC3.3 — Step 2 enumerates at least three run-failure modes
    (sandbox unavailable, no inferable entry point, all inputs time
    out) AND each falls through to diff-only dispatch. The slice 2
    security scratchpad pattern requires that the new failures roll
    up into the existing "Run / execution failure" skip point —
    verified separately by absence of any NEW top-level skip-point
    heading (the "Three silent skip points" enumeration must remain
    Flag off / Generator failure / Run failure).
    """

    def test_run_failure_falls_through_to_diff_only(self):
        text = DISPATCH_DOC.read_text()
        sub = _section(
            text,
            r"^### Execution Evidence \(optional, default off\)",
            r"^### |^## ")
        self.assertIsNotNone(sub)

        step2 = _section(
            sub,
            r"\*\*Step 2 [—-] Run candidate against discriminative inputs\*\*",
            r"^\*\*Step \d|^### |^## ")
        self.assertIsNotNone(step2, "Could not slice Step 2 body")
        lower = step2.lower()

        # Three run-failure modes (sandbox unavailable, no entry point,
        # all inputs timeout) — all three must be present.
        self.assertTrue(
            "sandbox" in lower
            and ("unavailable" in lower or "missing" in lower
                 or "absent" in lower),
            "Step 2 must list 'sandbox unavailable' as a run-failure "
            "mode")
        self.assertTrue(
            ("entry point" in lower or "entrypoint" in lower)
            and ("no inferable" in lower or "cannot infer" in lower
                 or "not inferable" in lower or "no entry" in lower),
            "Step 2 must list 'no inferable entry point' as a "
            "run-failure mode")
        self.assertTrue(
            ("all inputs" in lower and ("time out" in lower
                                         or "timeout" in lower
                                         or "timed out" in lower))
            or "all inputs time out" in lower,
            "Step 2 must list 'all inputs time out' as a run-failure "
            "mode")

        # Documented behavior: silent skip → diff-only.
        self.assertTrue(
            "silent skip" in lower or "silently skip" in lower,
            "Step 2 must say run-failure triggers a silent skip")
        self.assertIn(
            "diff-only",
            step2,
            "Step 2 must document the fallback as 'diff-only'")

        # The "Three silent skip points" enumeration must NOT have
        # been expanded — verify the SUB-section's three-skip-point
        # list still has exactly three top-level entries, and the
        # third entry still names "Run / execution failure" (the
        # roll-up the security scratchpad mandates).
        skip_points_re = (
            r"\*\*Three silent skip points\*\*[\s\S]*?"
            r"\n1\.\s.*?\n2\.\s.*?\n3\.\s[^\n]*?(\n[\n#]|$)")
        m = re.search(skip_points_re, sub)
        self.assertIsNotNone(
            m,
            "Sub-section must contain the 'Three silent skip points' "
            "enumeration with exactly three top-level entries")
        # Third entry must still mention 'run' / 'execution'.
        skip_block = m.group(0).lower()
        self.assertTrue(
            "run" in skip_block or "execution" in skip_block,
            "Third skip point must still name 'Run' or 'execution' "
            "failure — new run-failures roll up there, do NOT "
            "introduce a 4th top-level skip point")


class EvidenceBlockFormatDocumented(unittest.TestCase):
    """AC3.4 — Step 3 documents the `## Execution Evidence` block
    format with five fields per input (input description, input value,
    run output stdout/stderr, exit code, elapsed-ms). Block is
    identical across personas (once-per-slice contract).
    """

    def test_evidence_block_format_documented(self):
        text = DISPATCH_DOC.read_text()
        sub = _section(
            text,
            r"^### Execution Evidence \(optional, default off\)",
            r"^### |^## ")
        self.assertIsNotNone(sub)

        # Step 3 heading must exist within the sub-section.
        self.assertRegex(
            sub,
            r"\*\*Step 3 [—-] Format and append evidence\*\*",
            "Sub-section must contain a 'Step 3 — Format and append "
            "evidence' heading")

        step3 = _section(
            sub,
            r"\*\*Step 3 [—-] Format and append evidence\*\*",
            r"^\*\*Step \d|^### |^## ")
        self.assertIsNotNone(step3, "Could not slice Step 3 body")
        lower = step3.lower()

        # Five fields per input.
        self.assertTrue(
            "description" in lower,
            "Step 3 must document the 'description' field")
        self.assertTrue(
            "input" in lower,
            "Step 3 must document the 'input' value field")
        self.assertTrue(
            "stdout" in lower or "stderr" in lower or "output" in lower,
            "Step 3 must document the run output (stdout / stderr) "
            "field")
        self.assertTrue(
            "exit" in lower
            and ("code" in lower or "marker" in lower or "status" in lower),
            "Step 3 must document the 'exit code' field")
        self.assertTrue(
            "elapsed" in lower
            and ("ms" in lower or "millisecond" in lower or "time" in lower),
            "Step 3 must document the 'elapsed-ms' / elapsed-time "
            "field")

        # Identical-across-personas wording.
        self.assertTrue(
            "identical across" in lower
            or "identical across personas" in lower
            or "once-per-slice" in lower,
            "Step 3 must state the block is identical across personas "
            "or use the 'once-per-slice' contract phrasing")


class PersonaSpawnExamplesShowOptionalEvidencePlaceholder(
        unittest.TestCase):
    """AC3.5 — each of the three persona Agent example blocks
    (`patch-critic-correctness`, `patch-critic-regression-risk`,
    `patch-critic-scope-creep`) shows the optional `## Execution
    Evidence` placeholder line inside the prompt template, with a
    comment marking it conditionally injected.
    """

    def test_persona_spawn_examples_show_optional_evidence_placeholder(
            self):
        text = DISPATCH_DOC.read_text()
        # Slice § Multi-Persona Patch Critic Dispatch (the parent
        # section that contains all three persona examples).
        section = _section(
            text,
            r"^## Multi-Persona Patch Critic Dispatch",
            r"^## ")
        self.assertIsNotNone(
            section,
            "Could not locate § Multi-Persona Patch Critic Dispatch")

        for persona in (
                "patch-critic-correctness",
                "patch-critic-regression-risk",
                "patch-critic-scope-creep",
        ):
            with self.subTest(persona=persona):
                # Slice each persona Agent block. The block begins at
                # the `name: "<persona>"` line and ends at the next
                # `})` (closing of the Agent call).
                pattern = (
                    r'name:\s*"' + re.escape(persona)
                    + r'"[\s\S]*?\}\)')
                m = re.search(pattern, section)
                self.assertIsNotNone(
                    m,
                    f"Could not slice the Agent block for "
                    f"persona '{persona}'")
                block = m.group(0)
                lower = block.lower()

                # The placeholder line must appear inside the prompt.
                self.assertIn(
                    "## Execution Evidence",
                    block,
                    f"Persona '{persona}' spawn example must contain "
                    "the optional '## Execution Evidence' placeholder "
                    "line inside its prompt template")

                # A comment marking it conditionally injected must be
                # present — accept any of these substrings.
                self.assertTrue(
                    "conditionally injected" in lower
                    or "conditional injection" in lower
                    or "injected only when" in lower,
                    f"Persona '{persona}' must mark the placeholder "
                    "with a 'conditionally injected' (or equivalent) "
                    "comment")


class RubricUnchangedWhenEvidencePresent(unittest.TestCase):
    """AC3.6 — re-asserts the AC1.4 invariant under post-Slice-3
    state: the rubric dimension headings + severity scheme heading in
    `agents/patch-critic.md` are unchanged from #93.

    The presence of the optional `## Execution Evidence` block in
    Slice 3 does not alter the rubric section bytes — this test
    re-verifies the rubric contract holds after Slice 3 lands.
    """

    def test_rubric_unchanged_when_evidence_present(self):
        text = PATCH_CRITIC_DOC.read_text()
        rubric = _section(
            text,
            r"^## Rubric \(the four dimensions you score\)",
            r"^## ")
        self.assertIsNotNone(
            rubric,
            "Could not locate § Rubric in agents/patch-critic.md")

        for heading in (
                "### 1. Tests cover the change",
                "### 2. Diff is minimal vs intake spec",
                "### 3. No obvious regressions visible from the diff",
                "### 4. No incidental refactor",
                "### § 5. Accessibility",
        ):
            with self.subTest(heading=heading):
                self.assertIn(
                    heading, rubric,
                    f"§ Rubric must still contain '{heading}' after "
                    "Slice 3 lands (rubric unchanged from #93)")

        # § Severity Scheme heading must still exist as its own
        # ## section.
        sev = _section(
            text,
            r"^## Severity Scheme$",
            r"^## ")
        self.assertIsNotNone(
            sev,
            "agents/patch-critic.md must still contain the "
            "## Severity Scheme heading from #93 after Slice 3")


class NoCommittedFileExportsPatchCriticExecLayerFlag(unittest.TestCase):
    """AC3.7 — committed-invariant grep guard. No file under
    `hooks/`, `tests/`, `skills/`, `agents/`, or `orchestrator/` may
    contain a line that exports `CLAUDE_PATCH_CRITIC_EXEC_LAYER=1` —
    either via shell `export` or as a `VAR=val command` env-prefix.

    Code spans containing the literal `` `CLAUDE_PATCH_CRITIC_EXEC_LAYER=1` ``
    (markdown backticks) are NOT exports — exclude lines whose match
    is fully contained inside backticks.

    Excluded include-roots: `pipeline-state/**`, top-level
    CHANGELOG-style files. Self-test fixtures embedded in the test
    body verify the regex doesn't false-positive on backticked code
    spans and DOES catch unquoted exports.
    """

    INCLUDE_ROOTS = ("hooks", "tests", "skills", "agents", "orchestrator")
    EXPORT_RE = re.compile(
        r"export\s+CLAUDE_PATCH_CRITIC_EXEC_LAYER\s*=\s*1")
    PREFIX_RE = re.compile(
        r"^\s*CLAUDE_PATCH_CRITIC_EXEC_LAYER\s*=\s*1\s+"
        r"(?:bash|sh|exec|\S+\.(?:sh|bash))")

    def _line_matches_outside_quotes(self, line):
        """Return True iff a forbidden export pattern matches AND the
        match is NOT fully contained inside a quoted span on the same
        line. Quoted spans are: backtick code spans (`...`),
        Python/shell single-quoted strings ('...'), or Python/shell
        double-quoted strings ("...").

        The security-engineer scratchpad's pattern note pins
        "test-assertion string literals" as non-exports alongside
        documentation prose and code spans. Pairing each quote
        character independently captures all three forms.
        """
        spans_for_char = {}
        for ch in ("`", '"', "'"):
            positions = [i for i, c in enumerate(line) if c == ch]
            spans_for_char[ch] = list(zip(
                positions[0::2], positions[1::2]))

        def inside_any_quote(start, end):
            for spans in spans_for_char.values():
                for s, e in spans:
                    if s < start and end <= e + 1:
                        return True
            return False

        for pattern in (self.EXPORT_RE, self.PREFIX_RE):
            for m in pattern.finditer(line):
                if not inside_any_quote(m.start(), m.end()):
                    return True
        return False

    def test_self_fixture_backticked_code_span_does_not_match(self):
        # A backtick-enclosed reference is NOT an export.
        line = "    - Operators may opt in via `CLAUDE_PATCH_CRITIC_EXEC_LAYER=1` in their session."
        self.assertFalse(
            self._line_matches_outside_quotes(line),
            "Backticked code span must NOT trigger the AC3.7 grep "
            "guard (false-positive control)")

    def test_self_fixture_unquoted_export_does_match(self):
        # An unquoted shell export DOES trigger the guard.
        line = "export CLAUDE_PATCH_CRITIC_EXEC_LAYER=1"
        self.assertTrue(
            self._line_matches_outside_quotes(line),
            "Unquoted shell export MUST trigger the AC3.7 grep "
            "guard")

    def test_self_fixture_env_prefix_command_does_match(self):
        # Env-prefix-then-command form (e.g.
        # `CLAUDE_PATCH_CRITIC_EXEC_LAYER=1 bash run.sh`).
        line = "CLAUDE_PATCH_CRITIC_EXEC_LAYER=1 bash run.sh"
        self.assertTrue(
            self._line_matches_outside_quotes(line),
            "Env-prefix-then-command form MUST trigger the AC3.7 "
            "grep guard")

    def test_no_committed_file_exports_patch_critic_exec_layer_flag(
            self):
        violations = []
        for root in self.INCLUDE_ROOTS:
            base = REPO_ROOT / root
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                # Skip non-text files defensively.
                try:
                    content = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for lineno, line in enumerate(content.splitlines(),
                                              start=1):
                    if self._line_matches_outside_quotes(line):
                        rel = path.relative_to(REPO_ROOT)
                        violations.append(
                            f"{rel}:{lineno}: {line.strip()}")

        self.assertEqual(
            violations, [],
            "Found committed file(s) exporting "
            "CLAUDE_PATCH_CRITIC_EXEC_LAYER=1 outside allowed zones "
            "(self-reference shield violation):\n"
            + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
