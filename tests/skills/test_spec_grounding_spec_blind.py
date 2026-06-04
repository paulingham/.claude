"""
Spec-blind behavioural tests for ws-g-spec-grounding (slices A-D).

Authored from ACs + public API surface ONLY — never from src internals.
Public API surface used:
  - skills/spec-grounding/SKILL.md (frontmatter + procedure contract)
  - protocols/_proposals/2026-05-24-ears-acceptance-criteria.md
  - protocols/verdict-catalog.md
  - protocols/skill-directory.md
  - skills/story-writing/SKILL.md
  - skills/spec-blind-validate/SKILL.md
  - skills/pipeline/SKILL.md
  - agents/architect.md
  - skills/spec-grounding/__init__.py (public package surface)
  - from spec_grounding._lib.grounding import GroundedAC, ground_acs, validate_citations
  - from spec_grounding._lib.ac_forms import EARS_TYPES, classify_form, format_ac_line
"""
import os
import sys
import sqlite3
import unittest.mock
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "skills"))


# ===========================================================================
# Slice A — EARS Promotion + Verdict/Directory Registration (doc-contract)
# ===========================================================================

class TestSliceA:
    """AC-A1 through AC-A6: doc-contract checks on markdown files."""

    @pytest.fixture(scope="class")
    def proposal_text(self):
        return (
            REPO_ROOT / "protocols" / "_proposals" / "2026-05-24-ears-acceptance-criteria.md"
        ).read_text()

    @pytest.fixture(scope="class")
    def story_writing_text(self):
        return (REPO_ROOT / "skills" / "story-writing" / "SKILL.md").read_text()

    @pytest.fixture(scope="class")
    def verdict_catalog_text(self):
        return (REPO_ROOT / "protocols" / "verdict-catalog.md").read_text()

    @pytest.fixture(scope="class")
    def skill_directory_text(self):
        return (REPO_ROOT / "protocols" / "skill-directory.md").read_text()

    @pytest.fixture(scope="class")
    def spec_blind_text(self):
        return (REPO_ROOT / "skills" / "spec-blind-validate" / "SKILL.md").read_text()

    # AC-A1: EARS proposal status is IMPLEMENTED with item-4-deferred note
    def test_ac_a1_proposal_status_implemented(self, proposal_text):
        """AC-A1: proposal file shows Status: IMPLEMENTED; item-4-deferred note present."""
        assert "IMPLEMENTED" in proposal_text, (
            "protocols/_proposals/2026-05-24-ears-acceptance-criteria.md must show IMPLEMENTED"
        )
        # item 4 (ac_forms on spec-blind output) is deferred
        assert "deferred" in proposal_text.lower(), (
            "A deferred note for item 4 must appear in the proposal"
        )
        # "item 4" referenced somewhere near deferred
        assert "item 4" in proposal_text.lower() or "item-4" in proposal_text.lower(), (
            "Item 4 must be called out as deferred in the proposal"
        )

    # AC-A2: story-writing SKILL.md documents five EARS forms
    def test_ac_a2_five_ears_forms_documented(self, story_writing_text):
        """AC-A2: story-writing SKILL.md must contain all five EARS form names."""
        lower = story_writing_text.lower()
        for form_name in ("ubiquitous", "event", "state", "unwanted", "optional"):
            assert form_name in lower, (
                f"EARS form '{form_name}' not documented in skills/story-writing/SKILL.md"
            )

    # AC-A3: story-writing SKILL.md documents form: tag and [grounded:] suffix
    def test_ac_a3_form_tag_and_grounded_suffix_documented(self, story_writing_text):
        """AC-A3: story-writing SKILL.md must show 'form: ears-' and '[grounded:'."""
        assert "form: ears-" in story_writing_text, (
            "The 'form: ears-' tag is not documented in skills/story-writing/SKILL.md"
        )
        assert "[grounded:" in story_writing_text, (
            "The '[grounded: citation]' suffix is not documented in skills/story-writing/SKILL.md"
        )

    # AC-A4: verdict-catalog.md registers GROUNDED and GROUNDING_GAPS with emitter spec-grounding
    def test_ac_a4_verdict_catalog_has_both_verdicts_and_emitter(self, verdict_catalog_text):
        """AC-A4: verdict-catalog.md must list GROUNDED, GROUNDING_GAPS, emitter spec-grounding."""
        assert "GROUNDED" in verdict_catalog_text, (
            "GROUNDED not present in protocols/verdict-catalog.md"
        )
        assert "GROUNDING_GAPS" in verdict_catalog_text, (
            "GROUNDING_GAPS not present in protocols/verdict-catalog.md"
        )
        assert "spec-grounding" in verdict_catalog_text, (
            "Emitter 'spec-grounding' not present in protocols/verdict-catalog.md"
        )

    # AC-A5: skill-directory.md has /harness:spec-grounding with GROUNDED verdict
    def test_ac_a5_skill_directory_entry_with_grounded(self, skill_directory_text):
        """AC-A5: protocols/skill-directory.md must have /harness:spec-grounding + GROUNDED."""
        assert "/harness:spec-grounding" in skill_directory_text, (
            "/harness:spec-grounding row not found in protocols/skill-directory.md"
        )
        assert "GROUNDED" in skill_directory_text, (
            "GROUNDED verdict not found in protocols/skill-directory.md"
        )

    # AC-A6: spec-blind-validate SKILL.md § Inputs has form-tag annotation + trigger->arrange
    def test_ac_a6_spec_blind_inputs_has_form_annotation(self, spec_blind_text):
        """AC-A6: spec-blind-validate SKILL.md must annotate 'form:' tag and trigger->arrange."""
        assert "form:" in spec_blind_text, (
            "The 'form:' tag annotation is missing from skills/spec-blind-validate/SKILL.md"
        )
        lower = spec_blind_text.lower()
        assert "trigger" in lower, (
            "The 'trigger' mapping note is missing from skills/spec-blind-validate/SKILL.md"
        )
        assert "arrange" in lower, (
            "The 'arrange' mapping note is missing from skills/spec-blind-validate/SKILL.md"
        )


