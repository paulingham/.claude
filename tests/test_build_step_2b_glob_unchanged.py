"""AC4.4 — Step 2b cap-detection glob byte-identity.

Asserts the canonical glob `tests/**/*.property.{spec,test}.*` still
appears in build-implementation/SKILL.md byte-identical to its
original line 94 form, and the cap-reduction language (5→3) is
preserved. Also re-asserts byte-identity vs the new
property-based-test/SKILL.md (Slice 1's AC1.2 sibling check).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_IMPL_PATH = REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"
PBT_SKILL_PATH = REPO_ROOT / "skills" / "property-based-test" / "SKILL.md"

CANONICAL_GLOB = "tests/**/*.property.{spec,test}.*"


def test_step_2b_glob_byte_identical():
    body = BUILD_IMPL_PATH.read_text()
    # The cap-detection paragraph (originally line 94) must still
    # contain the canonical glob byte-for-byte. Byte-identity is the
    # contract: the line-94 occurrence cannot be mutated. Other
    # occurrences (e.g. Step 1d may reference the same glob) are
    # permitted as long as every occurrence is the canonical form.
    cap_detection_anchor = (
        "Detection is mechanical — file glob `" + CANONICAL_GLOB +
        "` next to the changed file → cap=3.")
    assert cap_detection_anchor in body, (
        f"build-implementation SKILL.md cap-detection paragraph "
        f"must contain the canonical glob byte-for-byte at its "
        f"original site: {cap_detection_anchor!r}")
    assert body.count(CANONICAL_GLOB) >= 1, (
        f"build-implementation SKILL.md must contain at least one "
        f"{CANONICAL_GLOB!r}")
    # Cap-reduction language preserved.
    assert "cap reduces from 5 to 3" in body, (
        "build-implementation SKILL.md must preserve the "
        "`cap reduces from 5 to 3` cap-reduction language")
    # Sibling byte-identity vs new skill (Slice 1 invariant).
    pbt_body = PBT_SKILL_PATH.read_text()
    assert CANONICAL_GLOB in pbt_body, (
        f"property-based-test SKILL.md must contain the canonical glob "
        f"{CANONICAL_GLOB!r} (Slice 1 byte-identity invariant)")
