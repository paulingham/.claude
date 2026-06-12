"""Pure decision core for the in-build-loop scan gate (hooks/build-loop-scan.sh).

This module owns the CANONICAL secret-detection patterns for the HARD-BLOCK
path. It is the single source of truth for "what counts as an introduced secret"
in a worktree commit. Keeping it import-clean (no subprocess, no filesystem I/O)
makes the secret-vs-clean decision unit-testable without a git checkout, exactly
as `hooks/_lib/agentic_security_gate.py` is for its gate.

The patterns here gate the STAGED DIFF at commit time (HARD-BLOCK, exit 2).
Any advisory command-string logging is a separate concern handled by separate
hooks and MUST NOT collapse into this module, which is the enforcing path only.
"""
from __future__ import annotations

import re

# Canonical secret patterns. Each entry maps a category label (surfaced in the
# artifact + stderr) to the regex that fires the HARD BLOCK on a staged line.
_SECRET_PATTERNS = (
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws-secret", re.compile(r"AWS_SECRET_ACCESS_KEY\s*=")),
    ("private-key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    # Stripe live secret key (sk_live_ + 16+ alphanumeric chars)
    ("stripe-secret", re.compile(r"sk_live_[A-Za-z0-9]{16,}")),
    # GitHub tokens: personal (ghp_), OAuth (gho_), server-to-server (ghs_)
    ("github-token", re.compile(r"gh[pos]_[A-Za-z0-9]{16,}")),
    # Slack bot token (xoxb-)
    ("slack-token", re.compile(r"xoxb-[0-9A-Za-z-]{16,}")),
    (
        "generic-secret",
        re.compile(
            # Quoted (api_key = "..." or '...') OR unquoted (api_key=abcd...) >= 16 chars
            r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*(?:['\"][^'\"\s]{16,}['\"]|[^'\"\s]{16,})"
        ),
    ),
)

# Obvious-placeholder markers. A staged line carrying one of these is treated as
# a fixture/example, NOT a live secret — so test fixtures and documented example
# values elsewhere in the tree do not false-trip the block. The hook's OWN
# AC1 positive test stages its fixture OUTSIDE a fixtures path AND uses a value
# the path-exemption (not this marker list) governs, so the intended block fires.
_FAKE_MARKERS = ("EXAMPLE", "FAKE", "DUMMY", "PLACEHOLDER", "TEST-", "TEST_")


def is_fake_secret_marker(line: str) -> bool:
    """True when a line carries an obvious non-live placeholder token.

    Matches case-sensitively on the documented placeholder tokens so a real
    high-entropy credential (no marker) is never suppressed. This is a PURE
    predicate — the caller decides WHEN to apply it (only for staged lines
    whose file path sits under a fixtures/tests directory), so the documented
    example AWS key still FIRES the block when introduced in real source.
    """
    return any(marker in (line or "") for marker in _FAKE_MARKERS)


def scan_for_secrets(staged_text: str) -> list[str]:
    """Return the sorted, de-duplicated secret categories present in the text.

    Scans every line unconditionally — placeholder suppression is the caller's
    path-scoped concern, not this function's. The caller pre-filters fixture
    lines via `is_fake_secret_marker` before passing them here when (and only
    when) the originating path is exempt.
    """
    found = set()
    for line in (staged_text or "").splitlines():
        for category, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                found.add(category)
    return sorted(found)


def decision(
    secrets: list[str],
    sast_findings: int,
    dep_findings: int,
    disabled: bool,
) -> dict:
    """Compose the gate verdict from the scan inputs.

    Returns {verdict, exit_code, categories}. Precedence: bypass > secret block
    > advisory findings > skipped/passed (resolved by the caller's tool census).
    """
    if disabled:
        return {"verdict": "BYPASSED", "exit_code": 0, "categories": secrets}
    if secrets:
        return {"verdict": "BLOCKED", "exit_code": 2, "categories": secrets}
    if sast_findings or dep_findings:
        return {"verdict": "FINDINGS", "exit_code": 0, "categories": []}
    return {"verdict": "PASSED", "exit_code": 0, "categories": []}
