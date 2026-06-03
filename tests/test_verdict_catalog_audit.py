"""C3 — Local catalog consistency reimplementation (AC29, M1).

Mirrors `tests/test_verdict_catalog_tools_valid.py`: parses the verdict catalog
table directly and asserts forward + reverse consistency. Runs locally against
file-system state — no shell-out, no `/harness-audit` invocation. Closes
H2/PR-Finding-1 by giving Tier 4 multi-target invariants a deterministic
catalog gate.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"
SKILLS_DIR = REPO_ROOT / "skills"

# Skills that legitimately do NOT emit a verdict (utility/pattern files).
# Aligned with `protocols/verdict-catalog.md > Notes` (capture, embedder, etc.)
SKILLS_WITHOUT_VERDICT = frozenset({
    "_template",
    "capture", "embedder", "mcp_memory", "recall",
    "skill-builder",
    "react-native-patterns", "web-frontend-patterns",
})

VALID_POLARITIES = frozenset({"success", "failure", "info"})


def _parse_catalog_rows():
    """Return list of dicts: {verdict, polarity, emitters (list), phase, branch}.

    Rows with multiple emitters use a comma-separated list of backtick-quoted
    skill names (e.g. `` `harness-audit`, `health-scan` ``). We capture the
    raw emitter cell and split on commas, stripping backticks per token.
    """
    rows = []
    body = CATALOG.read_text()
    # Capture: verdict | polarity | emitter-cell | phase | branch
    pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*([a-z]+)\s*\|"
        r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE)
    for m in pattern.finditer(body):
        emitter_cell = m.group(3)
        emitters = [e.strip().strip("`")
                    for e in emitter_cell.split(",")
                    if e.strip().strip("`")]
        rows.append({
            "verdict": m.group(1),
            "polarity": m.group(2),
            "emitters": emitters,
            "phase": m.group(4).strip(),
            "branch": m.group(5).strip(),
        })
    return rows


def _skill_verdicts(skill_path):
    """Extract verdicts a skill claims to emit.

    Looks at frontmatter `verdict:` and body `Verdict: X / Y / ...` lines.
    """
    text = skill_path.read_text()
    verdicts = set()
    # Frontmatter `verdict:` field.
    fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if fm:
        for line in fm.group(1).splitlines():
            line = line.strip()
            if line.startswith("verdict:"):
                value = line[len("verdict:"):].strip().strip('"\'')
                # Split "FOO / BAR" or "FOO|BAR".
                for token in re.split(r"[/|,]", value):
                    token = token.strip()
                    if token:
                        verdicts.add(token)
    # Body `Verdict: X / Y` lines.
    for m in re.finditer(r"^Verdict:\s*(.+)$", text, re.MULTILINE):
        for token in re.split(r"[/|,]", m.group(1).strip()):
            token = token.strip().strip("`")
            # Filter out template placeholder values like
            # "VERDICT" or generic shapes.
            if token and re.fullmatch(r"[A-Z_]+", token):
                verdicts.add(token)
    return verdicts


def _all_skill_files():
    files = []
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name in SKILLS_WITHOUT_VERDICT:
            continue
        if skill_dir.name == "_deferred":
            for sub in skill_dir.iterdir():
                if sub.is_dir():
                    skill_md = sub / "SKILL.md"
                    if skill_md.exists():
                        files.append((sub.name, skill_md))
            continue
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            files.append((skill_dir.name, skill_md))
    return files


def test_catalog_polarities_are_valid():
    """Every catalog row has a polarity in {success, failure, info}."""
    rows = _parse_catalog_rows()
    assert rows, "Catalog parser found no rows — parser/catalog drift"
    bad = [r for r in rows if r["polarity"] not in VALID_POLARITIES]
    assert not bad, f"Invalid polarity values: {bad}"


def test_forward_skill_verdicts_appear_in_catalog():
    """Forward: every verdict a skill claims to emit MUST be in the catalog."""
    rows = _parse_catalog_rows()
    catalog_verdicts = {r["verdict"] for r in rows}
    drift = []
    for skill_name, skill_path in _all_skill_files():
        for v in _skill_verdicts(skill_path):
            if v not in catalog_verdicts:
                drift.append((skill_name, v))
    assert not drift, (
        f"Skills emit verdicts not in `protocols/verdict-catalog.md`: {drift}")


def _emitter_resolves(name, known_agents):
    candidates = (
        SKILLS_DIR / name / "SKILL.md",
        SKILLS_DIR / "_deferred" / name / "SKILL.md",
    )
    if any(p.exists() for p in candidates):
        return True
    return name in known_agents


def test_reverse_catalog_emitters_resolve_to_real_skills():
    """Reverse: every catalog row's emitter MUST resolve to a real skill or known agent.

    Agent-emitted verdicts (e.g. `ORCHESTRATOR_APPLY_REQUIRED` from
    `fix-engineer`) are exempted from the resolves-to-skill check —
    they live in agent definitions, not skill files.
    """
    rows = _parse_catalog_rows()
    agents_dir = REPO_ROOT / "agents"
    known_agents = {p.stem for p in agents_dir.glob("*.md")}
    drift = []
    for row in rows:
        if not row["emitters"]:
            drift.append((row["verdict"], "<no emitters>"))
            continue
        unresolved = [e for e in row["emitters"]
                      if not _emitter_resolves(e, known_agents)]
        if unresolved:
            drift.append((row["verdict"], unresolved))
    assert not drift, (
        f"Catalog rows whose emitter does not resolve to a skill or agent: "
        f"{drift}")