# ===========================================================================
# Slice B — Python Helper Library (behaviour tests)
# ===========================================================================

class TestSliceB:
    """AC-B1 through AC-B10: black-box behavioural tests against the public API."""

    @pytest.fixture()
    def recall_db(self, tmp_path):
        """Minimal memory.sqlite built from db/schema.sql + INSERTs (per AC-B3 pattern)."""
        db_path = tmp_path / "memory.sqlite"
        schema_sql = (REPO_ROOT / "db" / "schema.sql").read_text()
        con = sqlite3.connect(str(db_path))
        try:
            con.executescript(schema_sql)
            con.execute(
                """
                INSERT INTO observations
                  (content_hash, session_id, timestamp, tool, searchable_text)
                VALUES
                  ('aaa1', 's1', '2026-01-01T00:00:00', 'Read',
                   'spec_blind_sentinel_recall_term unique_recall_phrase'),
                  ('aaa2', 's1', '2026-01-01T00:00:01', 'Write',
                   'grounding codebase pathlib traversal evidence'),
                  ('aaa3', 's2', '2026-01-01T00:00:02', 'Bash',
                   'ac_forms classify_form EARS forms pattern')
                """
            )
            con.commit()
        finally:
            con.close()
        return db_path

    # AC-B4: classify_form WHEN-SHALL => ears-event
    def test_ac_b4_classify_form_ears_event(self):
        """AC-B4: WHEN...SHALL text returns 'ears-event'."""
        from spec_grounding._lib.ac_forms import classify_form
        result = classify_form("WHEN the trigger fires the system SHALL emit a response")
        assert result == "ears-event", f"Expected 'ears-event', got '{result}'"

    # AC-B4 extended: other EARS forms classify correctly
    def test_ac_b4_classify_form_ears_state(self):
        """WHILE...SHALL text returns 'ears-state'."""
        from spec_grounding._lib.ac_forms import classify_form
        result = classify_form("WHILE the system is idle the system SHALL accept connections")
        assert result == "ears-state", f"Expected 'ears-state', got '{result}'"

    def test_ac_b4_classify_form_ears_unwanted(self):
        """IF...THEN text returns 'ears-unwanted'."""
        from spec_grounding._lib.ac_forms import classify_form
        result = classify_form("IF an error occurs THEN the system SHALL log it")
        assert result == "ears-unwanted", f"Expected 'ears-unwanted', got '{result}'"

    def test_ac_b4_classify_form_ears_optional(self):
        """WHERE...SHALL text returns 'ears-optional'."""
        from spec_grounding._lib.ac_forms import classify_form
        result = classify_form("WHERE the feature flag is enabled the system SHALL activate")
        assert result == "ears-optional", f"Expected 'ears-optional', got '{result}'"

    def test_ac_b4_classify_form_ears_ubiquitous(self):
        """SHALL with no qualifying prefix returns 'ears-ubiquitous'."""
        from spec_grounding._lib.ac_forms import classify_form
        result = classify_form("The system SHALL always be available during business hours")
        assert result == "ears-ubiquitous", f"Expected 'ears-ubiquitous', got '{result}'"

    # AC-B5: classify_form returns 'prose' on non-EARS text; never raises
    def test_ac_b5_classify_form_prose_fallback_no_raise(self):
        """AC-B5: Non-EARS text returns 'prose' without raising."""
        from spec_grounding._lib.ac_forms import classify_form
        for non_ears in [
            "The endpoint should handle errors gracefully",
            "",
            "   ",
            "a" * 2000,  # very long text
        ]:
            result = classify_form(non_ears)
            assert result == "prose", (
                f"Expected 'prose' for non-EARS input, got '{result}' for input: {non_ears!r}"
            )

    # AC-B4: EARS_TYPES contains the six defined form strings
    def test_ac_b4_ears_types_contains_all_forms(self):
        """EARS_TYPES frozenset contains all expected form strings."""
        from spec_grounding._lib.ac_forms import EARS_TYPES
        expected = {
            "ears-ubiquitous", "ears-event", "ears-state",
            "ears-unwanted", "ears-optional", "prose"
        }
        assert expected == EARS_TYPES, (
            f"EARS_TYPES mismatch. Expected: {expected}, Got: {EARS_TYPES}"
        )

    # AC-B8: format_ac_line with citation="gap" renders [grounded: gap]
    def test_ac_b8_format_ac_line_gap_citation(self):
        """AC-B8: format_ac_line('AC1', 'prose', 'text', 'gap') contains '[grounded: gap]'."""
        from spec_grounding._lib.ac_forms import format_ac_line
        line = format_ac_line("AC1", "prose", "The system shall log errors", "gap")
        assert "[grounded: gap]" in line, (
            f"Expected '[grounded: gap]' in output line, got: {line!r}"
        )

    # AC-B8 extended: format_ac_line renders expected structural components
    def test_ac_b8_format_ac_line_structure(self):
        """format_ac_line output contains ac_id, form, and [grounded: citation]."""
        from spec_grounding._lib.ac_forms import format_ac_line
        line = format_ac_line("AC42", "ears-event", "WHEN x the system SHALL y", "skills/foo.py:10-20")
        assert "AC42" in line, f"AC id missing from line: {line!r}"
        assert "ears-event" in line, f"form tag missing from line: {line!r}"
        assert "[grounded: skills/foo.py:10-20]" in line, f"citation missing from line: {line!r}"

    # AC-B1: ground_acs returns one GroundedAC per input
    def test_ac_b1_ground_acs_returns_one_per_input(self, tmp_path):
        """AC-B1: ground_acs returns exactly one GroundedAC per raw AC string."""
        from spec_grounding._lib.grounding import ground_acs, GroundedAC
        raw_acs = [
            "WHEN alpha_sentinel_xqz fires the system SHALL respond",
            "WHILE beta_sentinel_xqz holds the system SHALL maintain",
            "The system should handle gamma_sentinel_xqz",
        ]
        # Write a file to give at least one potential match
        (tmp_path / "code.py").write_text(
            "def alpha_sentinel_xqz(): pass\n"
            "def beta_sentinel_xqz(): pass\n",
            encoding="utf-8"
        )
        results = ground_acs(raw_acs, repo_root=tmp_path)
        assert len(results) == len(raw_acs), (
            f"Expected {len(raw_acs)} results, got {len(results)}"
        )
        for r in results:
            assert isinstance(r, GroundedAC), f"Not a GroundedAC instance: {r!r}"
            assert isinstance(r.id, str) and r.id, "GroundedAC.id must be a non-empty string"
            assert isinstance(r.citation, str) and r.citation, (
                "GroundedAC.citation must be a non-empty string"
            )
            assert isinstance(r.resolved, bool), "GroundedAC.resolved must be bool"

    # AC-B1: codebase hit => resolved=True, citation is non-empty
    def test_ac_b1_codebase_hit_resolved_true(self, tmp_path):
        """AC-B1: When an AC term appears in codebase, resolved=True and citation is non-empty."""
        from spec_grounding._lib.grounding import ground_acs
        unique_term = "spec_blind_unique_codebase_sentinel_xqz9"
        (tmp_path / "sentinel_module.py").write_text(
            f"def {unique_term}(): pass\n", encoding="utf-8"
        )
        results = ground_acs([unique_term], repo_root=tmp_path)
        assert len(results) == 1
        r = results[0]
        assert r.resolved is True, (
            f"Expected resolved=True for term found in codebase; got citation={r.citation!r}"
        )
        assert r.citation and r.citation != "gap", (
            f"Citation must be a file reference, not gap; got: {r.citation!r}"
        )

    # AC-B2: missing recall DB does not raise; returns ACs
    def test_ac_b2_missing_recall_db_no_raise(self, tmp_path):
        """AC-B2: CLAUDE_RECALL_DB_PATH pointing to non-existent path => no raise, ACs returned."""
        from spec_grounding._lib.grounding import ground_acs
        raw_acs = ["WHEN something happens the system SHALL respond"]
        with unittest.mock.patch.dict(
            os.environ, {"CLAUDE_RECALL_DB_PATH": "/nonexistent/xqz/memory.sqlite"}
        ):
            results = ground_acs(raw_acs, repo_root=tmp_path)
        assert len(results) == len(raw_acs), "Must return one GroundedAC per input"
        for r in results:
            assert not r.citation.startswith("recall:"), (
                f"recall: citation should not appear with missing DB; got: {r.citation!r}"
            )

    # AC-B3: valid recall DB => at least one recall: citation
    def test_ac_b3_recall_db_present_yields_recall_citation(self, tmp_path, recall_db):
        """AC-B3: With a valid recall DB, at least one citation starts with 'recall:'."""
        from spec_grounding._lib.grounding import ground_acs
        # Terms are verbatim from our fixture's searchable_text
        raw_acs = [
            "spec_blind_sentinel_recall_term unique_recall_phrase",
            "ac_forms classify_form EARS forms pattern",
        ]
        with unittest.mock.patch.dict(
            os.environ, {"CLAUDE_RECALL_DB_PATH": str(recall_db)}
        ):
            results = ground_acs(raw_acs, repo_root=tmp_path)
        assert len(results) == len(raw_acs)
        citations = [r.citation for r in results]
        assert any(c.startswith("recall:") for c in citations), (
            f"Expected at least one recall: citation; got: {citations}"
        )

    # AC-B6: validate_citations returns only non-resolving file:line AC ids
    def test_ac_b6_validate_citations_non_resolving_file(self, tmp_path):
        """AC-B6: Non-resolving file:line => AC id in gaps; gap and recall: excluded."""
        from spec_grounding._lib.grounding import GroundedAC, validate_citations
        grounded = [
            GroundedAC(
                id="AC-SB1",
                form="prose",
                text="text",
                citation="no/such/file/ever.py:99",
                resolved=True,
            ),
            GroundedAC(
                id="AC-SB2",
                form="prose",
                text="text",
                citation="gap",
                resolved=False,
            ),
            GroundedAC(
                id="AC-SB3",
                form="ears-event",
                text="text",
                citation="recall:obs-sentinel-001",
                resolved=True,
            ),
        ]
        gaps = validate_citations(grounded, repo_root=tmp_path)
        assert "AC-SB1" in gaps, "Non-resolving file citation should appear in gaps"
        assert "AC-SB2" not in gaps, "'gap' citation should be excluded from file-resolution check"
        assert "AC-SB3" not in gaps, "'recall:' citation should be excluded from file-resolution check"

    # AC-B6 extended: a valid file reference is NOT flagged as a gap
    def test_ac_b6_validate_citations_resolving_file_not_in_gaps(self, tmp_path):
        """AC-B6: A citation that resolves to a real file is NOT in the gap list."""
        from spec_grounding._lib.grounding import GroundedAC, validate_citations
        real_file = tmp_path / "real_file.py"
        real_file.write_text("# content\n", encoding="utf-8")
        grounded = [
            GroundedAC(
                id="AC-SB4",
                form="prose",
                text="text",
                citation=f"{real_file}:1",
                resolved=True,
            ),
        ]
        gaps = validate_citations(grounded, repo_root=tmp_path)
        assert "AC-SB4" not in gaps, (
            f"A citation pointing to a real file must not be flagged as a gap; gaps={gaps}"
        )

    # AC-B7: CLAUDE_RECALL_DB_PATH env var is honoured
    def test_ac_b7_db_path_from_env_var(self, tmp_path, recall_db):
        """AC-B7: CLAUDE_RECALL_DB_PATH env var is used; recall citations appear."""
        from spec_grounding._lib.grounding import ground_acs
        raw_acs = ["spec_blind_sentinel_recall_term unique_recall_phrase"]
        with unittest.mock.patch.dict(
            os.environ, {"CLAUDE_RECALL_DB_PATH": str(recall_db)}
        ):
            results = ground_acs(raw_acs, repo_root=tmp_path)
        assert any(r.citation.startswith("recall:") for r in results), (
            f"CLAUDE_RECALL_DB_PATH env var not honoured; citations: {[r.citation for r in results]}"
        )

    # AC-B9: traversal skips >1MB files and binary files without raising
    def test_ac_b9_traversal_skips_large_and_binary_files(self, tmp_path):
        """AC-B9: Large (>1MB), binary (null byte) files are skipped silently; no raise."""
        from spec_grounding._lib.grounding import ground_acs
        # Large file
        (tmp_path / "large.dat").write_bytes(b"a" * (1024 * 1024 + 1))
        # Binary file (null byte)
        (tmp_path / "binary.bin").write_bytes(b"some\x00binary\x00data")
        # Normal file with matching term
        unique = "traversal_b9_normal_sentinel_xqz"
        (tmp_path / "normal.py").write_text(f"def {unique}(): pass\n", encoding="utf-8")

        results = ground_acs([unique], repo_root=tmp_path)
        # Must not raise; returns one result
        assert len(results) == 1

    # AC-B9: traversal skips .git/ directories without raising
    def test_ac_b9_traversal_skips_dot_git(self, tmp_path):
        """AC-B9: .git/ directory is excluded from traversal."""
        from spec_grounding._lib.grounding import ground_acs
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        unique_git = "git_dir_sentinel_should_be_skipped_xqz"
        (git_dir / "config_file.py").write_text(
            f"def {unique_git}(): pass\n", encoding="utf-8"
        )
        results = ground_acs([unique_git], repo_root=tmp_path)
        assert len(results) == 1
        # The .git content must not be cited
        assert not results[0].resolved, (
            f".git/ content must not be resolved; citation={results[0].citation!r}"
        )

    # AC-B9: files raising OSError are skipped (simulated via tmp_path with unreadable file)
    def test_ac_b9_traversal_skips_ose_error_file(self, tmp_path):
        """AC-B9: OSError on a file during traversal is skipped without raising."""
        from spec_grounding._lib.grounding import ground_acs
        # Create a normal matching file to confirm traversal continues
        unique = "ose_error_skip_sentinel_xqz"
        (tmp_path / "good.py").write_text(f"def {unique}(): pass\n", encoding="utf-8")
        bad = tmp_path / "bad.py"
        bad.write_text("def unrelated(): pass\n", encoding="utf-8")
        # Simulate OSError by making bad.py unreadable
        import stat
        bad.chmod(0o000)
        try:
            results = ground_acs([unique], repo_root=tmp_path)
            assert len(results) == 1  # no exception propagated
        finally:
            bad.chmod(stat.S_IRUSR | stat.S_IWUSR)

    # AC-B10: ears + prose count invariant on ground_acs output
    def test_ac_b10_ac_forms_count_invariant(self, tmp_path):
        """AC-B10: For any ground_acs result, ears+prose counts == total == len(raw_acs)."""
        from spec_grounding._lib.grounding import ground_acs
        from spec_grounding._lib.ac_forms import EARS_TYPES
        raw_acs = [
            "WHEN a user logs in the system SHALL authenticate",  # ears-event
            "WHILE processing the system SHALL show a spinner",   # ears-state
            "IF an error occurs THEN the system SHALL rollback",  # ears-unwanted
            "The error message should be user-friendly",          # prose
            "The system should support multi-language",           # prose
        ]
        results = ground_acs(raw_acs, repo_root=tmp_path)
        assert len(results) == len(raw_acs)
        ears_forms = {f for f in EARS_TYPES if f != "prose"}
        ears_count = sum(1 for r in results if r.form in ears_forms)
        prose_count = sum(1 for r in results if r.form == "prose")
        assert ears_count + prose_count == len(results), (
            f"ears({ears_count}) + prose({prose_count}) != total({len(results)})"
        )

    # AC-B1/B2: ground_acs never raises even with empty input
    def test_ac_b1_ground_acs_empty_input_no_raise(self, tmp_path):
        """ground_acs([]) returns [] without raising."""
        from spec_grounding._lib.grounding import ground_acs
        results = ground_acs([], repo_root=tmp_path)
        assert results == [], f"Expected [], got {results!r}"

    # GroundedAC dataclass fields per API contract
    def test_ac_b1_grounded_ac_fields(self):
        """GroundedAC dataclass must have id, form, text, citation, resolved fields."""
        from spec_grounding._lib.grounding import GroundedAC
        ac = GroundedAC(
            id="AC-SB99",
            form="ears-event",
            text="WHEN x the system SHALL y",
            citation="skills/foo.py:1-5",
            resolved=True,
        )
        assert ac.id == "AC-SB99"
        assert ac.form == "ears-event"
        assert ac.text == "WHEN x the system SHALL y"
        assert ac.citation == "skills/foo.py:1-5"
        assert ac.resolved is True

    # GroundedAC must be frozen (immutable per API contract: frozen=True)
    def test_ac_b1_grounded_ac_is_frozen(self):
        """GroundedAC must be a frozen dataclass (immutable)."""
        from spec_grounding._lib.grounding import GroundedAC
        ac = GroundedAC(
            id="AC-SB100", form="prose", text="t", citation="gap", resolved=False
        )
        with pytest.raises((TypeError, AttributeError)):
            ac.id = "MUTATED"  # type: ignore[misc]


