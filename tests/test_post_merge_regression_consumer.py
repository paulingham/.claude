"""AC3: /harness:learn Step 7c-ter computes project-level post-merge-regression escape rate
and Step 9 renders a distinct labelled block.

Verifies:
- skills/learn/SKILL.md documents a ### 7c-ter section AFTER 7c-bis, computing
  post_merge_escape_rate from triggered_by_pipeline_id records.
- The 7c-ter body pins "present AND truthy" (not merely key-exists) as the numerator
  predicate — RED-on-revert mutant guard.
- post_merge_escape_rate is NOT a key in the Step 7c group-dict (project-level,
  regression guard mirrors 7c-bis).
- Step 9 renders a distinct labelled sub-block: "Post-Merge Regression Reliability"
  + raw count form "recorded pipelines" (NOT "merged pipelines") AND still contains
  #222's "deploy-phase rollbacks" (COMPOSE, not replace).
- Step 9 empty-state copy is pinned verbatim:
  "not yet measured — no post-merge regressions attributed."
- Step 7c-ter body has NO >= / <= numeric thresholds, NO % targets, NO enforcing
  verb without advisory qualifier (windowed to 7c-ter body only, avoiding 7c
  thresholds).
- Step 7c-ter documents skip-on-empty AND explicitly decouples from BOTH 7c-bis
  (deploy) AND Step 7c cost-quality.
- COMPOSE guard: 7c-bis body still contains escape_rate + "deploy-phase rollbacks"
  (not accidentally replaced by 7c-ter).
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEARN = REPO_ROOT / "skills" / "learn" / "SKILL.md"


def _step7c_ter_body() -> str:
    """Return the body of the ### 7c-ter section up to the next ### or ##."""
    text = LEARN.read_text()
    match = re.search(
        r"###\s+7c-ter\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


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


class Step7cTerDocumentsPostMergeEscapeFormula(unittest.TestCase):
    def test_step7c_ter_documents_post_merge_escape_formula(self):
        """Windowed 7c-ter body must document triggered_by_pipeline_id, classification,
        and the bug+truthy numerator."""
        body = _step7c_ter_body()
        self.assertTrue(
            body,
            "skills/learn/SKILL.md must have a ### 7c-ter section documenting "
            "post-merge regression escape rate",
        )
        self.assertIn(
            "triggered_by_pipeline_id",
            body,
            "Step 7c-ter must reference triggered_by_pipeline_id",
        )
        self.assertIn(
            "classification",
            body,
            "Step 7c-ter must reference classification (bug filter on numerator)",
        )
        self.assertIn(
            "bug",
            body,
            "Step 7c-ter must document that the numerator filters to classification=bug",
        )

    def test_consumer_counts_truthy_not_key_exists(self):
        """7c-ter body must explicitly say 'present AND truthy' (not just key-present).

        This is the value-pollution mutant guard: a null or '' value must NOT count.
        RED-on-revert if the truthy-not-just-present wording is dropped.
        """
        body = _step7c_ter_body()
        self.assertTrue(
            body,
            "### 7c-ter section not found — cannot verify truthy predicate wording",
        )
        self.assertRegex(
            body,
            r"present\s+AND\s+truthy|falsy.*do\s+NOT\s+count|falsy.*must\s+NOT\s+count"
            r"|truthy.*not.*key.exists|null.*must\s+NOT\s+count",
            msg="Step 7c-ter must explicitly document 'present AND truthy' counting predicate "
                "(a null or empty string must NOT count as attributed — "
                "mirrors the absence-tolerance contract)",
        )

    def test_rate_is_project_level_not_in_step7c_group_dict(self):
        """post_merge_escape_rate must NOT be a key in the Step 7c group-dict output."""
        body = _step7c_body()
        self.assertTrue(body, "### 7c section not found in skills/learn/SKILL.md")
        # Check the output-dict key list
        match = re.search(r"keys?\s*[`'\"]?\{([^}]+)\}", body)
        if match:
            keys_text = match.group(1)
            self.assertNotIn(
                "post_merge_escape_rate",
                keys_text,
                "post_merge_escape_rate must NOT appear in the Step 7c per-group output-dict "
                "key list (it is a project-level metric in Step 7c-ter, not a per-group key)",
            )
        # Also check the per-group aggregate table
        self.assertNotRegex(
            body,
            r"\|\s*post_merge_escape_rate\s*\|",
            msg="post_merge_escape_rate must not be a row in the Step 7c per-group table",
        )

    def test_step9_renders_distinct_labelled_line(self):
        """Step 9 must render Post-Merge Regression Reliability block + raw count
        '(n of m recorded pipelines)' (NOT 'merged pipelines') AND preserve #222's
        'deploy-phase rollbacks' label (COMPOSE, not replace)."""
        body = _step9_body()
        self.assertTrue(body, "### 9. Report section not found in skills/learn/SKILL.md")
        self.assertIn(
            "Post-Merge Regression Reliability",
            body,
            "Step 9 Report must include a 'Post-Merge Regression Reliability' labelled block",
        )
        # Must use 'recorded pipelines' NOT 'merged pipelines'
        self.assertRegex(
            body,
            r"recorded\s+pipelines",
            msg="Step 9 Post-Merge block must say 'recorded pipelines' "
                "(NOT 'merged pipelines') — conservative bias note",
        )
        # #222 COMPOSE guard: deploy-phase rollbacks must still be there
        self.assertIn(
            "deploy-phase rollbacks",
            body,
            "Step 9 must still contain #222's 'deploy-phase rollbacks' label "
            "(COMPOSE guard — 7c-ter adds, does not replace 7c-bis rendering)",
        )

    def test_step9_empty_state_copy_pinned(self):
        """Step 9 empty-state copy must be verbatim:
        'not yet measured — no post-merge regressions attributed.'"""
        body = _step9_body()
        self.assertTrue(body, "### 9. Report section not found in skills/learn/SKILL.md")
        self.assertIn(
            "not yet measured — no post-merge regressions attributed.",
            body,
            "Step 9 must contain verbatim empty-state copy "
            "'not yet measured — no post-merge regressions attributed.' "
            "for when no triggered_by_pipeline_id records exist",
        )

    def test_no_threshold_or_ceiling_in_step7c_ter(self):
        """Windowed 7c-ter body must have no >= / <= numeric thresholds, no % targets,
        and no enforcing verb without advisory qualifier."""
        body = _step7c_ter_body()
        self.assertTrue(
            body,
            "### 7c-ter section not found — cannot verify absence of threshold/ceiling",
        )
        self.assertNotRegex(
            body,
            r">=\s*\d+\.?\d*|<=\s*\d+\.?\d*",
            msg="Step 7c-ter must NOT contain >= or <= numeric thresholds or ceilings",
        )
        self.assertNotRegex(
            body,
            r"\d+\s*%",
            msg="Step 7c-ter must NOT contain percentage targets (no hard-coded ceiling)",
        )
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
                f"Step 7c-ter contains enforcing verb '{m.group()}' without advisory qualifier "
                f"in context: {context!r}",
            )

    def test_skip_on_empty_decoupled_from_222_and_7c(self):
        """7c-ter must document skip-on-empty AND explicitly decouple from BOTH
        7c-bis (deploy) AND Step 7c cost-quality."""
        body = _step7c_ter_body()
        self.assertTrue(body, "### 7c-ter section not found")
        self.assertRegex(
            body,
            r"skip|empty|zero|no\s+triggered",
            msg="Step 7c-ter must document skip-on-empty behaviour",
        )
        # Must decouple from 7c-bis (deploy reliability)
        self.assertRegex(
            body,
            r"(?:7c-bis|deploy[^a-z]|deploy_outcome|deployment)[^.]*"
            r"(?:not|independent|decoupled|separate|unaffected|does\s+not)"
            r"|(?:not|independent|decoupled|separate|unaffected|does\s+not)[^.]*"
            r"(?:7c-bis|deploy[^a-z]|deploy_outcome|deployment)",
            msg="Step 7c-ter must explicitly decouple its skip from Step 7c-bis "
                "(absence of triggered_by records must NOT skip the deploy reliability step)",
        )
        # Must decouple from Step 7c cost-quality
        self.assertRegex(
            body,
            r"(?:7c|cost.quality|per.group)[^.]*"
            r"(?:not|independent|decoupled|separate|unaffected|does\s+not)"
            r"|(?:not|independent|decoupled|separate|unaffected|does\s+not)[^.]*"
            r"(?:7c|cost.quality|per.group)",
            msg="Step 7c-ter must explicitly decouple its skip from Step 7c "
                "cost-quality correlation",
        )

    def test_222_escape_rate_still_documented(self):
        """COMPOSE guard: 7c-bis body must still contain escape_rate (not replaced by 7c-ter),
        and Step 9 body must still contain 'deploy-phase rollbacks' label from #222."""
        bis_body = _step7c_bis_body()
        self.assertTrue(
            bis_body,
            "### 7c-bis section not found — #222 deploy reliability may have been removed",
        )
        self.assertIn(
            "escape_rate",
            bis_body,
            "Step 7c-bis must still document escape_rate "
            "(COMPOSE guard: 7c-ter must not replace 7c-bis)",
        )
        step9 = _step9_body()
        self.assertTrue(step9, "### 9. Report section not found")
        self.assertIn(
            "deploy-phase rollbacks",
            step9,
            "Step 9 must still contain #222's 'deploy-phase rollbacks' label "
            "(COMPOSE guard: 7c-ter adds a distinct block, does not replace 7c-bis rendering)",
        )


if __name__ == "__main__":
    unittest.main()
