#!/usr/bin/env python3
"""Verdict-consistency helper invoked by verdict-consistency-check.sh.

Imports the canonical helpers from ``tests/test_verdict_catalog_audit`` so
the callable and the existing pytest audit agree byte-for-byte on what
counts as a verdict declaration AND on what counts as a resolved emitter
("directory exists" is sufficient — see canonical ``_emitter_resolves``).

Single-purpose interface: argv[1] is the config root (the ``CLAUDE_CONFIG_DIR``
the bash entry resolved); on bidirectional agreement print nothing and exit 0;
on first drift print one ``missing-in-{catalog,skill}: <verdict>`` line and
exit 1.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Some catalog rows qualify the emitter with a parenthetical role tag, e.g.
# `` `architect-context-recon` (agent) ``. The canonical parser splits on
# commas and strips outer backticks only, leaving the inner backtick + "
# (agent)" tail attached. Reduce each emitter token to its first
# backtick-delimited identifier so resolution matches what the catalog row
# *means* (the bare name) rather than its decorated form.
_FIRST_TOKEN = re.compile(r"[A-Za-z0-9_./-]+")


def _import_canonical(config_dir: Path):
    """Import canonical audit helpers, rebound to ``config_dir``.

    The canonical module is co-located with this helper (same repo); we
    locate it via this file's ``parents[2]/tests`` and fall back to
    ``config_dir/tests`` so a freestanding ``CLAUDE_CONFIG_DIR`` that ships
    its own copy still works. Canonical pins ``CATALOG``/``SKILLS_DIR`` at
    import time; we rebind both to honour the caller-supplied ``config_dir``.
    """
    here_tests = Path(__file__).resolve().parents[2] / "tests"
    fallback_tests = config_dir / "tests"
    for candidate in (here_tests, fallback_tests):
        if (candidate / "test_verdict_catalog_audit.py").is_file():
            sys.path.insert(0, str(candidate))
            break
    import test_verdict_catalog_audit as canonical
    canonical.CATALOG = config_dir / "rules" / "verdict-catalog.md"
    canonical.SKILLS_DIR = config_dir / "skills"
    return canonical


def _declared_verdicts(canonical) -> dict[str, list[str]]:
    """Return {verdict: [skill_name, ...]} for every skill that declares it."""
    declared: dict[str, list[str]] = {}
    for skill_name, skill_path in canonical._all_skill_files():
        for verdict in canonical._skill_verdicts(skill_path):
            declared.setdefault(verdict, []).append(skill_name)
    return declared


def _bare_name(token: str) -> str:
    """Reduce a catalog emitter token to its bare identifier (strip decoration)."""
    match = _FIRST_TOKEN.search(token)
    return match.group(0) if match else token


def check(config_dir: Path) -> tuple[int, str]:
    """Return (exit_code, diagnostic). exit_code==0 means no diagnostic."""
    canonical = _import_canonical(config_dir)
    rows = canonical._parse_catalog_rows()
    catalog_verdicts = {row["verdict"] for row in rows}
    declared = _declared_verdicts(canonical)
    for verdict in sorted(declared):
        if verdict not in catalog_verdicts:
            return 1, f"missing-in-catalog: {verdict}"
    agents_dir = config_dir / "agents"
    known_agents = {p.stem for p in agents_dir.glob("*.md")} if agents_dir.is_dir() else set()
    for row in rows:
        if not row["emitters"]:
            return 1, f"missing-in-skill: {row['verdict']}"
        if not any(canonical._emitter_resolves(_bare_name(e), known_agents) for e in row["emitters"]):
            return 1, f"missing-in-skill: {row['verdict']}"
    return 0, ""


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("error: usage verdict_consistency.py <config-dir>")
        return 1
    exit_code, diagnostic = check(Path(argv[1]))
    if diagnostic:
        print(diagnostic)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
