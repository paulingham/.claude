"""Helpers for instinct_loader: parse, validate, normalize, log."""
import json
import re
import subprocess
from pathlib import Path

import yaml

_FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_BODY = re.compile(r"^## Pattern[ \t]*\n(.*?)(?=\n##|\Z)",
                   re.MULTILINE | re.DOTALL)
_REQUIRED = ("id", "confidence", "roles")


def parse_file(path):
    match = _FM.match(path.read_text())
    fm = yaml.safe_load(match.group(1)) if match else None
    return (fm, match.group(2) if match else "")


def extract_summary(body):
    m = _BODY.search(body)
    text = (m.group(1).strip() if m else "")
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    return first[:200]


def validate(fm, body):
    if not isinstance(fm, dict):
        return "malformed-yaml"
    missing = next((k for k in _REQUIRED if k not in fm), None)
    if missing:
        return f"missing-{missing}-field"
    return None if extract_summary(body) else "missing-or-empty-pattern-body"


def normalize(fm, body, scope):
    return {"id": fm["id"], "confidence": float(fm["confidence"]),
            "roles": list(fm["roles"]), "domain": fm.get("domain", ""),
            "scope": scope, "pattern_summary": extract_summary(body)}


def log_warning(path, reason):
    script = str(Path(__file__).parent / "log-injection.sh")
    resolved = json.dumps({"file": str(path), "reason": reason})
    cmd = ["bash", script, '{"tool_input":{"subagent_type":""}}',
           resolved, "load-warning", "instinct-injections.jsonl"]
    subprocess.run(cmd, stderr=subprocess.DEVNULL, check=False)
