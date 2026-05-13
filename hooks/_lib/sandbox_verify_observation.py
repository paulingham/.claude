"""Pure read helpers for `phases.sandbox_verify` observation blocks.

Three functions for downstream consumers (`/learn`, `/forensics`,
`/eval-model-effectiveness`, `/cost-report`):

- `read_sandbox_phase(observation)` -> Optional[dict]
- `is_present(observation)` -> bool
- `diverging_tests_from_build_md(build_md_text)` -> list[str]

Tier-0 contracts (per Story 4 plan):
- C1: `read_sandbox_phase` returns Optional[dict]; never `{}`; pure.
- C2: `is_present` true iff dict with `verdict` key whose value is in the
       3-enum set {SANDBOX_VERIFIED, SANDBOX_FAILED, SANDBOX_SKIPPED}.
- C3: `diverging_tests_from_build_md` returns list[str]; idempotent.

Absence-tolerance invariant: legacy records missing the block return
None from `read_sandbox_phase`. Consumers MUST filter (via
`is_present`), never coerce absence to a synthetic verdict. Mirrors the
`phases.patch_critic` / `phases.pdr_rtv` precedent.

The build.md parser is deliberately tolerant: case-insensitive column
match on the `Diff` column, whitespace-stripped cell values, so a
column-order swap or extra surrounding whitespace does not break it.
"""
from __future__ import annotations

from typing import Optional

_VERDICT_ENUM = frozenset({
    "SANDBOX_VERIFIED",
    "SANDBOX_FAILED",
    "SANDBOX_SKIPPED",
})

_SANDBOX_HEADER = "## Sandbox Verify"


def read_sandbox_phase(observation: dict) -> Optional[dict]:
    """Return `observation['phases']['sandbox_verify']` or None.

    Returns None when:
    - the block is absent (legacy record), OR
    - the value is explicitly None.

    Returns the dict as-is when present. Pure — no I/O, no mutation of
    the input observation.
    """
    phases = observation.get("phases") or {}
    block = phases.get("sandbox_verify")
    if block is None:
        return None
    return block


def is_present(observation: dict) -> bool:
    """True iff the block is a dict with `verdict` in the 3-enum set.

    Used as a filter predicate by downstream consumers. Records that
    fail the predicate are skipped entirely — never coerced.
    """
    block = read_sandbox_phase(observation)
    if not isinstance(block, dict):
        return False
    verdict = block.get("verdict")
    return verdict in _VERDICT_ENUM


def diverging_tests_from_build_md(build_md_text: str) -> list[str]:
    """Parse the `## Sandbox Verify` table for rows where Diff == diverge.

    Returns the test names (column 1) in document order. Empty list
    when the section is absent or no row has Diff == diverge.

    Idempotent (C3): parsing the same input twice produces the same
    list — no hidden state.
    """
    if not build_md_text:
        return []
    header_idx = build_md_text.find(_SANDBOX_HEADER)
    if header_idx == -1:
        return []
    # Bound the section at the next `## ` heading (or EOF).
    body = build_md_text[header_idx + len(_SANDBOX_HEADER):]
    next_header = body.find("\n## ")
    if next_header != -1:
        body = body[:next_header]
    return _parse_diverge_rows(body)


def _parse_diverge_rows(section_body: str) -> list[str]:
    """Walk markdown table rows in `section_body`, return diverging tests.

    Skips the header + separator rows. A row is "diverging" when its
    Diff column (last cell) is `diverge` (case-insensitive). Test name
    is the first non-empty cell after the leading `|`.
    """
    diff_idx = _find_diff_column_index(section_body)
    if diff_idx is None:
        return []
    diverging: list[str] = []
    for line in section_body.splitlines():
        if not line.startswith("|"):
            continue
        if _is_separator_row(line):
            continue
        cells = _split_row(line)
        if len(cells) <= diff_idx:
            continue
        if _is_header_row(cells):
            continue
        if cells[diff_idx].strip().lower() == "diverge":
            diverging.append(cells[0].strip())
    return diverging


def _find_diff_column_index(section_body: str) -> Optional[int]:
    """Find the (0-based) column index whose header is `Diff`."""
    for line in section_body.splitlines():
        if not line.startswith("|"):
            continue
        if _is_separator_row(line):
            continue
        cells = _split_row(line)
        for idx, cell in enumerate(cells):
            if cell.strip().lower() == "diff":
                return idx
        # First non-separator row is the header — stop scanning.
        return None
    return None


def _split_row(line: str) -> list[str]:
    """Split a markdown table row by `|`, dropping the empty leading
    and trailing cells produced by the bracketing `|` characters."""
    parts = line.split("|")
    # Drop empty leading/trailing cells.
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _is_separator_row(line: str) -> bool:
    """Markdown separator rows look like `|---|---|---|`."""
    stripped = line.strip()
    body = stripped.strip("|").replace("-", "").replace(":", "").replace(
        " ", "").replace("|", "")
    return body == "" and "-" in stripped


def _is_header_row(cells: list[str]) -> bool:
    """Header row contains `Test` (the first column) — skip on parse."""
    return bool(cells) and cells[0].strip().lower() == "test"
