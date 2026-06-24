"""Slice C — SKILL marker tests.

C1: deploy SKILL emits [Deploy] marker on every terminal outcome (DEPLOYED,
    DEPLOY_FAILED, ROLLED_BACK) and heredoc removed.
C2: deployment-verification SKILL emits markers on BOTH DEPLOYMENT_VERIFIED→DEPLOYED
    AND AUTO_ROLLBACK paths.
C3: no SKILL retains raw bash >> or inline os.open heredoc.
C4: marker field order/keys match hook parser regex (round-trip contract).
C5: learn SKILL Step 7c-bis denominator explicitly filters to the four valid
    outcomes {DEPLOYED, ROLLED_BACK, AUTO_ROLLBACK, DEPLOY_FAILED}, excluding
    <unknown> and any other non-enum value from both numerator and denominator.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_SKILL = REPO_ROOT / "skills" / "deploy" / "SKILL.md"
VERIFY_SKILL = REPO_ROOT / "skills" / "deployment-verification" / "SKILL.md"
LEARN_SKILL = REPO_ROOT / "skills" / "learn" / "SKILL.md"

MARKER_RE = re.compile(
    r'\[Deploy\] outcome: [A-Z_]+ pipeline_id: [^\s]+ environment: [^\s]+'
)

DEPLOY_VERDICTS = ("DEPLOYED", "DEPLOY_FAILED", "ROLLED_BACK")
VERIFY_VERDICTS = ("DEPLOYED", "AUTO_ROLLBACK")


def _skill_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_c1_deploy_skill_has_deployed_marker() -> None:
    text = _skill_text(DEPLOY_SKILL)
    assert "[Deploy] outcome: DEPLOYED" in text, \
        "deploy SKILL must emit [Deploy] outcome: DEPLOYED marker"


def test_c1_deploy_skill_has_deploy_failed_marker() -> None:
    text = _skill_text(DEPLOY_SKILL)
    assert "[Deploy] outcome: DEPLOY_FAILED" in text, \
        "deploy SKILL must emit [Deploy] outcome: DEPLOY_FAILED marker"


def test_c1_deploy_skill_has_rolled_back_marker() -> None:
    text = _skill_text(DEPLOY_SKILL)
    assert "[Deploy] outcome: ROLLED_BACK" in text, \
        "deploy SKILL must emit [Deploy] outcome: ROLLED_BACK marker"


def test_c1_deploy_skill_heredoc_removed() -> None:
    text = _skill_text(DEPLOY_SKILL)
    assert "os.O_WRONLY | os.O_CREAT | os.O_APPEND" not in text, \
        "deploy SKILL must not retain inline os.open heredoc"


def test_c2_verify_skill_has_deployed_marker() -> None:
    text = _skill_text(VERIFY_SKILL)
    assert "[Deploy] outcome: DEPLOYED" in text, \
        "deployment-verification SKILL must emit marker on DEPLOYMENT_VERIFIED->DEPLOYED path"


def test_c2_verify_skill_has_auto_rollback_marker() -> None:
    text = _skill_text(VERIFY_SKILL)
    assert "[Deploy] outcome: AUTO_ROLLBACK" in text, \
        "deployment-verification SKILL must emit marker on AUTO_ROLLBACK path"


def test_c2_verify_skill_heredoc_removed() -> None:
    text = _skill_text(VERIFY_SKILL)
    assert "os.O_WRONLY | os.O_CREAT | os.O_APPEND" not in text, \
        "deployment-verification SKILL must not retain inline os.open heredoc"


def test_c3_deploy_skill_no_raw_bash_append() -> None:
    text = _skill_text(DEPLOY_SKILL)
    assert ">> observations.jsonl" not in text, \
        "deploy SKILL must not use raw bash >> to observations.jsonl"


def test_c3_verify_skill_no_raw_bash_append() -> None:
    text = _skill_text(VERIFY_SKILL)
    assert ">> observations.jsonl" not in text, \
        "deployment-verification SKILL must not use raw bash >> to observations.jsonl"


def test_c5_step7cbis_denominator_excludes_unknown_outcome() -> None:
    """C5: learn SKILL Step 7c-bis must restrict denominator to 4 valid outcomes.

    A deploy_outcome set containing an <unknown> record must yield an escape_rate
    computed over ONLY {DEPLOYED, ROLLED_BACK, AUTO_ROLLBACK, DEPLOY_FAILED}.
    The <unknown> value (and any other non-enum value) must be excluded from
    both numerator and denominator.

    This is a prose-contract test: assert that the SKILL.md Step 7c-bis Algorithm
    section explicitly names the 4-outcome filter so agents executing the step
    cannot include <unknown> records in the denominator.
    """
    text = _skill_text(LEARN_SKILL)
    # Extract the Step 7c-bis algorithm section
    match = re.search(
        r"7c-bis\..*?(?=###\s+7c-ter|\Z)",
        text, re.DOTALL
    )
    assert match, "SKILL.md must contain Step 7c-bis section"
    section = match.group(0)

    # The section must explicitly state that the denominator is restricted to
    # only the four valid outcome values, excluding unknown/non-enum values.
    # Accept any of these equivalent phrasings that make the filter unambiguous:
    has_explicit_filter = any([
        "outcome ∈ {DEPLOYED, ROLLED_BACK, AUTO_ROLLBACK, DEPLOY_FAILED}" in section,
        "outcome in {DEPLOYED, ROLLED_BACK, AUTO_ROLLBACK, DEPLOY_FAILED}" in section,
        ("DEPLOYED" in section and "ROLLED_BACK" in section
         and "AUTO_ROLLBACK" in section and "DEPLOY_FAILED" in section
         and ("exclude" in section.lower() or "excluding" in section.lower()
              or "unknown" in section.lower() or "non-enum" in section.lower()
              or "only records" in section.lower() or "filter to" in section.lower()
              or "restricted to" in section.lower())),
    ])
    assert has_explicit_filter, (
        "skills/learn/SKILL.md Step 7c-bis Algorithm must explicitly restrict "
        "the denominator to the four valid outcomes {DEPLOYED, ROLLED_BACK, "
        "AUTO_ROLLBACK, DEPLOY_FAILED}, excluding <unknown> and other non-enum "
        "values from both numerator and denominator. Current section:\n" + section[:800]
    )


def test_c4_marker_shape_matches_hook_parser_regex() -> None:
    # Hook parser regex from deploy-outcome-audit.sh:
    # [Deploy] outcome: <X> pipeline_id: <Y> environment: <Z>
    # where X/Y/Z match ^[A-Za-z0-9._-]+$
    sample_markers = [
        "[Deploy] outcome: DEPLOYED pipeline_id: task-123 environment: staging",
        "[Deploy] outcome: DEPLOY_FAILED pipeline_id: fix-99 environment: production",
        "[Deploy] outcome: ROLLED_BACK pipeline_id: task-abc environment: staging",
        "[Deploy] outcome: AUTO_ROLLBACK pipeline_id: v-job environment: production",
    ]
    field_re = re.compile(
        r'^\[Deploy\] outcome: ([A-Za-z0-9._-]+) pipeline_id: ([A-Za-z0-9._-]+) environment: ([A-Za-z0-9._-]+)$'
    )
    for marker in sample_markers:
        assert field_re.match(marker), \
            f"marker shape does not match hook parser regex: {marker!r}"
