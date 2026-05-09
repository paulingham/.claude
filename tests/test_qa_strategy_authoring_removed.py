"""AC5.1 — qa-engineer prompt body loses PBT authoring procedure.

Asserts the qa-engineer prompt body (the multi-line `prompt: "Analyze...`
literal in `skills/qa-test-strategy/SKILL.md`, terminated by the
closing `})` of the Agent invocation) contains zero substring matches
for the procedural authoring markers (Hypothesis, fast-check, PropEr,
@given, idempotence/inverse/oracle/metamorphic). Step numbering inside
the prompt body must be sequential 1..N with no gaps.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "qa-test-strategy" / "SKILL.md"

FORBIDDEN_AUTHORING_SUBSTRINGS = (
    "Hypothesis",
    "fast-check",
    "PropEr",
    "@given",
    "idempotence/inverse/oracle/metamorphic",
)


def _qa_engineer_prompt_body(body):
    """Extract the qa-engineer Agent prompt literal: from `prompt: "Analyze`
    to the closing `})`."""
    match = re.search(
        r'prompt:\s*"Analyze test coverage for this feature:(.*?)\}\)',
        body, re.DOTALL)
    assert match, "Could not locate qa-engineer Agent prompt body"
    return match.group(1)


def test_qa_engineer_prompt_no_pbt_authoring():
    body = SKILL_PATH.read_text()
    prompt = _qa_engineer_prompt_body(body)
    found = [s for s in FORBIDDEN_AUTHORING_SUBSTRINGS if s in prompt]
    assert not found, (
        f"qa-engineer prompt body still contains PBT authoring markers "
        f"after Slice 5: {found!r}")


def test_qa_engineer_prompt_step_numbering_sequential():
    body = SKILL_PATH.read_text()
    prompt = _qa_engineer_prompt_body(body)
    step_numbers = [int(m.group(1))
                    for m in re.finditer(r"^\s*(\d+)\.\s", prompt, re.MULTILINE)]
    assert step_numbers, "qa-engineer prompt body has no numbered steps"
    expected = list(range(1, len(step_numbers) + 1))
    assert step_numbers == expected, (
        f"qa-engineer prompt step numbering must be sequential 1..N with "
        f"no gaps, got {step_numbers}")
