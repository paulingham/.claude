"""AC-A6b: PORTING-NOTES.md documents the additionalDirectories deferred limitation."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PORTING_NOTES = REPO_ROOT / "PORTING-NOTES.md"


def test_porting_notes_documents_additional_directories_deferred():
    text = PORTING_NOTES.read_text()
    assert "additionalDirectories" in text, (
        'PORTING-NOTES.md missing "additionalDirectories"'
    )
    assert "deferred" in text, (
        'PORTING-NOTES.md missing "deferred" (CA4 deferred limitation note)'
    )
