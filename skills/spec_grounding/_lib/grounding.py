"""AC grounding: pathlib/re traversal (primary) + recall (secondary).

Public surface
--------------
GroundedAC       — frozen dataclass: id, form, text, citation, resolved
ground_acs()     — ground a list of raw AC strings; never raises
validate_citations() — return AC ids whose file:line citations don't resolve

Import contract for recall
--------------------------
Guarded import — degrades to codebase-only when recall is unavailable.
Callers must insert skills/ into sys.path before importing this module
(same requirement as all skill Python tests).
"""
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from spec_grounding._lib.ac_forms import classify_form

# ---------------------------------------------------------------------------
# Guarded recall import (plan § Import Contract)
# ---------------------------------------------------------------------------
try:
    _SKILLS_ROOT = str(Path(__file__).resolve().parents[3])
    if _SKILLS_ROOT not in sys.path:
        sys.path.insert(0, _SKILLS_ROOT)
    from recall import recall as _recall
    _RECALL_AVAILABLE = True
except ImportError:
    _RECALL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Traversal bounds
# ---------------------------------------------------------------------------
_MAX_FILES = 5000
_MAX_FILE_BYTES = 1024 * 1024  # 1 MB
_SKIP_DIRS = frozenset({".git", ".claude"})


# ---------------------------------------------------------------------------
# GroundedAC
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GroundedAC:
    id: str        # "AC1", "AC2" ...
    form: str      # EARS form tag or "prose"
    text: str      # full AC text
    citation: str  # "path/file.py:N-M" | "recall:obs-id" | "gap"
    resolved: bool # True = citation confirmed; False = "gap"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ground_acs(
    raw_acs: list,
    *,
    repo_root: Path,
    db_path=None,
    recall_limit: int = 10,
) -> list:
    """Ground raw AC strings against codebase + recall. Never raises.

    Returns one GroundedAC per input. Traversal is bounded to _MAX_FILES
    files and _MAX_FILE_BYTES per file. Binary files, .git/, and
    .claude/worktrees/ are skipped. Per-file OSError/UnicodeDecodeError
    are swallowed.
    """
    resolved_db = _resolve_db(db_path)
    codebase_index = _build_codebase_index(repo_root)

    results = []
    for idx, text in enumerate(raw_acs):
        ac_id = f"AC{idx + 1}"
        form = classify_form(text)
        citation = _find_citation(text, codebase_index, resolved_db, recall_limit)
        results.append(GroundedAC(
            id=ac_id,
            form=form,
            text=text,
            citation=citation,
            resolved=(citation != "gap"),
        ))
    return results


def validate_citations(grounded: list, repo_root: Path) -> list:
    """Return AC ids whose file:line citations do not resolve.

    'gap' and 'recall:*' citations are excluded from file-resolution checks.
    """
    gaps = []
    for ac in grounded:
        if _is_excluded_citation(ac.citation):
            continue
        if not _file_citation_resolves(ac.citation, repo_root):
            gaps.append(ac.id)
    return gaps


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_db(db_path):
    """Return explicit db_path or the value from CLAUDE_RECALL_DB_PATH env var."""
    if db_path is not None:
        return db_path
    env_val = os.environ.get("CLAUDE_RECALL_DB_PATH")
    return Path(env_val) if env_val else None


def _build_codebase_index(repo_root: Path) -> list:
    """Walk repo_root; return list of (path, content) for searchable text files.

    Skips: binary files, .git/, .claude/worktrees/, files >1MB,
    files that raise OSError or UnicodeDecodeError.
    Bounded to _MAX_FILES files.
    """
    index = []
    file_count = 0

    for filepath in _walk(repo_root):
        if file_count >= _MAX_FILES:
            break
        content = _safe_read(filepath)
        if content is None:
            continue
        index.append((filepath, content))
        file_count += 1

    return index


def _walk(directory: Path):
    """Yield file paths under directory, skipping excluded dirs."""
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        return

    for entry in entries:
        if entry.is_dir():
            if _is_skipped_dir(entry):
                continue
            yield from _walk(entry)
        elif entry.is_file():
            yield entry


def _is_skipped_dir(entry: Path) -> bool:
    if entry.name in _SKIP_DIRS:
        return True
    parts = entry.parts
    if ".claude" in parts and "worktrees" in parts:
        return True
    return False


def _safe_read(filepath: Path):
    """Return file text or None if the file should be skipped."""
    try:
        if filepath.stat().st_size > _MAX_FILE_BYTES:
            return None
    except OSError:
        return None

    try:
        raw = filepath.read_bytes()
    except OSError:
        return None

    if b"\x00" in raw:
        return None  # binary file

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _find_citation(text: str, codebase_index: list, db_path, recall_limit: int) -> str:
    """Return the best citation for ac_text: file:line, recall:id, or 'gap'."""
    terms = _extract_terms(text)
    if not terms:
        return "gap"

    # Try recall first if available and DB exists
    recall_citation = _recall_citation(terms, db_path, recall_limit)
    if recall_citation:
        return recall_citation

    # Fallback to codebase traversal
    return _codebase_citation(terms, codebase_index)


def _extract_terms(text: str) -> list:
    """Extract meaningful search terms from AC text (non-stopwords, len>=4)."""
    _STOPWORDS = frozenset({
        "when", "while", "then", "shall", "should", "that", "with",
        "this", "from", "have", "will", "been", "were", "they",
        "system", "the", "and", "for", "not", "are", "its",
        "also", "must", "each", "some", "any", "all",
    })
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    return [w for w in words if len(w) >= 4 and w.lower() not in _STOPWORDS]


def _recall_citation(terms: list, db_path, recall_limit: int) -> str:
    """Return 'recall:{id}' for the top hit, or '' if unavailable/no results."""
    if not _RECALL_AVAILABLE or db_path is None:
        return ""
    if not Path(str(db_path)).exists():
        return ""

    query = " ".join(terms[:5])
    try:
        hits = _recall.search(query, limit=recall_limit, db_path=str(db_path))
    except Exception:
        return ""

    if hits:
        hit = hits[0]
        obs_id = hit.get("id") or hit.get("rowid") or "unknown"
        return f"recall:{obs_id}"
    return ""


def _codebase_citation(terms: list, codebase_index: list) -> str:
    """Return 'file.py:N' for the first line matching any term, or 'gap'."""
    for filepath, content in codebase_index:
        for lineno, line in enumerate(content.splitlines(), start=1):
            if _line_matches_any(line, terms):
                return f"{filepath}:{lineno}"
    return "gap"


def _line_matches_any(line: str, terms: list) -> bool:
    line_lower = line.lower()
    return any(term.lower() in line_lower for term in terms)


def _is_excluded_citation(citation: str) -> bool:
    """True when citation is 'gap' or starts with 'recall:'."""
    return citation == "gap" or citation.startswith("recall:")


def _file_citation_resolves(citation: str, repo_root: Path) -> bool:
    """Return True if the file:line citation points to an existing file."""
    # Strip line number suffix (e.g. "path/file.py:14-28" or "path/file.py:14")
    path_part = citation.split(":")[0]
    candidate = repo_root / path_part
    return candidate.exists()
