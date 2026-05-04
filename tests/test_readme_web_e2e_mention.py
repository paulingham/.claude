"""C3 — README.md or CLAUDE.md mentions web E2E within 80-line window (AC23, M2)."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = (REPO_ROOT / "README.md", REPO_ROOT / "CLAUDE.md")
SUBSTRINGS = ("web E2E", "Playwright", "verification")


def _line_numbers(text, substring):
    return [i for i, line in enumerate(text.splitlines(), start=1)
            if substring in line]


def _max_min_distance(text, substrings):
    """Return None if any substring missing; else max(line) - min(line) across all."""
    all_lines = []
    for s in substrings:
        nums = _line_numbers(text, s)
        if not nums:
            return None
        all_lines.append(nums)
    # Pick a single co-occurrence: smallest window.
    # M2 requires max-min ≤ 80 over the chosen line picks.
    # Use simplest interpretation: each substring's smallest line number
    # against each substring's largest line number. We test the existence
    # of at least one tuple of (one occurrence per substring) with span ≤ 80.
    return _smallest_span_across(all_lines)


def _smallest_span_across(line_lists):
    """Smallest possible max-min window covering one occurrence of each substring."""
    smallest = None
    # Brute force over combinations — substrings are few (3) and occurrences
    # will be a handful.
    def recurse(idx, picks):
        nonlocal smallest
        if idx == len(line_lists):
            span = max(picks) - min(picks)
            if smallest is None or span < smallest:
                smallest = span
            return
        for n in line_lists[idx]:
            recurse(idx + 1, picks + [n])
    recurse(0, [])
    return smallest


def test_readme_or_claude_md_mentions_web_e2e_within_80_line_window():
    """AC23 (M2): All 3 substrings in same file with max-min ≤ 80 lines."""
    failures = []
    for path in CANDIDATES:
        if not path.exists():
            failures.append(f"{path.name}: missing")
            continue
        text = path.read_text()
        span = _max_min_distance(text, SUBSTRINGS)
        if span is None:
            missing = [s for s in SUBSTRINGS
                       if not _line_numbers(text, s)]
            failures.append(f"{path.name}: missing substrings {missing}")
            continue
        if span <= 80:
            return  # success on this file
        failures.append(f"{path.name}: span={span} > 80")
    assert False, (
        "Neither README.md nor CLAUDE.md mentions all 3 substrings "
        "(`web E2E`, `Playwright`, `verification`) within an 80-line "
        f"window. Details: {failures}")
