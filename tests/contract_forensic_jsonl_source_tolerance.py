"""Tier 0 contract: downstream consumers of `metrics/{session-id}/
hook-injections.jsonl` (which carry the resolver's `source` field) MUST
tolerate the new value `"claude-effort-env"`.

Three sibling assertions, one per consumer:

1. `/forensics` (skills/forensics/SKILL.md and any helper scripts)
2. observation-capture (hooks/observation-capture.sh, skills/learn/SKILL.md,
   helpers under hooks/_lib/)
3. `/eval-model-effectiveness` (skills/eval-model-effectiveness/SKILL.md and
   aggregation helpers)

Today, none of the three consumers contain a hard-coded `source`-enum
allowlist or strict-schema validator. The contract asserts that absence is
preserved AFTER the new tier ships — i.e., adding `claude-effort-env` to
the resolver does not require any of these three consumers to learn the new
value. If a future PR adds a strict allowlist that omits the new value, this
contract fires and the omission is caught at PR time.

Detection method: substring grep across the consumers for hard-coded source
values that do NOT include the new value, in close proximity to a validator
shape (e.g., `if ... not in {...}`, `assert ... in {...}`, `allowed_sources
= {...}`). A discovered allowlist must include `"claude-effort-env"`; a bare
absence-of-allowlist passes by construction.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# ALLOWLIST_VALIDATOR_PATTERNS: regex sequences that indicate a hard-coded
# source-enum allowlist or validator. Each pattern captures a `{...}` /
# `[...]` literal that contains string-like tokens; the surrounding
# context narrows the match to validator shapes (containment check, not
# arbitrary mention).
ALLOWLIST_VALIDATOR_PATTERNS = [
    # Python-style `not in {"env", "explicit", ...}` / `in {"env", ...}`
    re.compile(
        r'(?:not\s+in|in)\s*[\{\[]([^\}\]]*)[\}\]]',
    ),
    # Python-style allowlist assignment:
    # `ALLOWED_SOURCES = {"env", "explicit", ...}`
    re.compile(
        r'(?:[A-Z_]*SOURCES?[A-Z_]*|allowed_sources?)\s*=\s*'
        r'[\{\[]([^\}\]]*)[\}\]]',
    ),
    # bash-style case statement: `case "$source" in env|explicit|role)`
    re.compile(
        r'case\s+[\$"][^"]*source[^"]*[\$"]\s+in\s+([^)]+)\)',
        re.IGNORECASE,
    ),
]

# Source tokens we expect the resolver to emit. If any allowlist mentions
# any of these (a strong signal it is a `source`-enum allowlist) AND
# omits "claude-effort-env", the contract fails.
KNOWN_RESOLVER_SOURCES = {"env", "explicit", "role", "default"}
NEW_SOURCE_VALUE = "claude-effort-env"


def _scan_file_for_strict_source_allowlist(path: Path) -> list[str]:
    """Return list of human-readable findings: an allowlist that mentions
    known resolver sources but omits the new value."""
    findings: list[str] = []
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return findings

    for pattern in ALLOWLIST_VALIDATOR_PATTERNS:
        for match in pattern.finditer(text):
            literal_body = match.group(1)
            tokens = re.findall(r'"([^"]+)"|\'([^\']+)\'', literal_body)
            tokens = [t[0] or t[1] for t in tokens]
            if not tokens:
                continue
            token_set = set(tokens)
            mentions_resolver_sources = bool(
                token_set & KNOWN_RESOLVER_SOURCES
            )
            if not mentions_resolver_sources:
                continue
            if NEW_SOURCE_VALUE in token_set:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            findings.append(
                f"{path}:{line_no}: allowlist {sorted(token_set)} mentions "
                f"resolver source tokens but omits "
                f"'{NEW_SOURCE_VALUE}'"
            )
    return findings


class ForensicReaderToleratesClaudeEffortEnvSource(unittest.TestCase):
    """Contract: `/forensics` (and any helper script it loads) does NOT
    contain a strict `source`-enum allowlist that would reject the new
    `claude-effort-env` value."""

    def test_forensic_reader_tolerates_claude_effort_env_source(self):
        targets = [
            REPO_ROOT / "skills" / "forensics" / "SKILL.md",
        ]
        # Include any forensics helper scripts referenced in the skill dir.
        forensics_dir = REPO_ROOT / "skills" / "forensics"
        if forensics_dir.is_dir():
            for sub in forensics_dir.rglob("*"):
                if sub.is_file() and sub.suffix in {".py", ".sh", ".md"}:
                    if sub not in targets:
                        targets.append(sub)

        all_findings: list[str] = []
        for target in targets:
            if not target.exists():
                continue
            all_findings.extend(_scan_file_for_strict_source_allowlist(target))

        self.assertEqual(
            all_findings,
            [],
            (
                "/forensics or helpers contain a strict source-enum "
                "allowlist that omits the new value 'claude-effort-env'. "
                "Either add the new value to the allowlist or remove the "
                "allowlist entirely (the consumers do not need a strict "
                "validator).\n  findings:\n    "
                + "\n    ".join(all_findings)
            ),
        )


class ObservationCaptureDoesNotRejectClaudeEffortEnvSource(unittest.TestCase):
    """Contract: observation-capture path (hook + learn skill + helpers)
    does NOT contain a strict `source`-enum allowlist that would reject the
    new `claude-effort-env` value."""

    def test_observation_capture_does_not_reject_claude_effort_env_source(
        self,
    ):
        targets = [
            REPO_ROOT / "hooks" / "observation-capture.sh",
            REPO_ROOT / "skills" / "learn" / "SKILL.md",
        ]
        hooks_lib = REPO_ROOT / "hooks" / "_lib"
        if hooks_lib.is_dir():
            for sub in hooks_lib.iterdir():
                if sub.is_file() and sub.suffix in {".py", ".sh"}:
                    targets.append(sub)

        all_findings: list[str] = []
        for target in targets:
            if not target.exists():
                continue
            all_findings.extend(_scan_file_for_strict_source_allowlist(target))

        self.assertEqual(
            all_findings,
            [],
            (
                "Observation-capture path contains a strict source-enum "
                "allowlist that omits 'claude-effort-env'. Either add the "
                "new value or remove the allowlist.\n  findings:\n    "
                + "\n    ".join(all_findings)
            ),
        )


class EvalModelEffectivenessAggregatesNewSource(unittest.TestCase):
    """Contract: `/eval-model-effectiveness` aggregation does NOT contain a
    strict `source`-enum filter that would silently drop records with the
    new `claude-effort-env` value."""

    def test_eval_model_effectiveness_aggregates_new_source(self):
        targets = [
            REPO_ROOT / "skills" / "eval-model-effectiveness" / "SKILL.md",
        ]
        eval_dir = REPO_ROOT / "skills" / "eval-model-effectiveness"
        if eval_dir.is_dir():
            for sub in eval_dir.rglob("*"):
                if sub.is_file() and sub.suffix in {".py", ".sh", ".md"}:
                    if sub not in targets:
                        targets.append(sub)

        all_findings: list[str] = []
        for target in targets:
            if not target.exists():
                continue
            all_findings.extend(_scan_file_for_strict_source_allowlist(target))

        self.assertEqual(
            all_findings,
            [],
            (
                "/eval-model-effectiveness contains a strict source-enum "
                "filter that omits 'claude-effort-env'. Either add the "
                "new value or remove the filter.\n  findings:\n    "
                + "\n    ".join(all_findings)
            ),
        )


if __name__ == "__main__":
    unittest.main()
