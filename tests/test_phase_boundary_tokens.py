"""AC1–AC3 tests for phase_boundary_tokens.py — WRITTEN BEFORE IMPLEMENTATION (RED).

AC1: count_tokens(s) = ceil(len(s.encode('utf-8')) / 3.5)
AC2: compress_handoff keeps goal+ACs verbatim; last N findings full-resolution
AC3: main() emits exactly one JSONL record with the agreed schema
"""
import json
import math
import os
import sys
import tempfile
from pathlib import Path

# Allow import before the module exists (test will ImportError → RED)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks" / "_lib"))

import pytest


# ---------------------------------------------------------------------------
# AC1 — Token counting
# ---------------------------------------------------------------------------

class TestCountTokens:
    def test_token_count_is_ceil_bytes_over_3_5(self):
        from phase_boundary_tokens import count_tokens
        # 7 utf-8 bytes → ceil(7/3.5) = 2
        assert count_tokens("a" * 7) == 2

    def test_empty_string_returns_zero(self):
        from phase_boundary_tokens import count_tokens
        assert count_tokens("") == 0

    def test_single_ascii_char(self):
        from phase_boundary_tokens import count_tokens
        # 1 byte → ceil(1/3.5) = 1
        assert count_tokens("x") == 1

    def test_multibyte_utf8(self):
        from phase_boundary_tokens import count_tokens
        # "é" is 2 bytes in utf-8 → ceil(2/3.5) = 1
        assert count_tokens("é") == 1

    def test_result_is_ceiling_not_floor(self):
        from phase_boundary_tokens import count_tokens
        # 8 bytes → ceil(8/3.5) = ceil(2.285…) = 3
        assert count_tokens("a" * 8) == 3

    def test_large_string(self):
        from phase_boundary_tokens import count_tokens
        s = "a" * 350  # 350 bytes → ceil(350/3.5) = 100
        assert count_tokens(s) == 100


# ---------------------------------------------------------------------------
# AC2 — compress_handoff: goal+ACs verbatim; last N findings full-resolution
# ---------------------------------------------------------------------------

HANDOFF_DOC = """\
## Goal

Ship the phase-boundary compression step, advisory-first.

## Acceptance Criteria

- AC1: Token measurement is deterministic.
- AC2: Goal + ACs retained verbatim.
- AC3: One JSONL record per boundary.

## Key Findings

- Finding 1: something minor.
- Finding 2: something else minor.
- Finding 3: third finding.
- Finding 4: fourth finding here.
- Finding 5: fifth finding.
- Finding 6: sixth finding.
- Finding 7: seventh finding.
- Finding 8: eighth and final finding.
"""


class TestCompressHandoff:
    def test_goal_block_retained_verbatim(self):
        from phase_boundary_tokens import compress_handoff
        result = compress_handoff(HANDOFF_DOC, n=5)
        assert "## Goal\n\nShip the phase-boundary compression step, advisory-first." in result

    def test_ac_lines_retained_verbatim(self):
        from phase_boundary_tokens import compress_handoff
        result = compress_handoff(HANDOFF_DOC, n=5)
        assert "- AC1: Token measurement is deterministic." in result
        assert "- AC2: Goal + ACs retained verbatim." in result
        assert "- AC3: One JSONL record per boundary." in result

    def test_last_n_findings_preserved(self):
        from phase_boundary_tokens import compress_handoff
        # 8 findings, n=5 → findings 4..8 preserved verbatim
        result = compress_handoff(HANDOFF_DOC, n=5)
        assert "Finding 4: fourth finding here." in result
        assert "Finding 5: fifth finding." in result
        assert "Finding 6: sixth finding." in result
        assert "Finding 7: seventh finding." in result
        assert "Finding 8: eighth and final finding." in result

    def test_early_findings_summarized(self):
        from phase_boundary_tokens import compress_handoff
        # findings 1..3 should be replaced with a summary line, not appear verbatim
        result = compress_handoff(HANDOFF_DOC, n=5)
        assert "Finding 1: something minor." not in result
        assert "Finding 2: something else minor." not in result
        assert "Finding 3: third finding." not in result

    def test_summary_line_present_when_findings_elided(self):
        from phase_boundary_tokens import compress_handoff
        result = compress_handoff(HANDOFF_DOC, n=5)
        # Should contain a summary placeholder like "(summarized 3 earlier findings)"
        assert "summarized" in result.lower()
        assert "3" in result

    def test_when_findings_le_n_no_elision(self):
        from phase_boundary_tokens import compress_handoff
        # Only 3 findings, n=5 → all retained
        short_doc = """\
## Goal

Short goal.

## Key Findings

- Finding A.
- Finding B.
- Finding C.
"""
        result = compress_handoff(short_doc, n=5)
        assert "Finding A." in result
        assert "Finding B." in result
        assert "Finding C." in result
        assert "summarized" not in result.lower()

    def test_tokens_after_lte_tokens_before(self):
        from phase_boundary_tokens import compress_handoff, count_tokens
        result = compress_handoff(HANDOFF_DOC, n=5)
        assert count_tokens(result) <= count_tokens(HANDOFF_DOC)


