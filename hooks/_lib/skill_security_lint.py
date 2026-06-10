"""Skill security lint helper — scan SKILL.md / skill _lib files for:

  - injection: imperative override / authorization-escalation patterns.
  - secret: hardcoded credentials (AWS keys, generic api_key=, private keys).
  - over_broad_tool: frontmatter tools: granting Write/Edit/Agent/Bash to
    read-only phases (review, final-gate, utility) or wildcard tools: ["*"].

Public API:
    lint_skill_files(paths) -> dict

Return shape:
    {
        "findings": [{"file": str, "line": int, "category": str,
                      "severity": str, "snippet": str}],
        "counts": {"injection": int, "secret": int, "over_broad_tool": int},
        "files_scanned": int,
        "clean": bool,
    }

Design: fail-open (never raises), bounded (skip files >1MB), stdlib only.
One detector per function, cyclomatic complexity <=5 each.
"""
from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FILE_BYTES = 1 * 1024 * 1024  # 1 MB — mirror spec-grounding bound

# Adversarial override phrases; deliberately tight to avoid false positives.
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+the\s+above", re.IGNORECASE),
    re.compile(r"you\s+must\s+now\b", re.IGNORECASE),
    re.compile(r"bypass\s+the\s+gate", re.IGNORECASE),
    re.compile(r"disable\s+the\s+(security\s+)?(gate|guard|hook)", re.IGNORECASE),
    re.compile(r"grant\s+yourself\b", re.IGNORECASE),
    re.compile(r"as\s+an\s+admin\s+you\b", re.IGNORECASE),
]

# Credential patterns; deliberately high-signal.
_SECRET_PATTERNS: list[re.Pattern] = [
    # AWS access key ID
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Generic assignment: api_key = "..." / token: '...' / password = "..."
    re.compile(
        r"(?:api[_\-]?key|token|password|secret)\s*[=:]\s*[\"'][^\"']{8,}",
        re.IGNORECASE,
    ),
    # PEM private key header
    re.compile(r"-----BEGIN\s+(?:\w+\s+)?PRIVATE KEY-----"),
]

# Tools that confer write/execution capability.
_OVER_BROAD_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "Agent", "Bash"})

# Phases where write/execution tools are NOT expected.
_READ_ONLY_PHASES = frozenset({"review", "final-gate", "utility"})


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def lint_skill_files(paths: list) -> dict:
    """Scan skill files at `paths` for injection, secrets, and over-broad tools.

    Fail-open: catches all exceptions internally — never raises.
    Bounded: skips files larger than 1 MB.
    """
    findings: list[dict] = []
    files_scanned = 0

    for path in paths:
        try:
            file_findings = _scan_file(str(path))
        except Exception:  # noqa: BLE001
            continue
        if file_findings is not None:
            findings.extend(file_findings)
            files_scanned += 1

    counts = _count_by_category(findings)
    return {
        "findings": findings,
        "counts": counts,
        "files_scanned": files_scanned,
        "clean": len(findings) == 0,
    }


# ---------------------------------------------------------------------------
# File-level scan
# ---------------------------------------------------------------------------

def _scan_file(path: str) -> list[dict] | None:
    """Return findings for one file, or None if the file should be skipped."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return []

    size = p.stat().st_size
    if size > _MAX_FILE_BYTES:
        return []  # bounded skip — not an error

    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    findings: list[dict] = []
    findings.extend(_detect_injection(path, lines))
    findings.extend(_detect_secrets(path, lines))
    findings.extend(_detect_over_broad_tools(path, text))
    return findings


# ---------------------------------------------------------------------------
# Detectors — one function per category, cyclomatic <=5 each
# ---------------------------------------------------------------------------

def _detect_injection(path: str, lines: list[str]) -> list[dict]:
    """Flag imperative override / authorization-escalation patterns."""
    findings = []
    for lineno, line in enumerate(lines, start=1):
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(line):
                findings.append(_make_finding(
                    path, lineno, "injection", "HIGH", line.strip()))
                break  # one finding per line max
    return findings


def _detect_secrets(path: str, lines: list[str]) -> list[dict]:
    """Flag hardcoded credential patterns."""
    findings = []
    for lineno, line in enumerate(lines, start=1):
        for pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(_make_finding(
                    path, lineno, "secret", "CRITICAL", line.strip()))
                break  # one finding per line max
    return findings


def _detect_over_broad_tools(path: str, text: str) -> list[dict]:
    """Flag wildcard tools: ["*"] or over-broad grants on read-only phases."""
    frontmatter = _extract_frontmatter(text)
    if not frontmatter:
        return []

    phase = _parse_phase(frontmatter)
    tools = _parse_tools(frontmatter)
    if not tools:
        return []

    findings = []
    if _has_wildcard_tools(tools):
        findings.append(_make_finding(
            path, 1, "over_broad_tool", "HIGH",
            "tools: [\"*\"] — wildcard tool grant"))
        return findings

    if phase in _READ_ONLY_PHASES:
        for tool in tools:
            if tool in _OVER_BROAD_TOOLS:
                findings.append(_make_finding(
                    path, 1, "over_broad_tool", "HIGH",
                    f"tool `{tool}` granted on read-only phase `{phase}`"))

    return findings


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _extract_frontmatter(text: str) -> str:
    """Return the YAML content between the first two `---` delimiters, or ''."""
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return match.group(1) if match else ""


def _parse_phase(frontmatter: str) -> str:
    """Extract `phase:` value from frontmatter, or empty string."""
    match = re.search(r"^phase:\s*[\"']?([^\s\"']+)[\"']?", frontmatter, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _parse_tools(frontmatter: str) -> list[str]:
    """Parse `tools:` from frontmatter — handles both list and inline forms."""
    # Inline form: tools: ["Write", "Read"] or tools: [Write, Read]
    inline = re.search(r"^tools:\s*\[([^\]]*)\]", frontmatter, re.MULTILINE)
    if inline:
        raw = inline.group(1)
        return [t.strip().strip("\"'") for t in raw.split(",") if t.strip()]

    # Block list form:
    # tools:
    #   - Write
    #   - Read
    block_match = re.search(
        r"^tools:\s*\n((?:[ \t]+-[^\n]+\n?)+)", frontmatter, re.MULTILINE)
    if block_match:
        items = re.findall(r"^[ \t]+-\s*[\"']?([^\"'\n]+)[\"']?",
                           block_match.group(1), re.MULTILINE)
        return [i.strip() for i in items if i.strip()]

    return []


def _has_wildcard_tools(tools: list[str]) -> bool:
    """Return True if tools contains a wildcard '*' entry."""
    return any(t.strip() in ("*", '"*"', "'*'") for t in tools)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _make_finding(path: str, line: int, category: str,
                  severity: str, snippet: str) -> dict:
    return {
        "file": path,
        "line": line,
        "category": category,
        "severity": severity,
        "snippet": snippet[:200],  # bounded snippet length
    }


def _count_by_category(findings: list[dict]) -> dict:
    counts: dict[str, int] = {"injection": 0, "secret": 0, "over_broad_tool": 0}
    for f in findings:
        category = f.get("category", "")
        if category in counts:
            counts[category] += 1
    return counts
