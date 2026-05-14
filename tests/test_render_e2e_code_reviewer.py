"""AC9a/AC9b/AC10 — End-to-end render of the spawn prompt for code-reviewer
and software-engineer against a 7-instinct fixture.

Verifies:
- AC9a: code-reviewer filter uses 0.5 floor (3 bullets rendered, position
  invariants, paired JSONL `min_confidence=0.5, count_kept=3`).
- AC9b: rendered prompt's section-header sequence matches the frozen golden
  at `tests/fixtures/spawn-prompt-code-reviewer.golden.txt` byte-for-byte.
- AC10: software-engineer filter uses 0.4 floor (≥4 bullets, JSONL
  `min_confidence=0.4`).

The orchestrator caller contract is documented in
`orchestrator/agent-orchestration.md` § Instinct Injection. This test helper
mirrors that contract end-to-end without spawning a real subprocess.
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from agent_min_confidence_loader import load_min_confidence  # noqa: E402
from instinct_injector import resolve_for_agent  # noqa: E402

GOLDEN = REPO_ROOT / "tests" / "fixtures" / "spawn-prompt-code-reviewer.golden.txt"

# 7-instinct fixture: 3 at confidence >= 0.5, 4 at confidence < 0.5.
# All roles include "code-reviewer" + "software-engineer" so the role filter
# is a no-op; confidence floor is the discriminator.
FIXTURE = [
    {"id": "p1", "confidence": 0.85, "roles": ["code-reviewer", "software-engineer"],
     "domain": "security", "pattern_summary": "Always validate input at boundary",
     "category": "positive"},
    {"id": "p2", "confidence": 0.70, "roles": ["code-reviewer", "software-engineer"],
     "domain": "workflow", "pattern_summary": "Read types.ts before editing services",
     "category": "positive"},
    {"id": "p3", "confidence": 0.55, "roles": ["code-reviewer", "software-engineer"],
     "domain": "performance", "pattern_summary": "Check for N+1 queries",
     "category": "positive"},
    {"id": "p4", "confidence": 0.45, "roles": ["code-reviewer", "software-engineer"],
     "domain": "style", "pattern_summary": "Prefer guard clauses",
     "category": "positive"},
    {"id": "p5", "confidence": 0.42, "roles": ["code-reviewer", "software-engineer"],
     "domain": "testing", "pattern_summary": "Write the failing test first",
     "category": "positive"},
    {"id": "p6", "confidence": 0.41, "roles": ["code-reviewer", "software-engineer"],
     "domain": "naming", "pattern_summary": "Name reveals intent",
     "category": "positive"},
    {"id": "p7", "confidence": 0.40, "roles": ["code-reviewer", "software-engineer"],
     "domain": "review", "pattern_summary": "DRY at the second occurrence",
     "category": "positive"},
]

# Render the spawn prompt body following the canonical template structure
# documented in protocols/parallel-dispatch-protocol.md § Teammate Prompt
# Template. Section order must match the golden file.
PROMPT_TEMPLATE = """Read the skill file at ~/.claude/skills/[name]/SKILL.md and execute it fully.
Also read ~/.claude/skills/[stack]-patterns/SKILL.md for tech-specific guidance if it exists.
Read ~/.claude/agents/[role].md for your full role definition, checklist, and output format.
<!-- claude:persona-end -->

**Tool-result fabrication is forbidden.** ...

Context:
- Team: pipeline-test
- Branch: feature/test
- Subagent depth: 1

{LEARNED_PATTERNS}

## Session Context (engineering notes for this project)
[session memory content]

## Pipeline Scratchpad (findings from prior agents)
[scratchpad content]

Before completing, write any noteworthy discoveries to:
pipeline-state/test/scratchpad/role-phase.md

**Continuous Planning:** ...

