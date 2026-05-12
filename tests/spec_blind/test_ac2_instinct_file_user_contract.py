"""Spec-blind tests for AC2.

AC2 (verbatim from plan):
    An instinct file at
    learning/8efffd88329f34786e1828737702e911/instincts/v2.1.139-native-surface-mismatch.md
    exists with YAML frontmatter declaring id, confidence (numeric in [0,1]),
    roles (non-empty list containing architect AND infrastructure-engineer),
    domain (string), and scope (string).  Body contains a ## Pattern section
    discussing three v2.1.139 features (continueOnBlock, x-claude-code-agent-id,
    autoMode.hard_deny) as "looks like a fit but isn't" — body cites at least one
    canonical source (thinking-defaults.md, agent-protocol.md,
    code.claude.com/docs/en/hooks, code.claude.com/docs/en/settings).

User-facing contract:

  * The instinct loader (described in autonomous-intelligence rules) will load
    this file from disk on every Agent spawn in the relevant project hash.
  * If the file is missing or its frontmatter is malformed, the loader logs a
    load-warning and the instinct never reaches downstream agents — defeating
    the spike's whole purpose (preventing re-investigation).
  * If the body doesn't actually discuss the three named features, future
    architects/infra-engineers won't recognize the pattern when they encounter
    the same v2.1.139 names again.

These tests were authored WITHOUT reading the build agent's tests at
tests/test_instinct_v2139_native_surface_mismatch.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


# ---------- frontmatter helpers ----------


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a Markdown file into (yaml_frontmatter_dict, body_str).

    Frontmatter MUST be delimited by leading and trailing '---' lines per the
    canonical instinct file shape (referenced by autonomous-intelligence rules).
    """
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        raise AssertionError(
            "spec-blind: AC2 violated — instinct file does not begin with a "
            "'---' frontmatter delimiter"
        )
    # Locate the closing delimiter.
    parts = re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)
    # parts[0] = "" (before first ---), parts[1] = yaml, parts[2] = body
    assert len(parts) >= 3, (
        "spec-blind: AC2 violated — instinct file has no closing '---' "
        "frontmatter delimiter"
    )
    yaml_text = parts[1]
    body = parts[2].lstrip("\n")
    fm = yaml.safe_load(yaml_text)
    assert isinstance(fm, dict), (
        "spec-blind: AC2 violated — instinct frontmatter must parse to a YAML mapping"
    )
    return fm, body


