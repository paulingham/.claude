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

class TestEmitOneRecord:
    def test_emit_one_record(self):
        from phase_boundary_tokens import main
        with tempfile.TemporaryDirectory() as tmpdir:
            argv = [
                "phase_boundary_tokens.py",
                tmpdir,               # metrics_dir
                "2026-06-05T12:00:00Z",  # ts
                "build",              # phase_from
                "security-review",    # phase_to
                HANDOFF_DOC,          # doc (raw phase notes = tokens_before source)
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

    def test_wrong_arg_count_does_not_crash(self):
        from phase_boundary_tokens import main
        # Should return 0 without raising
        result = main(["phase_boundary_tokens.py"])
        assert result == 0

    def test_two_calls_append_two_lines(self):
        from phase_boundary_tokens import main
        with tempfile.TemporaryDirectory() as tmpdir:
            base_argv = [
                "phase_boundary_tokens.py",
                tmpdir,
                "2026-06-05T12:00:00Z",
                "build",
                "security-review",
                HANDOFF_DOC,
            ]
            main(base_argv)
            main(base_argv)
            out = os.path.join(tmpdir, "phase-boundary.jsonl")
            lines = Path(out).read_text().strip().splitlines()
            assert len(lines) == 2
