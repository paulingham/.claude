"""Slice slice-c-consumer AC7 — Field reference table documents wave_count / wave_widths.

`rules/_detail/autonomous-intelligence.md` § Field reference must list both
`phases.build.wave_count` and `phases.build.wave_widths` with absence-tolerance
prose for legacy-record readers.
"""
from pathlib import Path

import pytest

AI_FILE = (
    Path(__file__).resolve().parent.parent
    / "rules"
    / "_detail"
    / "autonomous-intelligence.md"
)


@pytest.fixture(scope="module")
def ai_text() -> str:
    return AI_FILE.read_text()


@pytest.fixture(scope="module")
def field_reference_block(ai_text: str) -> str:
    """Body between `#### Field reference` and the next `####` or `###` heading."""
    start = ai_text.find("#### Field reference")
    assert start != -1, "Field reference subsection missing"
    after = ai_text[start:]
    # Stop at the next `### ` (top-level subsection) — the table's own H4 is fine.
    next_h3 = after.find("\n### ")
    return after if next_h3 == -1 else after[:next_h3]


def test_field_reference_documents_wave_count(field_reference_block: str) -> None:
    assert "phases.build.wave_count" in field_reference_block
    # Absence-tolerance must be explicit.
    assert "tolerate absence" in field_reference_block.lower() or \
           "absence" in field_reference_block.lower()


def test_field_reference_documents_wave_widths(field_reference_block: str) -> None:
    assert "phases.build.wave_widths" in field_reference_block


def test_field_reference_wave_fields_cite_schema_version_2(field_reference_block: str) -> None:
    """Both fields are present only on schema_version: 2 pipelines — readers must know."""
    # Find the wave_count row.
    wc_idx = field_reference_block.find("phases.build.wave_count")
    assert wc_idx != -1
    # Look at the next ~600 chars for the schema_version qualifier.
    window = field_reference_block[wc_idx:wc_idx + 800]
    assert "schema_version: 2" in window or "schema_version 2" in window, (
        "wave_count row must qualify presence with schema_version: 2"
    )