# ---------------------------------------------------------------------------
# AC3 — One JSONL record per boundary with the agreed schema
# ---------------------------------------------------------------------------

def _write_handoff(directory, content=HANDOFF_DOC):
    """Write content to a temp handoff file and return its path string."""
    p = Path(directory) / "handoff.md"
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestEmitOneRecord:
    def test_emit_one_record(self):
        from phase_boundary_tokens import main
        with tempfile.TemporaryDirectory() as tmpdir:
            handoff_path = _write_handoff(tmpdir)
            argv = [
                "phase_boundary_tokens.py",
                tmpdir,               # metrics_dir
                "2026-06-05T12:00:00Z",  # ts
                "build",              # phase_from
                "security-review",    # phase_to
                handoff_path,         # path to handoff file (not content)
            ]
            main(argv)
            out = os.path.join(tmpdir, "phase-boundary.jsonl")
            assert os.path.exists(out), "phase-boundary.jsonl not created"
            lines = Path(out).read_text().strip().splitlines()
            assert len(lines) == 1, f"Expected 1 line, got {len(lines)}"
            rec = json.loads(lines[0])
            assert rec["ts"] == "2026-06-05T12:00:00Z"
            assert rec["phase_from"] == "build"
            assert rec["phase_to"] == "security-review"
            assert isinstance(rec["tokens_before"], int)
            assert isinstance(rec["tokens_after"], int)
            assert rec["tokens_after"] <= rec["tokens_before"]
            assert rec["goal_retained"] is True
            assert isinstance(rec["last_n_full"], int)
            assert rec["mode"] == "advisory"
            # omit-not-null: record key set must be exactly these 8 fields, no more
            assert set(rec.keys()) == {
                "ts", "phase_from", "phase_to",
                "tokens_before", "tokens_after",
                "goal_retained", "last_n_full", "mode",
            }

    def test_missing_handoff_file_returns_0_without_crash(self):
        """Non-existent handoff path must return 0 (advisory: never crash pipeline)."""
        from phase_boundary_tokens import main
        with tempfile.TemporaryDirectory() as tmpdir:
            argv = [
                "phase_boundary_tokens.py",
                tmpdir,
                "2026-06-05T12:00:00Z",
                "build",
                "security-review",
                "/nonexistent/path/handoff.md",
            ]
            result = main(argv)
            assert result == 0

    def test_wrong_arg_count_does_not_crash(self):
        from phase_boundary_tokens import main
        # Should return 0 without raising
        result = main(["phase_boundary_tokens.py"])
        assert result == 0

    def test_two_calls_append_two_lines(self):
        from phase_boundary_tokens import main
        with tempfile.TemporaryDirectory() as tmpdir:
            handoff_path = _write_handoff(tmpdir)
            base_argv = [
                "phase_boundary_tokens.py",
                tmpdir,
                "2026-06-05T12:00:00Z",
                "build",
                "security-review",
                handoff_path,
            ]
            main(base_argv)
            main(base_argv)
            out = os.path.join(tmpdir, "phase-boundary.jsonl")
            lines = Path(out).read_text().strip().splitlines()
            assert len(lines) == 2


# ---------------------------------------------------------------------------
# Fix 1 (CRITICAL) — AC-prefix false-positive: non-criterion items must be kept
# ---------------------------------------------------------------------------

