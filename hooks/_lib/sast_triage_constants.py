"""Module constants for SAST triage — one-line tunable knobs.

Stop-list, token threshold, severity maps, AC18 regexes. Centralised so
future tuning is a single-file change.
"""
from __future__ import annotations

import re

_RATIONALE_MIN_TOKENS = 8

_RATIONALE_STOP_LIST = frozenset({
    "safe",
    "benign",
    "ok",
    "fine",
    "false positive",
    "not an issue",
    "no issue",
    "looks fine",
    "looks safe",
})

_RATIONALE_NA_PATTERNS = frozenset({"n/a", "na", "none", "-", "null"})

_VALID_VERDICTS = frozenset({"keep", "drop", "unsure"})

_SEMGREP_SEVERITY_MAP = {"ERROR": "CRITICAL", "WARNING": "HIGH", "INFO": "LOW"}

_SARIF_SEVERITY_MAP = {
    "error": "HIGH",
    "warning": "MEDIUM",
    "note": "LOW",
    "none": "INFO",
}

_SEMGREP_TIMEOUT_DEFAULT = 60

# AC18 enforcement
_DISMISS_HEADING_RE = re.compile(
    r"(dismissed|skipped|not.applicable|not.a.finding|ignored|suppressed|out.of.scope)",
    re.IGNORECASE,
)
_AGENT_VERDICT_RE = re.compile(r"agent_verdict:\s*([a-zA-Z\-]+)")
_FORBIDDEN_AGENT_VERDICT = "not-applicable"
_VALID_AGENT_VERDICTS = frozenset({"confirmed", "downgraded"})
