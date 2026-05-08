"""Merge-block renderer (AC11, AC12) + agent-output audit (AC18)."""
from __future__ import annotations

import re
from typing import Iterable

from sast_triage_constants import (
    _AGENT_VERDICT_RE,
    _DISMISS_HEADING_RE,
    _FORBIDDEN_AGENT_VERDICT,
    _VALID_AGENT_VERDICTS,
)


def _render_entry(entry: dict, *, kind: str) -> list[str]:
    finding = entry["finding"]
    rationale = entry["rationale"]
    label = "Triage rationale" if kind == "keep" else "Triage uncertainty"
    return [
        (f"- **{finding['rule_id']}** `{finding['file']}:{finding['line']}` "
         f"(sast={finding['sast_severity']}) — {finding.get('message', '')}"),
        f"  - {label}: {rationale}",
    ]


def _section(triaged_subset: list[dict], kind: str) -> list[str]:
    plural = "s" if len(triaged_subset) != 1 else ""
    lines = [f"### {kind} ({len(triaged_subset)} finding{plural})"]
    for entry in triaged_subset:
        lines.extend(_render_entry(entry, kind=kind))
    return lines


def render_merge_block(triaged: list[dict]) -> str:
    """Render `## SAST Triage Findings (Pre-Rubric)` markdown block.

    `drop` excluded from the block (in JSONL only — AC12).
    """
    keep = [t for t in triaged if t["verdict"] == "keep"]
    unsure = [t for t in triaged if t["verdict"] == "unsure"]
    lines = [
        "## SAST Triage Findings (Pre-Rubric)",
        "",
        ("The following findings were triaged into your review. "
         "You MUST address each one in your output (either confirm it as a "
         "finding with severity, or explain why it does not apply — and your "
         "independent OWASP analysis still runs alongside)."),
        "",
    ]
    lines.extend(_section(keep, "keep"))
    lines.append("")
    lines.extend(_section(unsure, "unsure"))
    return "\n".join(lines)


# ---- AC18 audit ------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^(```|~~~)")


def _push_heading(stack: list[tuple[int, str]], level: int, text: str) -> None:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, text))


def _walk_headings(text: str) -> Iterable[tuple[tuple, int, str]]:
    stack: list[tuple[int, str]] = []
    in_fence = False
    for index, line in enumerate(text.splitlines()):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            yield tuple(stack), index, line
            continue
        match = None if in_fence else _HEADING_RE.match(line)
        if match:
            _push_heading(stack, len(match.group(1)), match.group(2))
            continue
        yield tuple(stack), index, line


def _stack_at_index(walked: list, target_idx: int) -> tuple:
    last_stack: tuple = ()
    for stack, idx, _line in walked:
        if idx == target_idx:
            return stack
        if idx > target_idx:
            break
        last_stack = stack
    return last_stack


def _strikethrough_contains(line: str, rule_id: str) -> bool:
    """True if rule_id appears inside a `~~...~~` span on this line."""
    return any(rule_id in m.group(1) for m in re.finditer(r"~~(.+?)~~", line))


def _verdict_within(
    lines: list[str], target_idx: int, *,
    radius: int = 5, claimed: set[int] | None = None,
) -> tuple[bool, str | None, int | None]:
    """Find an unclaimed `agent_verdict:` token within ±radius of target_idx."""
    claimed = claimed or set()
    lo = max(0, target_idx - radius)
    hi = min(len(lines), target_idx + radius + 1)
    for i in range(lo, hi):
        if i in claimed:
            continue
        match = _AGENT_VERDICT_RE.search(lines[i])
        if match:
            return True, match.group(1).strip().lower(), i
    return False, None, None


def _check_candidate(
    cand_idx: int, cand_line: str, *,
    rule_id: str, walked: list, lines: list[str],
    claimed: set[int],
) -> tuple[str | None, int | None]:
    """Return (reason, verdict_idx). reason None ⇒ candidate passes."""
    if _strikethrough_contains(cand_line, rule_id):
        return "wrapped-in-strikethrough", None
    stack = _stack_at_index(walked, cand_idx)
    under_findings = any(
        level == 2 and heading_text == "Findings"
        for level, heading_text in stack
    )
    under_dismissal = any(
        _DISMISS_HEADING_RE.search(heading_text)
        for _level, heading_text in stack
    )
    if not under_findings:
        return "not-under-findings-heading", None
    if under_dismissal:
        return "under-dismissal-heading", None
    has_token, verdict_value, verdict_idx = _verdict_within(
        lines, cand_idx, radius=5, claimed=claimed,
    )
    if not has_token:
        return "missing-agent-verdict-within-5-lines", None
    if verdict_value == _FORBIDDEN_AGENT_VERDICT:
        return "agent-verdict-not-applicable-forbidden", None
    if verdict_value not in _VALID_AGENT_VERDICTS:
        return f"invalid-agent-verdict-{verdict_value}", None
    return None, verdict_idx


def audit_agent_output(text: str, triage_findings: list[dict]) -> dict:
    """AC18 — verify every keep/unsure finding is preserved per the rubric."""
    lines = text.splitlines()
    walked = list(_walk_headings(text))
    violations: list[dict] = []
    claimed_verdicts: set[int] = set()

    for finding in triage_findings:
        rule_id = finding["rule_id"]
        location_token = f"{finding['file']}:{finding['line']}"
        candidates = [
            (idx, line) for idx, line in enumerate(lines)
            if rule_id in line and location_token in line
        ]
        if not candidates:
            violations.append(_violation(finding, "missing-from-output"))
            continue
        last_reason = "no-valid-occurrence"
        ok_idx: int | None = None
        for cand_idx, cand_line in candidates:
            reason, verdict_idx = _check_candidate(
                cand_idx, cand_line,
                rule_id=rule_id, walked=walked, lines=lines,
                claimed=claimed_verdicts,
            )
            if reason is None:
                ok_idx = verdict_idx
                break
            last_reason = reason
        if ok_idx is None:
            violations.append(_violation(finding, last_reason))
        else:
            claimed_verdicts.add(ok_idx)

    return {"ok": not violations, "violations": violations}


def _violation(finding: dict, reason: str) -> dict:
    return {
        "rule_id": finding["rule_id"],
        "file": finding["file"],
        "line": finding["line"],
        "reason": reason,
    }
