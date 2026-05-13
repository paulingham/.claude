#!/usr/bin/env python3
"""Verdict-consistency helper invoked by verdict-consistency-check.sh.

Reuses the catalog/skill parsing rules from the canonical test module
``tests/test_verdict_catalog_audit.py`` so the callable and the existing
audit test agree byte-for-byte on what counts as a verdict declaration.
The harness-audit SKILL describes the procedure; this helper IS the
executable instance the callable delegates to.

Single-purpose interface: argv[1] is the config root (the ``CLAUDE_CONFIG_DIR``
the bash entry resolved); on bidirectional agreement print nothing and exit 0;
on first drift print one ``missing-in-{catalog,skill}: <verdict>`` line and exit 1.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKILLS_WITHOUT_VERDICT = frozenset({
    "_template",
    "capture", "embedder", "mcp_memory", "recall",
    "skill-builder",
    "react-native-patterns", "web-frontend-patterns",
})

CATALOG_ROW = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*([a-z]+)\s*\|"
    r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$",
    re.MULTILINE,
)
FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
VERDICT_LINE = re.compile(r"^Verdict:\s*(.+)$", re.MULTILINE)
TOKEN_RE = re.compile(r"[A-Z_]+")


def parse_catalog(catalog_path: Path) -> dict[str, list[str]]:
    """Return {verdict: [emitter, ...]} for every row the catalog declares."""
    out: dict[str, list[str]] = {}
    if not catalog_path.exists():
        return out
    for match in CATALOG_ROW.finditer(catalog_path.read_text()):
        verdict = match.group(1)
        emitters = [
            token.strip().strip("`")
            for token in match.group(3).split(",")
            if token.strip().strip("`")
        ]
        out.setdefault(verdict, []).extend(emitters)
    return out


def skill_verdicts(skill_path: Path) -> set[str]:
    """Return the verdict tokens a skill claims to emit (frontmatter + body)."""
    text = skill_path.read_text()
    return _frontmatter_verdicts(text) | _body_verdicts(text)


def _frontmatter_verdicts(text: str) -> set[str]:
    """Extract verdict tokens declared in the YAML frontmatter `verdict:` field."""
    fm = FRONTMATTER.match(text)
    if not fm:
        return set()
    verdicts: set[str] = set()
    for line in fm.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("verdict:"):
            value = stripped[len("verdict:"):].strip().strip('"\'')
            verdicts.update(_split_verdict_value(value))
    return verdicts


def _body_verdicts(text: str) -> set[str]:
    """Extract verdict tokens declared in body `Verdict: X / Y` lines."""
    verdicts: set[str] = set()
    for body in VERDICT_LINE.finditer(text):
        for token in re.split(r"[/|,]", body.group(1).strip()):
            cleaned = token.strip().strip("`")
            if cleaned and TOKEN_RE.fullmatch(cleaned):
                verdicts.add(cleaned)
    return verdicts


def _split_verdict_value(value: str) -> set[str]:
    """Split a `verdict:` cell value (e.g. `FOO / BAR | BAZ`) into a token set."""
    return {
        token.strip()
        for token in re.split(r"[/|,]", value)
        if token.strip()
    }


def iter_skill_files(skills_root: Path):
    """Yield (skill_name, SKILL.md path) tuples for every emitter-eligible skill."""
    if not skills_root.is_dir():
        return
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name in SKILLS_WITHOUT_VERDICT:
            continue
        if skill_dir.name == "_deferred":
            for sub in sorted(skill_dir.iterdir()):
                if sub.is_dir() and (sub / "SKILL.md").exists():
                    yield sub.name, sub / "SKILL.md"
            continue
        if (skill_dir / "SKILL.md").exists():
            yield skill_dir.name, skill_dir / "SKILL.md"


def known_agents(agents_root: Path) -> set[str]:
    """Return stems of every agents/*.md file the agent-emitter rule allows."""
    return {path.stem for path in agents_root.glob("*.md")} if agents_root.is_dir() else set()


def check(config_dir: Path) -> tuple[int, str]:
    """Return (exit_code, diagnostic). exit_code==0 means no diagnostic."""
    catalog = parse_catalog(config_dir / "rules" / "verdict-catalog.md")
    skills_root = config_dir / "skills"
    agents_root = config_dir / "agents"
    declared: dict[str, list[str]] = {}
    for skill_name, skill_path in iter_skill_files(skills_root):
        for verdict in skill_verdicts(skill_path):
            declared.setdefault(verdict, []).append(skill_name)
    for verdict in sorted(declared):
        if verdict not in catalog:
            return 1, f"missing-in-catalog: {verdict}"
    agents = known_agents(agents_root)
    for verdict, emitters in sorted(catalog.items()):
        if not _verdict_has_real_emitter(verdict, emitters, declared, agents):
            return 1, f"missing-in-skill: {verdict}"
    return 0, ""


def _verdict_has_real_emitter(
    verdict: str,
    emitters: list[str],
    declared: dict[str, list[str]],
    agents: set[str],
) -> bool:
    """True when at least one named emitter actually emits this verdict.

    A skill-emitter must declare the verdict in its frontmatter or body. Agent
    emitters (e.g. `fix-engineer` emitting ORCHESTRATOR_APPLY_REQUIRED) are
    exempted from the frontmatter check — they emit through structured stdout,
    not a SKILL.md verdict enum — and only need to resolve to a known agent.
    """
    skills_that_declare = set(declared.get(verdict, []))
    for emitter in emitters:
        if emitter in skills_that_declare:
            return True
        if emitter in agents:
            return True
    return False


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("missing-in-catalog: <usage: verdict_consistency.py <config-dir>>")
        return 1
    exit_code, diagnostic = check(Path(argv[1]))
    if diagnostic:
        print(diagnostic)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
