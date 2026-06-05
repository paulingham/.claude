#!/usr/bin/env python3
"""Phase-boundary token measurement and handoff compression helper.

Implements the CAT (arXiv:2512.22087) measure+enforce-handoff step.

Args (positional):
  metrics_dir  ts  phase_from  phase_to  doc

Where doc is the raw phase state-file body (tokens_before source per R2).

Emits one JSONL record to {metrics_dir}/phase-boundary.jsonl.
Advisory mode only: does NOT rewrite the handoff file.
Python stdlib only.
"""
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jsonl_append import append_jsonl

_EXPECTED_ARGC = 6  # script + 5 positional args
_DEFAULT_N = 5
_SUMMARY_MARKER = "summarized"
_FINDINGS_HEADERS = {"## Key Findings", "## Next Phase Input"}
# Matches genuine AC-criterion list items: "- AC<digit>" or "* AC<digit>"
_AC_CRITERION_RE = re.compile(r'^[-*] AC\d')
_GOAL_HEADER = "## Goal"


def count_tokens(s: str) -> int:
    """Return ceil(utf8_bytes / 3.5). Empty string returns 0."""
    byte_count = len(s.encode("utf-8"))
    if byte_count == 0:
        return 0
    return math.ceil(byte_count / 3.5)


def _extract_findings(lines: list) -> list:
    """Extract top-level list items (- or * at column 0) with their continuations.

    Returns a list of raw source strings, each a complete finding including any
    trailing blank line that immediately follows it (preserving inter-finding
    spacing for verbatim round-trip).

    Only genuine AC-criterion lines (matching ``- AC<digit>`` or ``* AC<digit>``)
    are excluded; items like ``- ACME thing`` or ``- AC reconciliation`` are kept.
    """
    findings = []
    current_raw = []       # raw (unstripped) lines belonging to current finding
    in_findings_section = False

    for line in lines:
        stripped = line.rstrip()
        if stripped in _FINDINGS_HEADERS:
            in_findings_section = True
            continue
        if stripped.startswith("## ") and stripped not in _FINDINGS_HEADERS:
            in_findings_section = False
            if current_raw:
                findings.append("\n".join(current_raw))
                current_raw = []
            continue
        if not in_findings_section:
            continue

        is_top_level_item = stripped.startswith("- ") or stripped.startswith("* ")
        is_criterion = bool(_AC_CRITERION_RE.match(stripped))
        is_continuation = (
            (line.startswith("  ") or line.startswith("\t")) and bool(current_raw)
        )
        is_blank = stripped == ""

        if is_top_level_item and not is_criterion:
            if current_raw:
                findings.append("\n".join(current_raw))
            current_raw = [line]
        elif is_top_level_item and is_criterion:
            # genuine AC criterion — flush current finding (if any), skip this line
            if current_raw:
                findings.append("\n".join(current_raw))
                current_raw = []
        elif is_continuation:
            current_raw.append(line)
        elif is_blank and current_raw:
            # blank line following a finding — attach to current so it round-trips
            current_raw.append(line)

    if current_raw:
        # strip trailing blank lines from the last finding
        while current_raw and current_raw[-1].rstrip() == "":
            current_raw.pop()
        if current_raw:
            findings.append("\n".join(current_raw))
    return findings


def _split_goal_and_body(doc: str):
    """Split doc into (preamble_lines, findings_section_lines).

    Preamble = everything up to (but not including) the first findings header.
    Findings section = from the findings header onwards.
    """
    lines = doc.splitlines()
    for i, line in enumerate(lines):
        if line.rstrip() in _FINDINGS_HEADERS:
            return lines[:i], lines[i:]
    return lines, []


def _goal_present_in(text: str) -> bool:
    """Return True when the text contains a ## Goal section with non-empty content."""
    return _GOAL_HEADER in text


def compress_handoff(doc: str, n: int = _DEFAULT_N) -> str:
    """Compress a phase handoff document per R1 contract.

    - Goal block and all AC-criterion lines: retained verbatim.
    - Last n findings: retained verbatim (byte-identical, including blank separators).
    - Earlier findings: replaced by a single summary line.
    - No other transformation.
    """
    preamble_lines, findings_lines = _split_goal_and_body(doc)
    findings = _extract_findings(findings_lines)

    if len(findings) <= n:
        return doc

    elided_count = len(findings) - n
    kept_findings = findings[elided_count:]
    summary_line = f"- ({_SUMMARY_MARKER} {elided_count} earlier findings)"

    header_line = findings_lines[0] if findings_lines else ""
    output_parts = list(preamble_lines)
    output_parts.append(header_line)
    output_parts.append("")
    output_parts.append(summary_line)
    for finding in kept_findings:
        # Strip any trailing blank lines stored inside the finding; the separator
        # blank added here provides exactly one blank line between findings.
        finding_stripped = finding.rstrip("\n").rstrip()
        output_parts.append("")
        output_parts.append(finding_stripped)

    result = "\n".join(output_parts)
    result = result.rstrip("\n")
    if doc.endswith("\n"):
        result += "\n"
    return result


def build_record(ts, phase_from, phase_to, tokens_before, tokens_after, last_n,
                 *, goal_retained: bool = True):
    """Build the phase-boundary JSONL record.

    All fields are required; none are omitted.  goal_retained is caller-computed
    (True when the ## Goal block is present in the compressed output).
    """
    return {
        "ts": ts,
        "phase_from": phase_from,
        "phase_to": phase_to,
        "tokens_before": tokens_before,
        "tokens_after": tokens_after,
        "goal_retained": goal_retained,
        "last_n_full": last_n,
        "mode": "advisory",
    }


def main(argv):
    """Entry point. argv[1]=metrics_dir, argv[2]=ts, argv[3]=phase_from,
    argv[4]=phase_to, argv[5]=doc.
    """
    if len(argv) != _EXPECTED_ARGC:
        print(
            f"phase_boundary_tokens: expected {_EXPECTED_ARGC - 1} args, got {len(argv) - 1}",
            file=sys.stderr,
        )
        return 0
    try:
        _, metrics_dir, ts, phase_from, phase_to, doc = argv
        tokens_before = count_tokens(doc)
        compressed = compress_handoff(doc, n=_DEFAULT_N)
        tokens_after = count_tokens(compressed)
        goal_retained = _goal_present_in(compressed)
        rec = build_record(
            ts, phase_from, phase_to, tokens_before, tokens_after, _DEFAULT_N,
            goal_retained=goal_retained,
        )
        append_jsonl(metrics_dir, "phase-boundary.jsonl", rec)
    except Exception:  # noqa: BLE001 — advisory helper must never crash the pipeline
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
