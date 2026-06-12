"""Slice A SSOT — PLAN_FEASIBILITY_REJECTED verdict registration.

AC-A1 through AC-A6 covering:
  - Two emitter rows (light skill + heavy agents) in verdict-catalog.md
  - Downstream branch cells distinguish from CHANGES_REQUESTED
  - Notes bullet defines feasibility_drift forensic shape
  - Notes bullet exempts the heavy-gate agent row from reverse enforcement
  - plan-self-validation frontmatter declares ALL FOUR verdicts (regression guard)
  - Bidirectional consistency audit remains clean after the edits
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"
PLAN_SELF_VALIDATION_SKILL = (
    REPO_ROOT / "skills" / "plan-self-validation" / "SKILL.md"
)
SKILLS_DIR = REPO_ROOT / "skills"

_VERDICT = "PLAN_FEASIBILITY_REJECTED"

_SKILLS_WITHOUT_VERDICT = frozenset({
    "_template",
    "capture", "embedder", "mcp_memory", "recall",
    "skill-builder",
    "react-native-patterns", "web-frontend-patterns",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _catalog_text():
    return CATALOG.read_text()


def _parse_catalog_rows():
    """Return list of dicts: {verdict, polarity, emitter_cell, emitters, phase, branch}."""
    rows = []
    body = _catalog_text()
    pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*([a-z]+)\s*\|"
        r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )
    for m in pattern.finditer(body):
        emitter_cell = m.group(3)
        emitters = [
            e.strip().strip("`")
            for e in emitter_cell.split(",")
            if e.strip().strip("`")
        ]
        rows.append(
            {
                "verdict": m.group(1),
                "polarity": m.group(2),
                "emitter_cell": emitter_cell,
                "emitters": emitters,
                "phase": m.group(4).strip(),
                "branch": m.group(5).strip(),
            }
        )
    return rows


def _feasibility_rows(rows):
    return [r for r in rows if r["verdict"] == _VERDICT]


def _parse_skill_frontmatter_verdicts(skill_path):
    text = skill_path.read_text()
    fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not fm:
        return set()
    for line in fm.group(1).splitlines():
        line = line.strip()
        if line.startswith("verdict:"):
            value = line[len("verdict:"):].strip().strip("\"'")
            return {t.strip() for t in re.split(r"[/|,]", value) if t.strip()}
    return set()


def _normalize_emitter(name):
    """Strip backticks and trailing (agent)/(skill) annotation."""
    name = name.replace("`", "")
    name = re.sub(r"\s*\((?:agent|skill)\)\s*$", "", name)
    return name.strip()


# ---------------------------------------------------------------------------
# AC-A1
# ---------------------------------------------------------------------------

def test_two_emitter_rows_present_light_and_heavy():
    """Catalog has TWO PLAN_FEASIBILITY_REJECTED rows.

    Row 1 (light gate): emitter plan-self-validation, polarity failure,
    phase plan-validation.
    Row 2 (heavy gate): emitter naming both product-reviewer AND
    software-engineer, polarity failure, phase plan-validation.
    """
    rows = _parse_catalog_rows()
    feasibility = _feasibility_rows(rows)

    assert len(feasibility) == 2, (
        f"Expected exactly 2 {_VERDICT} rows, found {len(feasibility)}: "
        f"{[r['emitter_cell'] for r in feasibility]}"
    )

    for row in feasibility:
        assert row["polarity"] == "failure", (
            f"{_VERDICT} row must have polarity=failure, got: {row['polarity']}"
        )
        assert row["phase"] == "plan-validation", (
            f"{_VERDICT} row must have phase=plan-validation, "
            f"got: {row['phase']}"
        )

    light_rows = [
        r for r in feasibility
        if "plan-self-validation" in r["emitter_cell"]
    ]
    assert len(light_rows) == 1, (
        f"Expected exactly 1 light-gate row (emitter plan-self-validation), "
        f"found {len(light_rows)}"
    )

    heavy_rows = [
        r for r in feasibility
        if "product-reviewer" in r["emitter_cell"]
        and "software-engineer" in r["emitter_cell"]
    ]
    assert len(heavy_rows) == 1, (
        f"Expected exactly 1 heavy-gate row naming both product-reviewer and "
        f"software-engineer, found {len(heavy_rows)}"
    )


# ---------------------------------------------------------------------------
# AC-A2
# ---------------------------------------------------------------------------

def test_downstream_branch_differentiates_from_changes_requested():
    """Both rows' branch cells surface to user + write feasibility_drift.

    They must NOT describe silent architect re-work (the CHANGES_REQUESTED
    path).
    """
    rows = _parse_catalog_rows()
    feasibility = _feasibility_rows(rows)

    assert feasibility, f"No {_VERDICT} rows found in catalog"

    for row in feasibility:
        branch = row["branch"].lower()
        assert "feasibility_drift" in branch, (
            f"{_VERDICT} branch must mention feasibility_drift; "
            f"got: {row['branch']}"
        )
        assert "user" in branch or "surface" in branch or "surfaces" in branch, (
            f"{_VERDICT} branch must indicate user-surfacing (contains 'user' "
            f"or 'surface'); got: {row['branch']}"
        )
        # WHY: "silent re-work" is CHANGES_REQUESTED territory; PLAN_FEASIBILITY_REJECTED
        # must say it does NOT trigger silent re-work (the phrase is allowed in context
        # of explicitly negating that path, e.g. "does NOT trigger silent architect re-work").
        # We check the row does not assert IT TRIGGERS silent re-work (trigger present
        # without a preceding NOT/does not).
        silent_trigger = re.search(
            r"\btriggers?\s+silent\b|\bsilent\s+architect\s+re.?work\b(?!.*\bnot\b)",
            branch,
        )
        assert not silent_trigger or "not trigger" in branch or "does not" in branch, (
            f"{_VERDICT} branch must NOT describe triggering silent re-work "
            f"(CHANGES_REQUESTED territory); got: {row['branch']}"
        )


# ---------------------------------------------------------------------------
# AC-A3
# ---------------------------------------------------------------------------

def test_feasibility_drift_notes_present_with_overturned_false_on_agree():
    """A Notes bullet defines the feasibility_drift forensic shape.

    Must name: architect_said, reviewers_concluded, overturned,
    observations.jsonl, AND state present-with-overturned:false when the
    pass ran and both agreed FEASIBLE; absent only when no pass ran.
    """
    text = _catalog_text()

    assert "feasibility_drift" in text, (
        "protocols/verdict-catalog.md Notes must mention feasibility_drift"
    )

    notes_section = text[text.find("## Notes"):]
    assert "architect_said" in notes_section, (
        "feasibility_drift Notes bullet must name the 'architect_said' field"
    )
    assert "reviewers_concluded" in notes_section, (
        "feasibility_drift Notes bullet must name the 'reviewers_concluded' field"
    )
    assert "overturned" in notes_section, (
        "feasibility_drift Notes bullet must name the 'overturned' field"
    )
    assert "observations.jsonl" in notes_section, (
        "feasibility_drift Notes bullet must reference observations.jsonl"
    )
    assert (
        "overturned:false" in notes_section
        or "overturned: false" in notes_section
    ), (
        "feasibility_drift Notes bullet must state present-with-overturned:false "
        "when pass ran and both agreed FEASIBLE"
    )
    notes_lower = notes_section.lower()
    assert "absent" in notes_lower, (
        "feasibility_drift Notes bullet must document the absent-when-no-pass-ran rule"
    )


# ---------------------------------------------------------------------------
# AC-A4
# ---------------------------------------------------------------------------

def test_heavy_gate_row_reverse_audit_exempt_in_notes():
    """A Notes bullet exempts the heavy-gate agent row from reverse enforcement.

    Must cite the RECON_COMPLETE / ORCHESTRATOR_APPLY_REQUIRED / VISUAL_DIFF_*
    pattern.
    """
    text = _catalog_text()
    notes_section = text[text.find("## Notes"):]

    assert _VERDICT in notes_section, (
        f"Notes must have a bullet mentioning {_VERDICT} for the exemption"
    )

    feasibility_note_region = ""
    for bullet in notes_section.split("- "):
        if _VERDICT in bullet:
            feasibility_note_region = bullet
            break

    assert feasibility_note_region, (
        f"Could not find a Notes bullet containing {_VERDICT}"
    )

    assert "agent" in feasibility_note_region.lower(), (
        "Notes exemption bullet must say the heavy-gate row is agent-emitted"
    )
    assert (
        "RECON_COMPLETE" in feasibility_note_region
        or "ORCHESTRATOR_APPLY_REQUIRED" in feasibility_note_region
        or "VISUAL_DIFF" in feasibility_note_region
    ), (
        "Notes exemption bullet must cite the RECON_COMPLETE / "
        "ORCHESTRATOR_APPLY_REQUIRED / VISUAL_DIFF_* exemption pattern"
    )
    assert (
        "exempt" in feasibility_note_region.lower()
        or "skip" in feasibility_note_region.lower()
    ), (
        "Notes exemption bullet must state reverse-direction enforcement is "
        "skipped or the row is exempt"
    )


# ---------------------------------------------------------------------------
# AC-A5
# ---------------------------------------------------------------------------

def test_plan_self_validation_frontmatter_declares_all_verdicts():
    """plan-self-validation/SKILL.md frontmatter has a verdict: field with all four verdicts.

    Regression guard: PLAN_APPROVED, PLAN_HOLES, ROUTING_UPSHIFTED (the three
    pre-existing verdicts) MUST still be declared alongside the new
    PLAN_FEASIBILITY_REJECTED. Creating the field with only the new verdict
    would clobber them from the forward audit check.
    """
    verdicts = _parse_skill_frontmatter_verdicts(PLAN_SELF_VALIDATION_SKILL)

    assert verdicts, (
        "skills/plan-self-validation/SKILL.md must have a verdict: frontmatter "
        "field — it currently has none, which was previously audit-exempt; "
        "this field must be CREATED as part of slice-a"
    )

    required = {
        "PLAN_APPROVED",
        "PLAN_HOLES",
        "ROUTING_UPSHIFTED",
        "PLAN_FEASIBILITY_REJECTED",
    }
    missing = required - verdicts
    assert not missing, (
        f"plan-self-validation verdict: field is missing required verdicts: "
        f"{missing}. Currently declared: {verdicts}. All four must be present."
    )


# ---------------------------------------------------------------------------
# AC-A6
# ---------------------------------------------------------------------------

def test_verdict_consistency_audit_bidirectional_clean():
    """Bidirectional catalog <-> frontmatter consistency is clean.

    Forward: every verdict declared in plan-self-validation frontmatter
    appears in the catalog.
    Reverse (plan-self-validation rows): every catalog row whose emitter is
    plan-self-validation is declared in the frontmatter. The heavy-gate
    agent row (emitter names agents) is reverse-audit exempt, but each
    individual agent token must resolve to a known agent file.
    """
    rows = _parse_catalog_rows()
    catalog_verdicts = {r["verdict"] for r in rows}

    declared = _parse_skill_frontmatter_verdicts(PLAN_SELF_VALIDATION_SKILL)
    assert declared, (
        "plan-self-validation must have a verdict: frontmatter field for the "
        "forward check to be meaningful"
    )

    forward_drift = declared - catalog_verdicts
    assert not forward_drift, (
        f"plan-self-validation declares verdicts not in catalog: {forward_drift}"
    )

    skill_rows = [
        r for r in rows
        if r["verdict"] == _VERDICT
        and "plan-self-validation" in r["emitter_cell"]
    ]
    for row in skill_rows:
        assert row["verdict"] in declared, (
            f"Catalog row {row['verdict']} (emitter plan-self-validation) is "
            f"not declared in the skill frontmatter. Declared: {declared}"
        )

    heavy_rows = [
        r for r in rows
        if r["verdict"] == _VERDICT
        and "product-reviewer" in r["emitter_cell"]
    ]
    assert heavy_rows, (
        f"Expected at least one heavy-gate {_VERDICT} row naming product-reviewer"
    )

    agents_dir = REPO_ROOT / "agents"
    known_agents = {p.stem for p in agents_dir.glob("*.md")}
    for row in heavy_rows:
        for emitter_token in row["emitters"]:
            normalized = _normalize_emitter(emitter_token)
            skill_exists = (
                (SKILLS_DIR / normalized / "SKILL.md").exists()
                or (SKILLS_DIR / "_deferred" / normalized / "SKILL.md").exists()
            )
            agent_exists = normalized in known_agents
            assert skill_exists or agent_exists, (
                f"Heavy-gate row emitter '{normalized}' does not resolve to a "
                f"known skill or agent. Known agents include: "
                f"{sorted(known_agents)[:5]}..."
            )
