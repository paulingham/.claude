"""Detection ladder — rungs 1-4. Falls through on parse errors (AC19).

- Rung 1: $CLAUDE_SAST_SARIF_PATH
- Rung 2: pipeline-state/{task}/scratchpad/sast-*.sarif
- Rung 3: direct semgrep subprocess (AC4 / AC4a / AC4b / AC4c)
- Rung 4: nothing — TRIAGE_NO_INPUT
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from sast_triage_constants import _SEMGREP_TIMEOUT_DEFAULT
from sast_triage_parser import SarifShapeError, parse_sarif


def _read_sarif_file(path: Path) -> tuple[dict | None, str | None]:
    """Return (parsed_dict, error_class_or_None)."""
    try:
        text = path.read_text()
    except OSError as exc:
        return None, f"file-read-error: {exc}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        return None, "json-decode-error"


def _try_parse_sarif_file(
    path_obj: Path, *, rung: int, changed_files: list[str], failed_rungs: list,
) -> list[dict] | None:
    """Read + parse one SARIF file. Returns findings, or None on failure."""
    sarif, error = _read_sarif_file(path_obj)
    if error:
        sys.stderr.write(f"SAST: rung={rung} source={path_obj} error={error}\n")
        failed_rungs.append({"rung": rung, "source": str(path_obj), "error_class": error})
        return None
    if sarif is None:
        return None
    try:
        return parse_sarif(sarif, changed_files=changed_files)
    except SarifShapeError as exc:
        sys.stderr.write(
            f"SAST: rung={rung} source={path_obj} error=sarif-shape-error: {exc}\n"
        )
        failed_rungs.append(
            {"rung": rung, "source": str(path_obj), "error_class": "sarif-shape-error"}
        )
        return None


def _rung1(changed_files: list[str], failed_rungs: list) -> tuple[list[dict] | None, dict | None]:
    sarif_path = os.environ.get("CLAUDE_SAST_SARIF_PATH")
    if not sarif_path or not Path(sarif_path).is_file():
        return None, None
    findings = _try_parse_sarif_file(
        Path(sarif_path), rung=1, changed_files=changed_files, failed_rungs=failed_rungs,
    )
    if findings is None:
        return None, None
    return findings, {"rung": 1, "path": sarif_path}


def _rung2(scratchpad_dir: Path, changed_files: list[str], failed_rungs: list) -> tuple[list[dict] | None, dict | None]:
    if not scratchpad_dir.is_dir():
        return None, None
    for path_obj in sorted(scratchpad_dir.glob("sast-*.sarif")):
        findings = _try_parse_sarif_file(
            path_obj, rung=2, changed_files=changed_files, failed_rungs=failed_rungs,
        )
        if findings is not None:
            return findings, {"rung": 2, "path": str(path_obj)}
    return None, None


def _semgrep_subprocess(changed_files: list[str], failed_rungs: list) -> dict | None:
    """Invoke semgrep, return parsed SARIF dict or None on failure."""
    timeout = int(os.environ.get("CLAUDE_SAST_SEMGREP_TIMEOUT_SEC", _SEMGREP_TIMEOUT_DEFAULT))
    cmd = ["semgrep", "--sarif", "--json", "--quiet", "--", *changed_files]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        sys.stderr.write("SAST: rung=3 source=semgrep status=timeout\n")
        failed_rungs.append({"rung": 3, "source": "semgrep", "error_class": "timeout"})
        return None
    except FileNotFoundError:
        sys.stderr.write("SAST: rung=3 source=semgrep status=not-installed\n")
        return None
    if proc.returncode != 0:
        sys.stderr.write(f"SAST: rung=3 source=semgrep status=exit-code-{proc.returncode}\n")
        failed_rungs.append(
            {"rung": 3, "source": "semgrep", "error_class": f"exit-code-{proc.returncode}"}
        )
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.stderr.write("SAST: rung=3 source=semgrep status=semgrep-shape-error\n")
        failed_rungs.append(
            {"rung": 3, "source": "semgrep", "error_class": "semgrep-shape-error"}
        )
        return None


def _rung3(changed_files: list[str], failed_rungs: list) -> tuple[list[dict] | None, dict | None]:
    """AC4 / AC4a / AC4b / AC4c — direct semgrep subprocess invocation."""
    if shutil.which("semgrep") is None:
        sys.stderr.write("SAST: rung=3 source=semgrep status=not-installed\n")
        return None, None
    sarif = _semgrep_subprocess(changed_files, failed_rungs)
    if sarif is None:
        return None, None
    try:
        findings = parse_sarif(sarif, changed_files=changed_files)
    except SarifShapeError as exc:
        sys.stderr.write(f"SAST: rung=3 source=semgrep status=sarif-shape-error: {exc}\n")
        failed_rungs.append(
            {"rung": 3, "source": "semgrep", "error_class": "sarif-shape-error"}
        )
        return None, None
    return findings, {"rung": 3, "path": "semgrep"}


def detect_findings(
    *,
    scratchpad_dir,
    changed_files: list[str],
    failed_rungs: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    """Walk the 4-rung detection ladder. Returns (findings, source_metadata)."""
    if failed_rungs is None:
        failed_rungs = []
    scratchpad_dir = Path(scratchpad_dir)

    for rung_fn in (
        lambda: _rung1(changed_files, failed_rungs),
        lambda: _rung2(scratchpad_dir, changed_files, failed_rungs),
        lambda: _rung3(changed_files, failed_rungs),
    ):
        findings, source = rung_fn()
        if source is not None:
            return findings, source
    return [], {"rung": 4, "path": ""}
