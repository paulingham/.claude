"""Snapshot test: CLAUDE.md Agent-Team table must list every agent/*.md file
(excluding dynamic/ and archive/) exactly once, with Default Model matching
the agent's `model:` frontmatter value.

Row count == discovered agent file count (currently 19, but asserted against
live discovery so the test stays accurate as agents are added/removed).
"""
import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
EXCLUDED_SUBDIRS = {"dynamic", "archive"}

FOOTNOTE_RE = re.compile(r"\s*\[\d+\]\s*$")


def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    return yaml.safe_load(text[4:end]) or {}


def _discover_agent_files() -> list:
    files = []
    for path in sorted(AGENTS_DIR.glob("*.md")):
        if any(part in EXCLUDED_SUBDIRS for part in path.relative_to(AGENTS_DIR).parts):
            continue
        files.append(path)
    return files


def _parse_agent_team_table_rows() -> list[str]:
    """Return data rows (raw markdown lines) from the ### Agent Team table.

    Finds the ``### Agent Team`` heading, locates the first markdown table
    after it (lines starting with ``|``), and returns rows after the
    ``|---|`` separator until the first non-``|`` line.
    """
    text = CLAUDE_MD.read_text()
    lines = text.splitlines()

    # Find the heading
    heading_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "### Agent Team":
            heading_idx = i
            break
    if heading_idx is None:
        raise AssertionError("CLAUDE.md: '### Agent Team' heading not found")

    # Find first table line after heading
    table_start = None
    for i in range(heading_idx + 1, len(lines)):
        if lines[i].strip().startswith("|"):
            table_start = i
            break
    if table_start is None:
        raise AssertionError("CLAUDE.md: no markdown table found after '### Agent Team'")

    # Collect all consecutive table lines
    table_lines = []
    for i in range(table_start, len(lines)):
        if lines[i].strip().startswith("|"):
            table_lines.append(lines[i].strip())
        else:
            break

    # Skip the header row (first |...|) and the separator row (|---|)
    data_rows = []
    past_separator = False
    for line in table_lines:
        if not past_separator:
            # The separator row contains only hyphens, pipes, and spaces
            if re.match(r"^\|[-| ]+\|$", line):
                past_separator = True
            continue
        data_rows.append(line)

    return data_rows


def _row_cells(row: str) -> list[str]:
    """Split a markdown table row into stripped cell strings."""
    return [cell.strip() for cell in row.strip("|").split("|")]


class AgentTeamTableSnapshotTest(unittest.TestCase):
    """Snapshot invariants for the CLAUDE.md ### Agent Team table."""

    def setUp(self):
        self._agent_files = _discover_agent_files()
        self._rows = _parse_agent_team_table_rows()

    def test_row_count_equals_agent_file_count(self):
        """Table data-row count must equal the number of discovered agent files."""
        agent_count = len(self._agent_files)
        row_count = len(self._rows)
        self.assertEqual(
            row_count,
            agent_count,
            f"CLAUDE.md Agent-Team table has {row_count} data rows but "
            f"{agent_count} agent files were discovered in agents/ "
            f"(excl. dynamic/archive). Missing or extra rows detected.\n"
            f"Agent files: {[p.stem for p in self._agent_files]}\n"
            f"Table rows: {self._rows}",
        )

    def test_every_agent_appears_exactly_once(self):
        """Every agent/*.md stem must appear as exactly one row; no extras, no dupes."""
        expected_stems = {p.stem for p in self._agent_files}
        table_agents = [_row_cells(row)[0] for row in self._rows]
        table_agent_set = set(table_agents)

        missing = expected_stems - table_agent_set
        extra = table_agent_set - expected_stems
        duplicates = {a for a in table_agents if table_agents.count(a) > 1}

        errors = []
        if missing:
            errors.append(f"Missing agents (in files but not in table): {sorted(missing)}")
        if extra:
            errors.append(f"Extra agents (in table but no file): {sorted(extra)}")
        if duplicates:
            errors.append(f"Duplicate agent rows: {sorted(duplicates)}")

        self.assertFalse(errors, "\n".join(errors))

    def test_default_model_matches_frontmatter(self):
        """Each row's Default Model cell (col index 3) must equal agent frontmatter model:."""
        stem_to_path = {p.stem: p for p in self._agent_files}
        errors = []

        for row in self._rows:
            cells = _row_cells(row)
            if len(cells) < 4:
                errors.append(f"Row has fewer than 4 cells: {row!r}")
                continue

            agent_name = cells[0]
            raw_model_cell = cells[3]
            # Strip footnote annotations like " [1]"
            table_model = FOOTNOTE_RE.sub("", raw_model_cell).strip()

            if agent_name not in stem_to_path:
                # Already caught by test_every_agent_appears_exactly_once
                continue

            fm = _parse_frontmatter(stem_to_path[agent_name])
            frontmatter_model = fm.get("model")

            if frontmatter_model is None:
                errors.append(
                    f"{agent_name}: no 'model:' key in frontmatter "
                    f"(agents/{agent_name}.md)"
                )
                continue

            if table_model != frontmatter_model:
                errors.append(
                    f"{agent_name}: table Default Model is {table_model!r} "
                    f"but frontmatter model: is {frontmatter_model!r} "
                    f"(agents/{agent_name}.md)"
                )

        self.assertFalse(
            errors,
            "Default Model / frontmatter mismatches:\n" + "\n".join(errors),
        )


if __name__ == "__main__":
    unittest.main()
