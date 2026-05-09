"""AC1.8 — `/property-based-test` skill documents the language → framework table.

Asserts a markdown table with header `| Language | PBT framework |`
exists; rows include Python/Hypothesis, TypeScript/fast-check,
Erlang/PropEr, Go (none), Rust, Swift (none), Bash; framework-less
languages emit PBT_SKIPPED reason `no-framework-for-language` (or
`no-candidates` for typeless shells), NOT PBT_BLOCKED.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"

REQUIRED_PAIRS = (
    ("Python", "Hypothesis"),
    ("TypeScript", "fast-check"),  # may also be "JavaScript"
    ("Erlang", "PropEr"),
)
MUST_NAME_LANGUAGES = ("Go", "Rust", "Swift", "Bash")


def _has_table_header(body):
    return bool(
        re.search(r"\|\s*Language\s*\|\s*PBT framework\s*\|",
                  body, re.IGNORECASE))


def test_skill_documents_language_framework_table():
    body = SKILL_PATH.read_text()
    assert _has_table_header(body), (
        "property-based-test SKILL.md missing language-framework table "
        "with header `| Language | PBT framework |`")
    for language, framework in REQUIRED_PAIRS:
        assert language in body and framework in body, (
            f"language-framework table missing pairing: {language} / {framework}")
    for language in MUST_NAME_LANGUAGES:
        assert language in body, (
            f"language-framework table must name {language}")
    # Skipped reason for framework-less languages must reference one of the
    # benign skip codes — NEVER PBT_BLOCKED.
    assert "no-framework-for-language" in body or "no-candidates" in body, (
        "language-framework table must route framework-less languages to "
        "PBT_SKIPPED reason `no-framework-for-language` or `no-candidates`")
