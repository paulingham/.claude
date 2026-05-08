"""SAST triage — public API for `/security-review` § 0.

The agent IS the LLM caller (skill § 0.3 contains the iteration loop).
This module exposes only validator + plumbing — NO LLM calls, no
network I/O.

Submodules:
  - sast_triage_constants: stop-list, severity maps, regexes
  - sast_triage_parser:    SARIF parsing, severity normalization, validator
  - sast_triage_detection: 4-rung detection ladder
  - sast_triage_telemetry: JSONL writers (main + bypass + parse-failed)
  - sast_triage_render:    merge-block render + AC18 audit
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Re-export public surface (test imports + skill caller use these).
from sast_triage_constants import (  # noqa: F401
    _RATIONALE_MIN_TOKENS,
    _RATIONALE_STOP_LIST,
)
from sast_triage_parser import (  # noqa: F401
    SarifShapeError,
    normalize_severity,
    parse_sarif,
    validate_triage_output,
)
from sast_triage_detection import detect_findings  # noqa: F401
from sast_triage_telemetry import (  # noqa: F401
    write_bypass_record,
    write_decision_jsonl,
    write_parse_failed_record,
)
from sast_triage_render import (  # noqa: F401
    audit_agent_output,
    render_merge_block,
)


def triage_finding(parsed_model_output: dict, finding: dict) -> dict:
    """AC8 — validate a model's triage output for one finding.

    NOT an LLM call. The agent invokes this AFTER getting the model's
    response. `finding` is part of the signature so the caller binds
    finding metadata into the decision record at the call site.
    """
    return validate_triage_output(parsed_model_output)


def detect_and_triage(
    *,
    task_id: str,
    changed_files: list[str],
    scratchpad_dir: Path | str | None = None,
) -> dict:
    """Top-level entry: § 0 detection + bypass-handling.

    Verdicts:
      - TRIAGE_BYPASSED — bypass switch set
      - TRIAGE_NO_INPUT — no rung had any input
      - TRIAGE_PARSE_FAILED — every rung that resolved produced parse errors
      - TRIAGE_READY — findings detected; agent loops § 0.3 next
    """
    if os.environ.get("CLAUDE_DISABLE_SAST_TRIAGE") == "1":
        sys.stderr.write("SAST triage bypassed via CLAUDE_DISABLE_SAST_TRIAGE\n")
        write_bypass_record(task_id=task_id)
        return {"verdict": "TRIAGE_BYPASSED", "findings": [], "source": None}

    if scratchpad_dir is None:
        scratchpad_dir = Path("pipeline-state") / task_id / "scratchpad"

    failed_rungs: list[dict] = []
    findings, source = detect_findings(
        scratchpad_dir=scratchpad_dir,
        changed_files=changed_files,
        failed_rungs=failed_rungs,
    )
    if findings:
        return {"verdict": "TRIAGE_READY", "findings": findings, "source": source}
    if failed_rungs:
        write_parse_failed_record(task_id=task_id, failed_rungs=failed_rungs)
        return {
            "verdict": "TRIAGE_PARSE_FAILED",
            "findings": [],
            "source": source,
            "failed_rungs": failed_rungs,
        }
    return {"verdict": "TRIAGE_NO_INPUT", "findings": [], "source": source}
