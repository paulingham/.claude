"""Colocated test discovery shim for hooks/_lib/pipeline_state.py.

The full TDD suite lives in tests/test_thinking_defaults.py — this file
re-exports those test classes so the per-module test discovery convention
(test_<module>.py mirrors <module>.py) is satisfied.
"""
from test_thinking_defaults import *  # noqa: F401,F403
