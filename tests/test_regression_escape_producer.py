"""AC2: Deploy + deployment-verification skills document outcome append step.

Verifies:
- skills/deploy/SKILL.md documents a deploy_outcome append step using os.open + O_APPEND.
- skills/deployment-verification/SKILL.md appends a deploy_outcome record carrying AUTO_ROLLBACK.
- Both producers source hooks/_lib/project-hash.sh and write under learning/{project-hash}/observations.jsonl.
- Producer prose is advisory (no enforcing verb without advisory qualifier).
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY = REPO_ROOT / "skills" / "deploy" / "SKILL.md"
VERIFY = REPO_ROOT / "skills" / "deployment-verification" / "SKILL.md"

ENFORCING_VERBS = re.compile(
    r"\b(blocks|prevents|rejects|enforces|denies)\b", re.IGNORECASE
)
ADVISORY_QUALIFIER = re.compile(
    r"\b(advisory|optional|telemetry|log.?only|capture|signal)\b", re.IGNORECASE
)


def _new_step_body(text: str) -> str:
    """Return text of the deploy outcome step if present, else empty string."""
    match = re.search(
        r"(?:Persist deploy outcome|deploy_outcome.*append)(.+?)(?=\n###|\n##|\Z)",
        text, re.DOTALL | re.IGNORECASE)
    return match.group(0) if match else ""


class DeploySkillDocumentsOutcomeAppend(unittest.TestCase):
    def test_deploy_skill_documents_outcome_append(self):
        text = DEPLOY.read_text()
        self.assertIn("deploy_outcome", text,
                      "skills/deploy/SKILL.md must document a deploy_outcome append step")
        self.assertIn("os.open", text,
                      "skills/deploy/SKILL.md must use os.open (not bare >>) for sandbox-safe append")
        self.assertIn("O_APPEND", text,
                      "skills/deploy/SKILL.md must use O_APPEND flag")
        self.assertNotIn(">> observations.jsonl", text,
                         "skills/deploy/SKILL.md must NOT use bare bash >> to observations.jsonl")

    def test_verification_skill_documents_auto_rollback_append(self):
        text = VERIFY.read_text()
        self.assertIn("deploy_outcome", text,
                      "skills/deployment-verification/SKILL.md must document a deploy_outcome append step")
        self.assertIn("AUTO_ROLLBACK", text,
                      "skills/deployment-verification/SKILL.md must reference AUTO_ROLLBACK outcome")
        self.assertIn("os.open", text,
                      "skills/deployment-verification/SKILL.md must use os.open for sandbox-safe append")
        self.assertIn("O_APPEND", text,
                      "skills/deployment-verification/SKILL.md must use O_APPEND flag")

    def test_producer_uses_project_hash_helper(self):
        deploy_text = DEPLOY.read_text()
        verify_text = VERIFY.read_text()
        for skill_name, text in [("deploy", deploy_text), ("deployment-verification", verify_text)]:
            self.assertIn("project-hash.sh", text,
                          f"skills/{skill_name}/SKILL.md must source hooks/_lib/project-hash.sh")
            self.assertIn("observations.jsonl", text,
                          f"skills/{skill_name}/SKILL.md must write to learning/{{project-hash}}/observations.jsonl")

    def test_producer_prose_is_advisory_not_gate(self):
        deploy_text = DEPLOY.read_text()
        verify_text = VERIFY.read_text()
        for skill_name, text in [("deploy", deploy_text), ("deployment-verification", verify_text)]:
            new_step = _new_step_body(text)
            if not new_step:
                continue
            for match in ENFORCING_VERBS.finditer(new_step):
                start = max(0, match.start() - 100)
                end = min(len(new_step), match.end() + 100)
                context = new_step[start:end]
                self.assertTrue(
                    ADVISORY_QUALIFIER.search(context),
                    f"skills/{skill_name}/SKILL.md new step contains enforcing verb "
                    f"'{match.group()}' without an advisory qualifier in context: {context!r}",
                )


if __name__ == "__main__":
    unittest.main()
