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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jsonl_append import append_jsonl

_EXPECTED_ARGC = 6  # script + 5 positional args
_DEFAULT_N = 5
_SUMMARY_MARKER = "summarized"
_FINDINGS_HEADERS = {"## Key Findings", "## Next Phase Input"}


def count_tokens(s: str) -> int:
    """Return ceil(utf8_bytes / 3.5). Empty string returns 0."""
    byte_count = len(s.encode("utf-8"))
    if byte_count == 0:
        return 0
    return math.ceil(byte_count / 3.5)


def _extract_findings(lines: list) -> list:
    """Extract top-level list items (- or * at column 0) with their continuations.

    Returns a list of strings, each a complete finding (item + indented lines).
    AC lines (starting with '- AC') are excluded.
    """
    findings = []
    current = []
    in_findings_section = False

    for line in lines:
        stripped = line.rstrip()
        if stripped in _FINDINGS_HEADERS:
            in_findings_section = True
            continue
        if stripped.startswith("## ") and stripped not in _FINDINGS_HEADERS:
            in_findings_section = False
            if current:
                findings.append("\n".join(current))
                current = []
            continue
        if not in_findings_section:
            continue
        is_top_level_item = stripped.startswith("- ") or stripped.startswith("* ")
        is_continuation = (stripped.startswith("  ") or stripped.startswith("\t")) and bool(current)
        is_ac_line = stripped.startswith("- AC") or stripped.startswith("* AC")

        if is_top_level_item and not is_ac_line:
            if current:
                findings.append("\n".join(current))
            current = [stripped]
        elif is_continuation and current:
            current.append(stripped)
        elif is_top_level_item and is_ac_line:
            if current:
                findings.append("\n".join(current))
                current = []

    if current:
        findings.append("\n".join(current))
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


def compress_handoff(doc: str, n: int = _DEFAULT_N) -> str:
    """Compress a phase handoff document per R1 contract.

    - Goal block and all AC lines: retained verbatim.
    - Last n findings: retained verbatim.
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

    # Find the findings header line index in findings_lines
    header_line = findings_lines[0] if findings_lines else ""
    output_lines = list(preamble_lines)
    output_lines.append(header_line)
    output_lines.append("")
    output_lines.append(summary_line)
    for finding in kept_findings:
        for fline in finding.splitlines():
            output_lines.append(fline)

    result = "\n".join(output_lines)
    if doc.endswith("\n"):
        result += "\n"
    return result


def build_record(ts, phase_from, phase_to, tokens_before, tokens_after, last_n):
    """Build the JSONL record; omit-not-null: all fields required here."""
    return {
        "ts": ts,
        "phase_from": phase_from,
        "phase_to": phase_to,
        "tokens_before": tokens_before,
        "tokens_after": tokens_after,
        "goal_retained": True,
        "last_n_full": last_n,
        "mode": "advisory",
    }


def main(argv):
    """Entry point. argv[1]=metrics_dir, argv[2]=ts, argv[3]=phase_from,
    argv[4]=phase_to, argv[5]=doc.
    """
    if len(argv) != _EXPECTED_ARGC:
        return 0
    try:
        _, metrics_dir, ts, phase_from, phase_to, doc = argv
        tokens_before = count_tokens(doc)
        compressed = compress_handoff(doc, n=_DEFAULT_N)
        tokens_after = count_tokens(compressed)
        rec = build_record(ts, phase_from, phase_to, tokens_before, tokens_after, _DEFAULT_N)
        append_jsonl(metrics_dir, "phase-boundary.jsonl", rec)
    except Exception:  # noqa: BLE001 — advisory helper must never crash the pipeline
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
