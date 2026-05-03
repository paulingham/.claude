"""Slice A — task_state_path helper contract tests.

Locks the new-layout write path the helper produces. Three tests cover
the three constructor permutations called out in the AC stub list.
"""
from pathlib import Path

import pytest

from pipeline_state_paths import task_state_path


def test_task_state_path_returns_new_layout(tmp_path):
    result = task_state_path(tmp_path, "abc", "build")
    assert result == tmp_path / "abc" / "build.md"


def test_task_state_path_workstream_variant(tmp_path):
    result = task_state_path(tmp_path, "abc", "build", workstream="auth")
    assert result == tmp_path / "workstreams" / "auth" / "abc" / "build.md"


@pytest.mark.parametrize("workstream", [None, ""])
def test_task_state_path_workstream_none_means_root(tmp_path, workstream):
    """Contract: workstream=None and workstream='' both yield root layout."""
    result = task_state_path(tmp_path, "abc", "build", workstream=workstream)
    assert result == tmp_path / "abc" / "build.md"
