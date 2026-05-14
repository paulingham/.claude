"""AC3 — Orchestrator caller-contract Step 3 references the persona-end marker.

The Instinct Injection caller contract Step 3 in
`orchestrator/agent-orchestration.md` must reference the persona-end marker
as the splice anchor (not a line number).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "orchestrator" / "agent-orchestration.md"


def _instinct_injection_section() -> str:
    text = DOC.read_text()
    # Section header sits at "### Instinct Injection (every Agent spawn)".
    start = text.index("### Instinct Injection")
    # Next top-level (### …) sibling header bounds the section.
    rest = text[start + len("### Instinct Injection"):]
    nxt = re.search(r"\n### ", rest)
    end = start + len("### Instinct Injection") + (nxt.start() if nxt else len(rest))
    return text[start:end]


def _step_block(section: str, step_number: int) -> str:
    """Return the body of `N. **…**:` step block within the section."""
    # Match the step header anchored at start-of-line.
    pat = re.compile(rf"(?ms)^{step_number}\. \*\*.+?(?=^\d+\. \*\*|\Z)")
    m = pat.search(section)
    assert m, f"Step {step_number} not found in Instinct Injection section"
    return m.group(0)


def test_caller_contract_step3_references_persona_end_marker():
    section = _instinct_injection_section()
    step3 = _step_block(section, 3)
    has_marker = "<!-- claude:persona-end -->" in step3 or "persona-end marker" in step3
    assert has_marker, (
        "Caller contract Step 3 must reference the persona-end marker "
        "(literal `<!-- claude:persona-end -->` or phrase `persona-end marker`). "
        f"Step 3 body was:\n{step3}"
    )
