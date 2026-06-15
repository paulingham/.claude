"""A1-A5: arch_fitness.detect_cycles — import-cycle detector for hooks/_lib.

These are CI-gating pytest tests (RED-first per plan r2 AC F-SE1).
All tests build fixtures in tmp dirs and call the public API directly.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hooks._lib.arch_fitness import detect_cycles


def _write(parent: Path, stem: str, body: str) -> Path:
    path = parent / f"{stem}.py"
    path.write_text(textwrap.dedent(body))
    return path


# A1 — three clean modules with no intra-lib imports → no cycles
def test_clean_modules_return_empty(tmp_path: Path) -> None:
    _write(tmp_path, "alpha", """\
        import json
        import os
    """)
    _write(tmp_path, "bravo", """\
        from pathlib import Path
    """)
    _write(tmp_path, "charlie", """\
        pass
    """)
    assert detect_cycles(str(tmp_path)) == []


# A2 — a→b→a: two-node cycle; both nodes appear in the reported cycle
def test_two_node_cycle_reported(tmp_path: Path) -> None:
    _write(tmp_path, "a", "import b\n")
    _write(tmp_path, "b", "import a\n")
    cycles = detect_cycles(str(tmp_path))
    assert len(cycles) >= 1
    flat = {stem for cycle in cycles for stem in cycle}
    assert "a" in flat and "b" in flat


# A3 — a→b→c→a: three-node cycle; all three nodes appear
def test_three_node_cycle_reported(tmp_path: Path) -> None:
    _write(tmp_path, "a", "import b\n")
    _write(tmp_path, "b", "import c\n")
    _write(tmp_path, "c", "import a\n")
    cycles = detect_cycles(str(tmp_path))
    assert len(cycles) >= 1
    flat = {stem for cycle in cycles for stem in cycle}
    assert "a" in flat and "b" in flat and "c" in flat


# A4 — both `import b` and `from b import x` produce the edge a→b
def test_import_and_from_import_both_create_edge(tmp_path: Path) -> None:
    _write(tmp_path, "a", """\
        import b
        from b import something
    """)
    _write(tmp_path, "b", "import a\n")
    cycles = detect_cycles(str(tmp_path))
    assert len(cycles) >= 1
    flat = {stem for cycle in cycles for stem in cycle}
    assert "a" in flat and "b" in flat


# A5 — stdlib and absent-stem imports do NOT produce edges
def test_stdlib_and_absent_imports_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "a", """\
        import json
        import os
        from pathlib import Path
        from collections import defaultdict
        import nonexistent_module_xyz
        from also_missing import thing
    """)
    assert detect_cycles(str(tmp_path)) == []
