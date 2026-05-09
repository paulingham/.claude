"""Slice A — Adversarial generation extends to refactor slices.

Asserts `skills/build-implementation/SKILL.md` Step 2b documents a
refactor branch that is env-gated by `CLAUDE_ADVERSARIAL_TESTS_REFACTOR=1`
with `cap=3`, preserves the bug-fix-skip iron law verbatim, documents
the master kill-switch precedence, renders a 5-row pipe-delimited
markdown truth table, and the Step 4 self-review checklist references
the refactor branch.

Each test maps 1:1 to a Slice A acceptance criterion (A1..A5 + Tier 0).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"


def _section_body(body, heading_prefix):
    """Extract the body of a `### Step ...` section.

    Mirrors the `_step_1d_body` helper in
    `tests/test_build_step_1d_env_hatch.py`. Returns the section text
    from the heading line up to (but not including) the next `### Step `
    heading or end-of-file.
    """
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(heading_prefix):
            start = i
            break
    assert start is not None, f"{heading_prefix!r} heading not found"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("### Step "):
            end = j
            break
    return "\n".join(lines[start:end])


def _step_2b_body():
    return _section_body(SKILL_PATH.read_text(), "### Step 2b")


def _step_4_body():
    return _section_body(SKILL_PATH.read_text(), "### Step 4")


def _truth_table_rows(step_2b):
    """Return the data rows of the precedence truth table.

    Locates a markdown table whose first column heading contains
    `CLAUDE_ADVERSARIAL_TESTS` and returns the data-row lines (skipping
    the header row and the `---` separator). Each row is the raw
    pipe-delimited line, leading/trailing pipes stripped.
    """
    lines = step_2b.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (stripped.startswith("|")
                and "CLAUDE_ADVERSARIAL_TESTS" in stripped
                and stripped.count("|") >= 4):
            header_idx = i
            break
    assert header_idx is not None, (
        "Step 2b body must contain a markdown table whose first column "
        "heading references CLAUDE_ADVERSARIAL_TESTS")
    # Separator row directly follows the header.
    sep_idx = header_idx + 1
    assert sep_idx < len(lines) and re.match(
        r"^\s*\|\s*-{3,}", lines[sep_idx]), (
        "markdown separator row not found directly under header")
    rows = []
    for j in range(sep_idx + 1, len(lines)):
        stripped = lines[j].strip()
        if not stripped.startswith("|"):
            break
        rows.append(stripped.strip("|"))
    return rows


def test_step_2b_documents_truth_table():
    """Tier 0 — pipe-delimited markdown table with 5 rows encoding the
    env-var gating precedence truth table. Each row must contain its
    required token set (per plan § Tier 0 Slice A).
    """
    step_2b = _step_2b_body()
    rows = _truth_table_rows(step_2b)
    assert len(rows) == 5, (
        f"truth table must have exactly 5 data rows, got {len(rows)}")
    required_per_row = [
        # Row 1: master kill-switch
        ("CLAUDE_ADVERSARIAL_TESTS", "0", "SKIPPED", "master"),
        # Row 2: greenfield default-on
        ("unset", "greenfield", "RUNS", "cap=5"),
        # Row 3: refactor opt-in
        ("CLAUDE_ADVERSARIAL_TESTS_REFACTOR", "1", "refactor", "RUNS",
         "cap=3"),
        # Row 4: refactor soak default-off
        ("refactor", "SKIPPED", "soak"),
        # Row 5: bug-fix iron law
        ("bug-fix", "SKIPPED", "iron law"),
    ]
    for idx, tokens in enumerate(required_per_row):
        row_text = rows[idx]
        for tok in tokens:
            assert tok in row_text, (
                f"row {idx + 1} missing required token {tok!r}; "
                f"row text: {row_text!r}")


def test_step_2b_heading_no_longer_excludes_refactor():
    """A1 — Step 2b heading documents refactor branch."""
    step_2b = _step_2b_body()
    heading_line = step_2b.splitlines()[0]
    assert "(greenfield ACs only)" not in heading_line, (
        "Step 2b heading must not retain the `(greenfield ACs only)` "
        "exclusivity claim now that the refactor branch is documented")
    lowered = heading_line.lower()
    assert ("refactor" in lowered) or ("env-gated" in lowered), (
        "Step 2b heading must mention `refactor` or `env-gated` to "
        "document the new branch")


def test_step_2b_documents_refactor_cap_3_with_env_var():
    """A2 — Refactor branch documented with cap=3 in a single contiguous
    paragraph that contains `CLAUDE_ADVERSARIAL_TESTS_REFACTOR=1`.

    The regex anchoring (`CLAUDE_ADVERSARIAL_TESTS_REFACTOR=1` token)
    discriminates from the existing PBT-overlap paragraph at line 109,
    which contains `cap reduces from 5 to 3` but not the refactor flag.
    """
    step_2b = _step_2b_body()
    pattern = re.compile(
        r"refactor[\s\S]{0,400}?cap=3[\s\S]{0,400}?"
        r"CLAUDE_ADVERSARIAL_TESTS_REFACTOR=1")
    assert pattern.search(step_2b), (
        "Step 2b body must contain a paragraph where `refactor`, "
        "`cap=3`, and `CLAUDE_ADVERSARIAL_TESTS_REFACTOR=1` co-occur "
        "within a 400-char window")


def test_step_2b_bug_fix_skip_paragraph_preserved():
    """A3 — Bug-fix-skip paragraph preserved verbatim.

    Regression invariant. The bug-fix iron law lives in this paragraph;
    it must not drift during Slice A. If a future slice intentionally
    rewrites the bug-fix paragraph, audit Step 2b's gating logic FIRST
    (does the bug-fix branch still skip?), then update both the
    production paragraph and this assertion in lockstep — never one
    without the other. Mismatch = ATDD audit gap.
    """
    body = SKILL_PATH.read_text()
    expected = (
        "**Bug-fix slices SKIP this step entirely.** For bug-fix work, "
        "the repro test IS the contract — adversarial probing belongs "
        "in greenfield AC implementation, not regression closure. See "
        "`skills/bug-fix/SKILL.md` for the per-behaviour cycle that "
        "applies instead.")
    assert expected in body, (
        "bug-fix-skip paragraph must be present byte-identical")


def test_step_2b_documents_master_kill_switch_precedence():
    """A4 — Master kill-switch precedence documented in a single
    sentence that names both env vars and one of the precedence verbs.
    """
    step_2b = _step_2b_body()
    pattern = re.compile(
        r"CLAUDE_ADVERSARIAL_TESTS=0[^.]*"
        r"\b(overrides|takes precedence over|wins)\b"
        r"[^.]*\bCLAUDE_ADVERSARIAL_TESTS_REFACTOR\b")
    assert pattern.search(step_2b), (
        "Step 2b body must contain a single sentence stating that "
        "`CLAUDE_ADVERSARIAL_TESTS=0` overrides / takes precedence "
        "over / wins against `CLAUDE_ADVERSARIAL_TESTS_REFACTOR`")


def test_step_4_checklist_documents_refactor_branch():
    """A5 — Step 4 self-review checklist references the refactor branch
    (CLAUDE_ADVERSARIAL_TESTS_REFACTOR + cap, case-insensitive).
    """
    step_4 = _step_4_body()
    # Find the Step 2b checklist line — the line referencing Step 2b.
    matching = [
        line for line in step_4.splitlines()
        if line.lstrip().startswith("- [ ]") and "Step 2b" in line]
    assert matching, (
        "Step 4 checklist must contain a Step 2b line")
    line = matching[0]
    lowered = line.lower()
    assert "claude_adversarial_tests_refactor" in lowered, (
        f"Step 2b checklist line must mention "
        f"CLAUDE_ADVERSARIAL_TESTS_REFACTOR; got: {line!r}")
    assert "cap" in lowered, (
        f"Step 2b checklist line must mention `cap`; got: {line!r}")
