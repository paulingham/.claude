"""Doc-contract tests for slice A: EARS Promotion + Verdict/Directory Registration.

Slice A ACs: AC-A1 through AC-A6.
Slice C tests (AC-C1 through AC-C5) will be appended by another engineer in wave 1.

Pattern: repo root via Path(__file__).resolve().parents[2]; plain-text substring assertions.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ears_proposal_text():
    path = REPO_ROOT / "protocols" / "_proposals" / "2026-05-24-ears-acceptance-criteria.md"
    return path.read_text()


@pytest.fixture(scope="module")
def story_writing_skill_text():
    path = REPO_ROOT / "skills" / "story-writing" / "SKILL.md"
    return path.read_text()


@pytest.fixture(scope="module")
def verdict_catalog_text():
    path = REPO_ROOT / "protocols" / "verdict-catalog.md"
    return path.read_text()


@pytest.fixture(scope="module")
def skill_directory_text():
    path = REPO_ROOT / "protocols" / "skill-directory.md"
    return path.read_text()


@pytest.fixture(scope="module")
def spec_blind_validate_skill_text():
    path = REPO_ROOT / "skills" / "spec-blind-validate" / "SKILL.md"
    return path.read_text()


# ---------------------------------------------------------------------------
# AC-A1: EARS proposal status is IMPLEMENTED with item-4-deferred note
# ---------------------------------------------------------------------------


def test_ears_proposal_status_is_implemented(ears_proposal_text):
    assert "IMPLEMENTED" in ears_proposal_text
    # item-4-deferred note must be present (item 4 = ac_forms on spec-blind output)
    assert "deferred" in ears_proposal_text.lower() or "item 4" in ears_proposal_text.lower()


# ---------------------------------------------------------------------------
# AC-A2: story-writing SKILL.md documents all five EARS forms
# ---------------------------------------------------------------------------


def test_story_writing_skill_documents_five_ears_forms(story_writing_skill_text):
    text_lower = story_writing_skill_text.lower()
    assert "ubiquitous" in text_lower, "EARS Ubiquitous form missing"
    assert "event" in text_lower, "EARS Event form missing"
    assert "state" in text_lower, "EARS State form missing"
    assert "unwanted" in text_lower, "EARS Unwanted form missing"
    assert "optional" in text_lower, "EARS Optional form missing"


# ---------------------------------------------------------------------------
# AC-A3: story-writing SKILL.md documents form: tag and [grounded:] suffix
# ---------------------------------------------------------------------------


def test_story_writing_skill_documents_form_tag_and_grounded_suffix(story_writing_skill_text):
    assert "form: ears-" in story_writing_skill_text, "form: ears- tag not documented"
    assert "[grounded:" in story_writing_skill_text, "[grounded: citation] suffix not documented"


# ---------------------------------------------------------------------------
# AC-A4: verdict-catalog.md registers GROUNDED and GROUNDING_GAPS with emitter spec-grounding
# ---------------------------------------------------------------------------


def test_verdict_catalog_registers_grounded_and_grounding_gaps(verdict_catalog_text):
    assert "GROUNDED" in verdict_catalog_text, "GROUNDED verdict missing from catalog"
    assert "GROUNDING_GAPS" in verdict_catalog_text, "GROUNDING_GAPS verdict missing from catalog"
    assert "spec-grounding" in verdict_catalog_text, "spec-grounding emitter missing from catalog"


# ---------------------------------------------------------------------------
# AC-A5: skill-directory.md has /harness:spec-grounding row with GROUNDED verdict
# ---------------------------------------------------------------------------


def test_skill_directory_has_spec_grounding_entry(skill_directory_text):
    assert "/harness:spec-grounding" in skill_directory_text, \
        "/harness:spec-grounding row missing from skill directory"
    assert "GROUNDED" in skill_directory_text, \
        "GROUNDED verdict missing from skill directory"


# ---------------------------------------------------------------------------
# AC-A6: spec-blind-validate SKILL.md § Inputs contains form-tag annotation
# ---------------------------------------------------------------------------


def test_spec_blind_validate_skill_documents_form_tag_annotation(spec_blind_validate_skill_text):
    text = spec_blind_validate_skill_text
    assert "form:" in text, "form: tag annotation missing from spec-blind-validate Inputs"
    # trigger→arrange or trigger->arrange mapping note
    assert "trigger" in text.lower() and "arrange" in text.lower(), \
        "trigger→arrange mapping note missing from spec-blind-validate Inputs"
