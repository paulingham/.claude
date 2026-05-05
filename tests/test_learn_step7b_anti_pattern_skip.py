"""C8 S5: anti-pattern instincts NEVER auto-scaffold permanent skills.

Step 7b of `/learn` (Live-SWE promotion loop) auto-scaffolds new
permanent skills under `~/.claude/skills/<tool-name>/` when a scratch
tool's signature recurs across >= 3 distinct pipelines via the
`TOOL_SYNTHESISED_PROMOTABLE` verdict. Anti-pattern instincts MUST
be excluded from that scan — they are guidance, not promotable
verdicts.

Two tests:
  AC5.1 — behavioural: a freshly-mined anti-pattern instinct that
          shares the recurrence shape of a promotable signal does
          NOT cause Step 7b to scaffold a new skill directory.
  AC5.2 — documentation: SKILL.md § 7b carries the literal exclusion
          phrase so future edits cannot silently regress.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "learn" / "SKILL.md"
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from learn_anti_pattern_mining import mine_anti_patterns  # noqa: E402


class Step7bSkipsAntiPatternInstincts(unittest.TestCase):
    """Anti-pattern files that match the >=3-pipeline recurrence shape
    do NOT cause `~/.claude/skills/<tool-name>/` directories to be
    scaffolded by Step 7b.

    Step 7b's detection pipeline (per SKILL.md):
      jq filter on TOOL_SYNTHESISED_PROMOTABLE verdict
      -> sort | uniq -c | awk '$1 >= 3' -> mkdir skills/<tool>

    A correctly-mined anti-pattern instinct emits to
    `instincts/anti-pattern-<key>.md`. It does NOT emit a
    TOOL_SYNTHESISED_PROMOTABLE verdict to scratchpad_findings.
    Therefore the Step 7b detection sees zero matches and no skill
    directory is scaffolded.
    """

    def test_anti_pattern_instinct_does_not_trigger_skill_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            obs = tmp_path / "observations.jsonl"
            with obs.open("w") as f:
                # Three pipelines with the SAME warning finding.
                # Mining will emit one anti-pattern file. Step 7b
                # MUST see no TOOL_SYNTHESISED_PROMOTABLE and so
                # MUST NOT create any skills/* directory.
                for n in (1, 2, 3):
                    f.write(json.dumps({
                        "record_type": "pipeline",
                        "pipeline_id": f"p-{n}",
                        "phases": {"review": {"rounds": 2}},
                        "scratchpad_findings":
                            ["warning: payment webhook timing"],
                    }) + "\n")
            files = mine_anti_patterns(observations_path=obs,
                                       instincts_dir=tmp_path / "instincts")
            self.assertEqual(len(files), 1)
            # Reproduce the Step 7b detection pipe: scan
            # observations.jsonl for TOOL_SYNTHESISED_PROMOTABLE.
            promotable_count = 0
            with obs.open() as f:
                for line in f:
                    if "TOOL_SYNTHESISED_PROMOTABLE" in line:
                        promotable_count += 1
            self.assertEqual(promotable_count, 0,
                             "Anti-pattern mining must not emit "
                             "TOOL_SYNTHESISED_PROMOTABLE verdicts.")
            # Belt-and-braces: confirm the emitted file lives under
            # instincts/, not under a hypothetical skills/ scaffold.
            for f in files:
                self.assertEqual(f.parent.name, "instincts")
                self.assertNotEqual(f.parent.parent.name, "skills")


class Step7bDocSnapshotPinsSkipClause(unittest.TestCase):
    """SKILL.md § 7b contains the literal exclusion phrase."""

    def test_skill_md_step_7b_contains_explicit_anti_pattern_skip_phrase(self):
        text = SKILL_PATH.read_text()
        # Find the §7b section start.
        match = re.search(
            r"### 7b\..*?(?=\n### 7c\.|\n### 8\.|\Z)",
            text, re.DOTALL)
        self.assertIsNotNone(match,
                             "Could not locate § 7b in skills/learn/SKILL.md")
        section = match.group(0)
        self.assertIn(
            "anti-pattern instincts are excluded from the auto-scaffold scan",
            section.lower(),
            "§ 7b must contain the literal anti-pattern skip phrase")


if __name__ == "__main__":
    unittest.main()