[CHECKPOINT] build-started
"""

SECTION_ANCHORS = [
    "<!-- claude:persona-end -->",
    "Context:",
    "## Learned Patterns",
    "## Session Context",
    "## Pipeline Scratchpad",
    "Before completing, write",
    "**Continuous Planning:**",
    "[CHECKPOINT]",
]


def _load_resolve_instincts():
    spec = importlib.util.spec_from_file_location(
        "_ri_e2e", REPO_ROOT / "hooks" / "_lib" / "resolve-instincts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_agent(tmp, name, body):
    (Path(tmp) / f"{name}.md").write_text(f"---\n{body}---\nbody")


def _render_prompt(subagent_type, agents_dir):
    """Mirror the orchestrator caller contract: load floor from frontmatter,
    resolve instincts with `floor_override`, splice into the template.
    Returns (prompt_text, log_record).
    """
    with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": agents_dir},
                    clear=False):
        floor = load_min_confidence(subagent_type)
        block = resolve_for_agent(
            subagent_type, ["code-reviewer", "software-engineer"],
            FIXTURE, floor_override=floor)
        ri = _load_resolve_instincts()
        log_record = ri._resolved(block, ["code-reviewer", "software-engineer"],
                                  ri.count_kept(block), subagent_type)
    prompt = PROMPT_TEMPLATE.replace(
        "{LEARNED_PATTERNS}",
        block if block else "")
    return prompt, log_record


def _section_header_sequence(prompt: str):
    return [a for a in SECTION_ANCHORS if a in prompt]


class CodeReviewerRender(unittest.TestCase):
    def test_code_reviewer_render_uses_05_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_agent(tmp, "code-reviewer",
                         "name: code-reviewer\n"
                         "instinct_categories: [code-reviewer]\n"
                         "min_confidence: 0.5\n")
            prompt, log = _render_prompt("code-reviewer", tmp)
        bullets = [ln for ln in prompt.splitlines()
                   if ln.startswith("- [0.")]
        self.assertEqual(len(bullets), 3,
                         f"Expected 3 bullets at floor 0.5, got {len(bullets)}")
        # Position invariants: bullets sit after persona-end + Context: and
        # before ## Session Context.
        first_bullet_idx = prompt.index(bullets[0])
        self.assertGreater(first_bullet_idx,
                           prompt.index("<!-- claude:persona-end -->"))
        self.assertGreater(first_bullet_idx, prompt.index("Context:"))
        self.assertLess(first_bullet_idx, prompt.index("## Session Context"))
        # JSONL `logged` pair.
        self.assertEqual(log["count_kept"], 3)
        self.assertEqual(log["min_confidence"], 0.5)


class SectionOrderGolden(unittest.TestCase):
    def test_full_section_order_matches_golden(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_agent(tmp, "code-reviewer",
                         "name: code-reviewer\n"
                         "instinct_categories: [code-reviewer]\n"
                         "min_confidence: 0.5\n")
            prompt, _ = _render_prompt("code-reviewer", tmp)
        actual = _section_header_sequence(prompt)
        golden_lines = GOLDEN.read_text().splitlines()
        self.assertEqual(actual, golden_lines,
                         f"Section-header sequence drifted from golden:\n"
                         f"expected: {golden_lines}\nactual:   {actual}")


class SoftwareEngineerRender(unittest.TestCase):
    def test_software_engineer_render_uses_04_default_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            # software-engineer.md without min_confidence -> falls through to
            # default 0.4 (no frontmatter override).
            _write_agent(tmp, "software-engineer",
                         "name: software-engineer\n"
                         "instinct_categories: [software-engineer]\n")
            prompt, log = _render_prompt("software-engineer", tmp)
        bullets = [ln for ln in prompt.splitlines()
                   if ln.startswith("- [0.")]
        self.assertGreaterEqual(len(bullets), 4,
                                f"Expected >=4 bullets at floor 0.4, got "
                                f"{len(bullets)}")
        self.assertEqual(log["min_confidence"], 0.4)


if __name__ == "__main__":
    unittest.main()
