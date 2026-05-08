"""SARIF parser, severity normalization, and triage-output validator.

Pure data-shape concerns. Raises `SarifShapeError` on malformed SARIF (caught
by the detection ladder for fall-through). Validator force-rewrites bad
verdicts/rationales to `unsure` per AC9 / AC10.
"""
from __future__ import annotations

import sys
from typing import Any

from sast_triage_constants import (
    _RATIONALE_MIN_TOKENS,
    _RATIONALE_NA_PATTERNS,
    _RATIONALE_STOP_LIST,
    _SARIF_SEVERITY_MAP,
    _SEMGREP_SEVERITY_MAP,
    _VALID_VERDICTS,
)


class SarifShapeError(ValueError):
    """SARIF document is JSON-parseable but missing required structure."""


def normalize_severity(raw: str, tool: str) -> str:
    """AC7 — Semgrep + SARIF severity strings normalize to internal scale."""
    if tool == "semgrep" and raw in _SEMGREP_SEVERITY_MAP:
        return _SEMGREP_SEVERITY_MAP[raw]
    if tool == "sarif" and raw in _SARIF_SEVERITY_MAP:
        return _SARIF_SEVERITY_MAP[raw]
    sys.stderr.write(
        f"SAST: unknown severity {raw!r} from tool={tool}; defaulting to INFO\n"
    )
    return "INFO"


def _safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _extract_finding(result: dict, tool_kind: str) -> dict:
    """Pull a normalized finding dict out of one SARIF result entry."""
    rule_id = result.get("ruleId")
    level = result.get("level", "warning")
    message = _safe_get(result, "message", "text", default="")
    locations = result.get("locations") or [{}]
    phys = locations[0].get("physicalLocation", {}) if isinstance(locations[0], dict) else {}
    file_uri = _safe_get(phys, "artifactLocation", "uri")
    line = _safe_get(phys, "region", "startLine")
    if rule_id is None or file_uri is None or line is None:
        raise SarifShapeError(
            f"result missing rule_id/file/line: rule_id={rule_id}, file={file_uri}, line={line}"
        )
    return {
        "rule_id": rule_id,
        "tool": "semgrep" if tool_kind == "semgrep" else "other",
        "file": file_uri,
        "line": line,
        "sast_severity": normalize_severity(level, tool=tool_kind),
        "message": message,
        "snippet": _safe_get(phys, "region", "snippet", "text", default=""),
    }


def parse_sarif(sarif: dict, changed_files: list[str]) -> list[dict]:
    """Flatten SARIF runs[].results[] → normalized findings, changed-files only."""
    runs = sarif.get("runs")
    if not isinstance(runs, list):
        raise SarifShapeError("missing or non-list `runs` key")
    changed_set = set(changed_files)
    findings: list[dict] = []
    for run in runs:
        tool_name = _safe_get(run, "tool", "driver", "name", default="").lower()
        tool_kind = "semgrep" if "semgrep" in tool_name else "sarif"
        for result in run.get("results") or []:
            finding = _extract_finding(result, tool_kind)
            if finding["file"] in changed_set:
                findings.append(finding)
    return findings


def _rationale_rejection_reason(rationale: Any) -> str | None:
    """Return rejection reason or None if rationale is acceptable (AC9)."""
    if not isinstance(rationale, str):
        return "non-string"
    stripped = rationale.strip()
    if not stripped:
        return "empty-or-whitespace"
    lowered = stripped.lower()
    if lowered in _RATIONALE_NA_PATTERNS:
        return "na-pattern"
    collapsed = " ".join(lowered.split())
    if collapsed in _RATIONALE_STOP_LIST:
        return "stop-list"
    tokens = stripped.split()
    if len(tokens) < _RATIONALE_MIN_TOKENS:
        return f"too-few-tokens ({len(tokens)} < {_RATIONALE_MIN_TOKENS})"
    return None


def _force_unsure(reason: str, original_rationale: Any) -> dict:
    """Build the system rationale per AC9 / AC10."""
    excerpt = ""
    if isinstance(original_rationale, str):
        excerpt = original_rationale.strip()[:60]
    return {
        "verdict": "unsure",
        "rationale": (
            f"Triage parser rejected model rationale: {reason}; "
            f"defaulting to unsure per conservatism rule "
            f"(rationale was: {excerpt})"
        ),
    }


def validate_triage_output(parsed: dict) -> dict:
    """Apply AC9 + AC10. Returns `{verdict, rationale}`."""
    verdict = parsed.get("verdict") if isinstance(parsed, dict) else None
    rationale = parsed.get("rationale") if isinstance(parsed, dict) else None

    if verdict not in _VALID_VERDICTS:
        return _force_unsure(
            f"verdict {verdict!r} not in {sorted(_VALID_VERDICTS)}",
            rationale,
        )
    rejection = _rationale_rejection_reason(rationale)
    if rejection is not None:
        return _force_unsure(rejection, rationale)
    return {"verdict": verdict, "rationale": rationale}
