"""AC1.2 — `/property-based-test` skill body documents the procedure.

Asserts the procedure markers are all present AND the canonical glob
string `tests/**/*.property.{spec,test}.*` is byte-identical between the
new skill and `skills/build-implementation/SKILL.md` line 94.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"
BUILD_IMPL_PATH = REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"

CANONICAL_GLOB = "tests/**/*.property.{spec,test}.*"
PROCEDURE_MARKERS = (
    "identify candidate",
    "time-box",
    "60s",
    "freeze",
    CANONICAL_GLOB,
)


def test_skill_documents_full_pbt_procedure():
    body = SKILL_PATH.read_text()
    body_lower = body.lower()
    # Procedure markers checked case-insensitively except the canonical glob,
    # which must be byte-identical (case included).
    missing = []
    for marker in PROCEDURE_MARKERS:
        haystack = body if marker == CANONICAL_GLOB else body_lower
        needle = marker if marker == CANONICAL_GLOB else marker.lower()
        if needle not in haystack:
            missing.append(marker)
    assert not missing, (
        f"property-based-test SKILL.md is missing procedure markers: "
        f"{missing!r}")


def test_glob_byte_identical_between_new_skill_and_build_implementation():
    new_body = SKILL_PATH.read_text()
    existing_body = BUILD_IMPL_PATH.read_text()
    assert CANONICAL_GLOB in new_body, (
        f"property-based-test SKILL.md missing canonical glob "
        f"{CANONICAL_GLOB!r}")
    assert CANONICAL_GLOB in existing_body, (
        f"build-implementation SKILL.md missing canonical glob "
        f"{CANONICAL_GLOB!r} — Step 2b cap-detection broken")