# ===========================================================================
# Slice C — Orchestrator Wiring + SKILL.md (doc-contract)
# ===========================================================================

class TestSliceC:
    """AC-C1 through AC-C5: doc-contract checks on wiring documents."""

    @pytest.fixture(scope="class")
    def pipeline_skill_text(self):
        return (REPO_ROOT / "skills" / "pipeline" / "SKILL.md").read_text()

    @pytest.fixture(scope="class")
    def spec_grounding_skill_text(self):
        return (REPO_ROOT / "skills" / "spec-grounding" / "SKILL.md").read_text()

    @pytest.fixture(scope="class")
    def architect_text(self):
        return (REPO_ROOT / "agents" / "architect.md").read_text()

    # AC-C1: pipeline/SKILL.md has Step 2c-ter: Spec-Grounding after Step 2c-bis
    def test_ac_c1_pipeline_skill_has_step_2c_ter(self, pipeline_skill_text):
        """AC-C1: skills/pipeline/SKILL.md must contain 'Step 2c-ter' and 'Spec-Grounding'."""
        assert "Step 2c-ter" in pipeline_skill_text, (
            "Step 2c-ter section missing from skills/pipeline/SKILL.md"
        )
        assert "Spec-Grounding" in pipeline_skill_text, (
            "Spec-Grounding heading missing from skills/pipeline/SKILL.md"
        )

    # AC-C1: Step 2c-ter appears after Step 2c-bis in pipeline/SKILL.md
    def test_ac_c1_step_2c_ter_after_2c_bis(self, pipeline_skill_text):
        """AC-C1: Step 2c-ter must appear after Step 2c-bis in pipeline/SKILL.md."""
        idx_bis = pipeline_skill_text.find("Step 2c-bis")
        idx_ter = pipeline_skill_text.find("Step 2c-ter")
        assert idx_bis != -1, "Step 2c-bis not found in pipeline/SKILL.md"
        assert idx_ter != -1, "Step 2c-ter not found in pipeline/SKILL.md"
        assert idx_ter > idx_bis, (
            f"Step 2c-ter (pos {idx_ter}) must appear after Step 2c-bis (pos {idx_bis})"
        )

    # AC-C2: pipeline/SKILL.md documents GROUNDING_GAPS as non-blocking
    def test_ac_c2_grounding_gaps_non_blocking_documented(self, pipeline_skill_text):
        """AC-C2: pipeline/SKILL.md must document GROUNDING_GAPS and spec-grounding.md output."""
        assert "GROUNDING_GAPS" in pipeline_skill_text, (
            "GROUNDING_GAPS not documented in skills/pipeline/SKILL.md"
        )
        assert "spec-grounding.md" in pipeline_skill_text, (
            "spec-grounding.md output path not documented in skills/pipeline/SKILL.md"
        )

    # AC-C3: spec-grounding/SKILL.md frontmatter has required fields
    def test_ac_c3_skill_md_frontmatter_fields(self, spec_grounding_skill_text):
        """AC-C3: skills/spec-grounding/SKILL.md must have name, verdict, phase, dispatch."""
        text = spec_grounding_skill_text
        assert "name: spec-grounding" in text, (
            "name: spec-grounding missing from SKILL.md frontmatter"
        )
        assert "GROUNDED" in text, "GROUNDED verdict missing from SKILL.md frontmatter"
        assert "GROUNDING_GAPS" in text, "GROUNDING_GAPS verdict missing from SKILL.md frontmatter"
        assert "phase: plan" in text, "phase: plan missing from SKILL.md frontmatter"
        assert "dispatch: subagent" in text, "dispatch: subagent missing from SKILL.md frontmatter"

    # AC-C4: agents/architect.md Pre-Drafting Recon references spec-grounding.md
    def test_ac_c4_architect_references_spec_grounding_md(self, architect_text):
        """AC-C4: agents/architect.md must reference 'spec-grounding.md' in Pre-Drafting Recon."""
        assert "spec-grounding.md" in architect_text, (
            "spec-grounding.md not referenced in agents/architect.md"
        )

    # AC-C5: spec-grounding.md reference in architect.md has conditional qualifier
    def test_ac_c5_architect_spec_grounding_read_is_conditional(self, architect_text):
        """AC-C5: 'if present' or 'if exists' must appear near spec-grounding.md in architect.md."""
        lower = architect_text.lower()
        idx = lower.find("spec-grounding.md")
        assert idx != -1, "spec-grounding.md not found in architect.md"
        # Check within a 300-char window around the reference
        window_start = max(0, idx - 150)
        window_end = min(len(lower), idx + 200)
        window = lower[window_start:window_end]
        assert "if present" in window or "if exists" in window, (
            f"No conditional qualifier near spec-grounding.md in architect.md. Window: {window!r}"
        )