def _load_instinct(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    return _split_frontmatter(text)


# ---------- AC2: existence ----------


def test_instinct_file_exists_at_canonical_path(instinct_path: Path) -> None:
    """AC2 names the EXACT path.  If the file is in the wrong directory, the
    instinct loader (scoped to learning/{project-hash}/instincts/*.md per
    rules/_detail/autonomous-intelligence.md) will never see it.
    """
    assert instinct_path.is_file(), (
        f"spec-blind: AC2 violated — instinct file not present at canonical "
        f"path {instinct_path}; instinct loader will never discover this pattern"
    )


# ---------- AC2: frontmatter required fields ----------


def test_frontmatter_declares_id_field(instinct_path: Path) -> None:
    fm, _ = _load_instinct(instinct_path)
    assert "id" in fm, "spec-blind: AC2 violated — frontmatter missing 'id'"
    assert isinstance(fm["id"], str) and fm["id"].strip(), (
        f"spec-blind: AC2 violated — frontmatter 'id' must be a non-empty "
        f"string, got {fm['id']!r}"
    )


def test_frontmatter_confidence_is_numeric_in_unit_interval(instinct_path: Path) -> None:
    """AC2: 'confidence (numeric in [0,1])'.  Confidence outside [0,1] will
    fail the instinct loader's normalize step per autonomous-intelligence
    rules (load-warning reason 'missing-confidence-field' is emitted on
    invalid values too)."""
    fm, _ = _load_instinct(instinct_path)
    assert "confidence" in fm, (
        "spec-blind: AC2 violated — frontmatter missing 'confidence'"
    )
    conf = fm["confidence"]
    assert isinstance(conf, (int, float)) and not isinstance(conf, bool), (
        f"spec-blind: AC2 violated — confidence must be numeric, got "
        f"{type(conf).__name__} ({conf!r})"
    )
    assert 0.0 <= float(conf) <= 1.0, (
        f"spec-blind: AC2 violated — confidence {conf} is outside [0, 1]"
    )


def test_frontmatter_roles_contains_architect_and_infrastructure_engineer(
    instinct_path: Path,
) -> None:
    """AC2: 'roles (non-empty list containing architect AND infrastructure-engineer)'.

    If either role is missing, the instinct never injects into that role's
    spawns — future architects or infra-engineers will re-investigate the
    same dead-end v2.1.139 features.
    """
    fm, _ = _load_instinct(instinct_path)
    assert "roles" in fm, "spec-blind: AC2 violated — frontmatter missing 'roles'"
    roles = fm["roles"]
    assert isinstance(roles, list), (
        f"spec-blind: AC2 violated — roles must be a YAML list, got "
        f"{type(roles).__name__}"
    )
    assert roles, "spec-blind: AC2 violated — roles list is empty"
    role_set = {r for r in roles if isinstance(r, str)}
    missing = {"architect", "infrastructure-engineer"} - role_set
    assert not missing, (
        f"spec-blind: AC2 violated — roles missing required entries: "
        f"{sorted(missing)} (got {sorted(role_set)})"
    )


def test_frontmatter_domain_is_string(instinct_path: Path) -> None:
    fm, _ = _load_instinct(instinct_path)
    assert "domain" in fm, "spec-blind: AC2 violated — frontmatter missing 'domain'"
    assert isinstance(fm["domain"], str) and fm["domain"].strip(), (
        f"spec-blind: AC2 violated — domain must be a non-empty string, "
        f"got {fm['domain']!r}"
    )


def test_frontmatter_scope_is_string(instinct_path: Path) -> None:
    fm, _ = _load_instinct(instinct_path)
    assert "scope" in fm, "spec-blind: AC2 violated — frontmatter missing 'scope'"
    assert isinstance(fm["scope"], str) and fm["scope"].strip(), (
        f"spec-blind: AC2 violated — scope must be a non-empty string, "
        f"got {fm['scope']!r}"
    )


# ---------- AC2: body content ----------


def test_body_contains_pattern_heading(instinct_path: Path) -> None:
    """AC2: 'Body contains a ## Pattern section'."""
    _, body = _load_instinct(instinct_path)
    # Accept the heading anywhere in the body, case-sensitive (Markdown convention).
    assert re.search(r"(?m)^##\s+Pattern\b", body), (
        "spec-blind: AC2 violated — instinct body has no '## Pattern' heading"
    )


def test_body_discusses_continue_on_block_feature(instinct_path: Path) -> None:
    """AC2 names continueOnBlock as one of three v2.1.139 features."""
    _, body = _load_instinct(instinct_path)
    assert "continueOnBlock" in body, (
        "spec-blind: AC2 violated — body must discuss 'continueOnBlock' "
        "(one of three named v2.1.139 features that look like a fit but aren't)"
    )


def test_body_discusses_x_claude_code_agent_id_feature(instinct_path: Path) -> None:
    """AC2 names x-claude-code-agent-id as one of three features."""
    _, body = _load_instinct(instinct_path)
    assert "x-claude-code-agent-id" in body, (
        "spec-blind: AC2 violated — body must discuss 'x-claude-code-agent-id' "
        "(one of three named v2.1.139 features that look like a fit but aren't)"
    )


def test_body_discusses_automode_hard_deny_as_not_a_replacement(instinct_path: Path) -> None:
    """AC2 names autoMode.hard_deny as the third feature, framed as 'additive,
    not a replacement'.  The body must convey that nuance — otherwise a future
    architect could misread the pattern as 'autoMode.hard_deny is the new
    destructive-verb gate' and rip out main-branch-guard.sh.
    """
    _, body = _load_instinct(instinct_path)
    assert "autoMode.hard_deny" in body or "hard_deny" in body, (
        "spec-blind: AC2 violated — body must discuss 'autoMode.hard_deny'"
    )
    # The nuance: additive / belt-and-braces / not a replacement.
    lower = body.lower()
    nuance_markers = [
        "additive",
        "belt-and-braces",
        "belt and braces",
        "never a replacement",
        "not a replacement",
        "at best additive",
    ]
    matched = [m for m in nuance_markers if m in lower]
    assert matched, (
        "spec-blind: AC2 violated — body discusses autoMode.hard_deny but "
        "fails to mark it as additive / belt-and-braces / not-a-replacement.  "
        "Without that nuance, future readers may rip out main-branch-guard.sh."
    )


def test_body_cites_at_least_one_canonical_source(instinct_path: Path) -> None:
    """AC2: 'body cites at least one canonical source' from the named list."""
    _, body = _load_instinct(instinct_path)
    canonical_sources = [
        "thinking-defaults.md",
        "agent-protocol.md",
        "code.claude.com/docs/en/hooks",
        "code.claude.com/docs/en/settings",
    ]
    matched = [src for src in canonical_sources if src in body]
    assert matched, (
        f"spec-blind: AC2 violated — body cites none of the canonical sources "
        f"{canonical_sources}.  Without a canonical citation, the instinct "
        f"is unverifiable hearsay."
    )
