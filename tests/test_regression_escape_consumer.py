"""AC3: /harness:learn Step 7c-bis computes project-level escape_rate and Step 9 renders it.

Verifies:
- skills/learn/SKILL.md documents a project-level Step 7c-bis section computing
  escape_rate = count(ROLLED_BACK|AUTO_ROLLBACK) / count(deploy_outcome records),
  joined by pipeline_id, NOT grouped by (role, task-class).
- The Step 7c per-group output-dict key list does NOT contain escape_rate
  (regression guard: escape_rate is project-level, not per-group).
- The Step 9 Report block renders a revert/escape-rate line with the
  '(n of m deployed pipelines)' raw-count form.
- No threshold or ceiling appears within the Step 7c-bis sub-section body
  (windowed grep to avoid false-RED from existing Step 7c thresholds).
- Step 7c-bis documents skip-on-empty for the Step 9 Deployment Reliability
  line specifically, and that the Step 7c cost-quality correlation is NOT
  skipped by absent deploy_outcome records.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEARN = REPO_ROOT / "skills" / "learn" / "SKILL.md"


def _step7c_bis_body() -> str:
    """Return the body of the ### 7c-bis section up to the next ### or ##."""
    text = LEARN.read_text()
    match = re.search(
        r"###\s+7c-bis\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


def _step7c_body() -> str:
    """Return the body of the ### 7c section up to the next ### or ##."""
    text = LEARN.read_text()
    match = re.search(
        r"###\s+7c\b[^#\n]*\n(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


def _step9_body() -> str:
    """Return the body of the ### 9. Report section up to the next ### or ##."""
    text = LEARN.read_text()
    match = re.search(
        r"###\s+9\.\s+Report\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


class LearnStep7cBisDocumentsEscapeRate(unittest.TestCase):
    def test_learn_step7c_bis_documents_escape_rate_formula(self):
        body = _step7c_bis_body()
        self.assertTrue(
            body,
            "skills/learn/SKILL.md must have a ### 7c-bis section documenting "
            "project-level deployment reliability")
        self.assertIn("escape_rate", body,
                      "Step 7c-bis must document the escape_rate field")
        self.assertRegex(
            body,
            r"ROLLED_BACK.*AUTO_ROLLBACK|AUTO_ROLLBACK.*ROLLED_BACK",
            msg="Step 7c-bis formula must reference both ROLLED_BACK and AUTO_ROLLBACK",
        )
        self.assertIn("pipeline_id", body,
                      "Step 7c-bis must document joining by pipeline_id")
        self.assertRegex(
            body,
            r"(?:project.level|not per.group|not grouped)",
            msg="Step 7c-bis must document that escape_rate is project-level, not per-group",
        )

    def test_escape_rate_is_project_level_not_in_step7c_group_dict(self):
        body = _step7c_body()
        self.assertTrue(body, "### 7c section not found in skills/learn/SKILL.md")
        # The output dict keys in Step 7c must not include escape_rate
        match = re.search(
            r"keys?\s*[`'\"]?\{([^}]+)\}",
            body)
        if match:
            keys_text = match.group(1)
            self.assertNotIn(
                "escape_rate", keys_text,
                "escape_rate must NOT appear in the Step 7c per-group output-dict key list "
                "(it is a project-level metric in Step 7c-bis, not a per-group key)",
            )
        # Also check the per-group aggregate table does not list escape_rate as a row
        self.assertNotRegex(
            body,
            r"\|\s*escape_rate\s*\|",
            msg="escape_rate must not be a row in the Step 7c per-group aggregate table",
        )

    def test_step9_report_renders_escape_rate_line(self):
        body = _step9_body()
        self.assertTrue(body, "### 9. Report section not found in skills/learn/SKILL.md")
        self.assertIn("escape rate", body.lower(),
                      "Step 9 Report must render a revert/escape-rate line")
        self.assertRegex(
            body,
            r"of\s+\d*[nm]\s+deployed pipelines|of\s+\{n[^}]*\}\s+deployed pipelines"
            r"|n_reverts.*n_deploys|n_deploy|deployed pipelines",
            msg="Step 9 escape rate line must include the raw count '(n of m deployed pipelines)' form",
        )

    def test_step9_empty_state_copy_and_scope_label(self):
        """Pins the empty-state template and scope label in Step 9 Report (mutant M5)."""
        body = _step9_body()
        self.assertTrue(body, "### 9. Report section not found in skills/learn/SKILL.md")
        self.assertIn(
            "not yet measured",
            body,
            "Step 9 Report must document the empty-state fallback copy "
            "'not yet measured' for when no deploy_outcome records exist",
        )
        self.assertIn(
            "deploy-phase rollbacks",
            body,
            "Step 9 Report must document the scope label 'deploy-phase rollbacks' "
            "in the Deployment Reliability section heading",
        )

    def test_deploy_failed_excluded_from_numerator(self):
        """Pins the DEPLOY_FAILED denominator-only rule in 7c-bis (mutant M1)."""
        body = _step7c_bis_body()
        self.assertTrue(body, "### 7c-bis section not found in skills/learn/SKILL.md")
        self.assertIn(
            "DEPLOY_FAILED",
            body,
            "Step 7c-bis must mention DEPLOY_FAILED to document its denominator role",
        )
        self.assertRegex(
            body,
            r"DEPLOY_FAILED.{0,120}NOT the numerator|NOT the numerator.{0,120}DEPLOY_FAILED",
            msg="Step 7c-bis must document that DEPLOY_FAILED counts in the denominator "
                "but NOT the numerator (deploy attempted, never shipped — no regression escape)",
        )

    def test_no_threshold_or_ceiling_in_escape_rate(self):
        body = _step7c_bis_body()
        self.assertTrue(
            body,
            "### 7c-bis section not found — cannot verify absence of threshold/ceiling")
        # Numeric comparison operators with a value
        self.assertNotRegex(
            body,
            r">=\s*\d+\.?\d*|<=\s*\d+\.?\d*",
            msg="Step 7c-bis must NOT contain >= or <= numeric thresholds or ceilings",
        )
        # Percentage target
        self.assertNotRegex(
            body,
            r"\d+\s*%",
            msg="Step 7c-bis must NOT contain percentage targets (no hard-coded ceiling)",
        )
        # Enforcing verbs without advisory qualifier
        enforcing = re.compile(
            r"\b(blocks|prevents|rejects|enforces|denies)\b", re.IGNORECASE
        )
        advisory = re.compile(
            r"\b(advisory|optional|telemetry|log.?only|capture|signal)\b", re.IGNORECASE
        )
        for m in enforcing.finditer(body):
            start = max(0, m.start() - 100)
            end = min(len(body), m.end() + 100)
            context = body[start:end]
            self.assertTrue(
                advisory.search(context),
                f"Step 7c-bis contains enforcing verb '{m.group()}' without advisory qualifier "
                f"in context: {context!r}",
            )

    def test_escape_rate_tolerates_zero_deploy_outcomes(self):
        body = _step7c_bis_body()
        self.assertTrue(body, "### 7c-bis section not found")
        # Must document skip-on-empty for Step 9 Deployment Reliability line
        self.assertRegex(
            body,
            r"skip|empty|zero|no\s+deploy",
            msg="Step 7c-bis must document skip-on-empty behaviour (no raise on zero records)",
        )
        # Must document that Step 7c cost-quality correlation is NOT affected
        self.assertRegex(
            body,
            r"(?:step\s+7c|cost.quality|7c\s+per.group)[^.]*(?:not|unaffected|independent|separate|does\s+not)",
            msg="Step 7c-bis must explicitly decouple its skip from the Step 7c "
                "cost-quality correlation (absence of deploy_outcome records must NOT "
                "skip the Step 7c cost-quality step)",
        )


if __name__ == "__main__":
    unittest.main()