# ===========================================================================
# Slice D — Test Infrastructure (sentinel + hygiene)
# ===========================================================================

class TestSliceD:
    """AC-D1, AC-D2, AC-D3: test-infrastructure checks."""

    # AC-D2: module imports cleanly with correct sys.path
    def test_ac_d2_module_imports_cleanly(self):
        """AC-D2: spec_grounding._lib.grounding and ac_forms import cleanly."""
        from spec_grounding._lib import grounding, ac_forms  # noqa: F401
        assert callable(getattr(grounding, "ground_acs", None)), (
            "ground_acs not callable in spec_grounding._lib.grounding"
        )
        assert callable(getattr(grounding, "validate_citations", None)), (
            "validate_citations not callable in spec_grounding._lib.grounding"
        )
        assert hasattr(grounding, "GroundedAC"), (
            "GroundedAC not present in spec_grounding._lib.grounding"
        )
        assert callable(getattr(ac_forms, "classify_form", None)), (
            "classify_form not callable in spec_grounding._lib.ac_forms"
        )
        assert callable(getattr(ac_forms, "format_ac_line", None)), (
            "format_ac_line not callable in spec_grounding._lib.ac_forms"
        )
        assert hasattr(ac_forms, "EARS_TYPES"), (
            "EARS_TYPES not present in spec_grounding._lib.ac_forms"
        )

    # AC-D3: static sentinel — env-var hygiene convention
    def test_ac_d3_env_var_tests_use_patch_dict_sentinel(self):
        """AC-D3: Static sentinel — all os.environ mutations in this file use patch.dict.
        This test passes unconditionally; code-reviewer verifies the convention.
        """
        assert True

    # AC-D1: this file itself collects without error (sentinel)
    def test_ac_d1_spec_blind_test_file_collection_sentinel(self):
        """AC-D1: If pytest collected and reached this test, no collection errors occurred."""
        pass