class TestExtractFindingsAcPrefix:
    def test_acme_finding_is_kept(self):
        """'- ACME deploy failed' is NOT an AC criterion — must be kept as a finding."""
        from phase_boundary_tokens import compress_handoff
        doc = """\
## Goal

Test goal.

## Key Findings

- ACME deploy failed in staging.
- AC reconciliation broke the pipeline.
- Finding C is fine.
- Finding D is fine.
- Finding E is fine.
- Finding F is fine.
"""
        result = compress_handoff(doc, n=5)
        # With 6 findings, n=5: first finding elided, last 5 kept.
        # "ACME deploy failed" is finding 1 → summarized; all others kept.
        # The key assertion: the function must NOT silently drop ACME/ACr lines.
        # Findings 2-6 should appear verbatim.
        assert "AC reconciliation broke the pipeline." in result
        assert "Finding C is fine." in result
        assert "Finding D is fine." in result
        assert "Finding E is fine." in result
        assert "Finding F is fine." in result

    def test_ac_digit_criterion_excluded_from_findings(self):
        """'- AC1: ...' IS a criterion line and must NOT appear as a finding."""
        from phase_boundary_tokens import _extract_findings
        lines = [
            "## Key Findings",
            "",
            "- AC1: This is an acceptance criterion.",
            "- AC2: Another criterion.",
            "- Real finding here.",
        ]
        findings = _extract_findings(lines)
        texts = "\n".join(findings)
        assert "AC1:" not in texts
        assert "AC2:" not in texts
        assert "Real finding here." in texts

    def test_non_digit_ac_prefix_kept_as_finding(self):
        """'- ACme thing' and '- AC reconciliation' are findings, not criteria."""
        from phase_boundary_tokens import _extract_findings
        lines = [
            "## Key Findings",
            "",
            "- ACME thing broke.",
            "- AC reconciliation failed.",
            "- Normal finding.",
        ]
        findings = _extract_findings(lines)
        texts = "\n".join(findings)
        assert "ACME thing broke." in texts
        assert "AC reconciliation failed." in texts
        assert "Normal finding." in texts


# ---------------------------------------------------------------------------
# Fix 2 (CRITICAL) — Verbatim round-trip: blank lines between findings preserved
# ---------------------------------------------------------------------------

HANDOFF_WITH_BLANK_LINES = """\
## Goal

Goal text here.

## Key Findings

- Finding 1: first.

- Finding 2: second.

- Finding 3: third.

- Finding 4: fourth.

- Finding 5: fifth.

- Finding 6: sixth.
"""


class TestVerbatimRoundTrip:
    def test_kept_findings_are_byte_identical(self):
        """Last-N findings must be byte-identical (including surrounding blank lines)."""
        from phase_boundary_tokens import compress_handoff
        result = compress_handoff(HANDOFF_WITH_BLANK_LINES, n=5)
        # findings 2-6 are the kept last-5; verify each appears verbatim
        assert "- Finding 2: second." in result
        assert "- Finding 3: third." in result
        assert "- Finding 4: fourth." in result
        assert "- Finding 5: fifth." in result
        assert "- Finding 6: sixth." in result

    def test_blank_lines_between_kept_findings_preserved(self):
        """Blank lines separating kept findings must survive compression."""
        from phase_boundary_tokens import compress_handoff
        result = compress_handoff(HANDOFF_WITH_BLANK_LINES, n=5)
        # Each pair of adjacent kept findings should still be separated by a blank line
        assert "- Finding 2: second.\n\n- Finding 3: third." in result


# ---------------------------------------------------------------------------
# Fix 3 (HIGH) — goal_retained must be computed, not hardcoded True
# ---------------------------------------------------------------------------

class TestGoalRetainedComputed:
    def test_goal_retained_true_when_goal_present(self):
        """When the doc has a goal block that survives compression, goal_retained=True."""
        from phase_boundary_tokens import main
        with tempfile.TemporaryDirectory() as tmpdir:
            handoff_path = _write_handoff(tmpdir)
            argv = [
                "phase_boundary_tokens.py",
                tmpdir,
                "2026-06-05T12:00:00Z",
                "build",
                "security-review",
                handoff_path,
            ]
            main(argv)
            rec = json.loads(Path(tmpdir, "phase-boundary.jsonl").read_text().strip())
            assert rec["goal_retained"] is True

    def test_goal_retained_false_when_no_goal_block(self):
        """When the doc has NO ## Goal section, goal_retained=False."""
        from phase_boundary_tokens import main
        no_goal_doc = """\
## Key Findings

- Finding 1.
- Finding 2.
- Finding 3.
- Finding 4.
- Finding 5.
- Finding 6.
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            handoff_path = _write_handoff(tmpdir, no_goal_doc)
            argv = [
                "phase_boundary_tokens.py",
                tmpdir,
                "2026-06-05T12:00:00Z",
                "build",
                "security-review",
                handoff_path,
            ]
            main(argv)
            rec = json.loads(Path(tmpdir, "phase-boundary.jsonl").read_text().strip())
            assert rec["goal_retained"] is False

    def test_build_record_accepts_goal_retained_param(self):
        """build_record must accept and store a computed goal_retained value."""
        from phase_boundary_tokens import build_record
        rec_true = build_record("ts", "a", "b", 100, 50, 5, goal_retained=True)
        rec_false = build_record("ts", "a", "b", 100, 50, 5, goal_retained=False)
        assert rec_true["goal_retained"] is True
        assert rec_false["goal_retained"] is False


# ---------------------------------------------------------------------------
# Fix 6 (cheap) — wrong argc logs to stderr, still returns 0
# ---------------------------------------------------------------------------

class TestWrongArgcLogsStderr:
    def test_wrong_argc_emits_stderr_warning(self, capsys):
        from phase_boundary_tokens import main
        main(["phase_boundary_tokens.py"])  # only 1 arg, expects 6
        captured = capsys.readouterr()
        assert "usage" in captured.err.lower() or "expected" in captured.err.lower() or "argc" in captured.err.lower() or captured.err != ""


# ---------------------------------------------------------------------------
# Final-Gate condition 1 — _goal_present_in: line-start match only
# ---------------------------------------------------------------------------

class TestGoalPresentLineStart:
    def test_inline_goal_header_not_treated_as_present(self):
        """'## Goal' embedded inside a finding body must not count as a goal header."""
        from phase_boundary_tokens import _goal_present_in
        # "## Goal" appears only mid-sentence, not at line-start as a header
        doc_no_header = (
            "## Key Findings\n\n"
            "- See ## Goal below for context.\n"
            "- Another finding.\n"
        )
        assert _goal_present_in(doc_no_header) is False

    def test_real_goal_header_detected(self):
        """A proper ## Goal section at line-start → True."""
        from phase_boundary_tokens import _goal_present_in
        assert _goal_present_in("## Goal\n\nShip it.\n") is True

    def test_goal_not_present_in_empty_doc(self):
        from phase_boundary_tokens import _goal_present_in
        assert _goal_present_in("") is False


# ---------------------------------------------------------------------------
# Final-Gate condition 3 (QA gap 4) — exactly-n-findings boundary
# ---------------------------------------------------------------------------

_EXACTLY_N_DOC = """\
## Goal

Goal text.

## Key Findings

- Finding 1.
- Finding 2.
- Finding 3.
- Finding 4.
- Finding 5.
"""


class TestExactlyNFindings:
    def test_exactly_n_findings_no_compression(self):
        """With exactly n=5 findings, compress_handoff must return the doc unchanged."""
        from phase_boundary_tokens import compress_handoff
        result = compress_handoff(_EXACTLY_N_DOC, n=5)
        assert result == _EXACTLY_N_DOC

    def test_exactly_n_findings_no_summary_line(self):
        """No 'summarized' marker when count == n."""
        from phase_boundary_tokens import compress_handoff
        result = compress_handoff(_EXACTLY_N_DOC, n=5)
        assert "summarized" not in result.lower()


# ---------------------------------------------------------------------------
# Final-Gate condition 4 (QA gap 2) — SKILL.md Step 3 renumber intact
# ---------------------------------------------------------------------------

class TestSkillMdRenumber:
    def test_no_duplicate_numeric_substep_in_step3_block(self):
        """Step 3 sub-steps must not have any duplicate numeric label (e.g. two '5.')."""
        import re
        skill_path = (
            Path(__file__).resolve().parent.parent / "skills" / "pipeline" / "SKILL.md"
        )
        text = skill_path.read_text(encoding="utf-8")
        # Locate the "For each phase:" paragraph inside Step 3 — the immediate
        # sub-step list that was renumbered.  Stop at the first sub-heading (####).
        for_each_match = re.search(
            r"For each phase:\n(.*?)(?=^####|\Z)", text, re.DOTALL | re.MULTILINE
        )
        assert for_each_match, "'For each phase:' block not found in SKILL.md Step 3"
        block = for_each_match.group(1)
        # Only column-0 top-level list items of the form "N. " (not 2b., not indented)
        numbers = re.findall(r"^(\d+)\. ", block, re.MULTILINE)
        assert len(numbers) == len(set(numbers)), (
            f"Duplicate sub-step numbers in Step 3 'For each phase:' block: {numbers}"
        )
