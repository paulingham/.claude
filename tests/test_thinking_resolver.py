"""Colocated test discovery shim for hooks/_lib/thinking_resolver.py.

The full TDD suite lives in tests/test_thinking_defaults.py — this file
re-exports those test classes so the per-module test discovery convention
(test_<module>.py mirrors <module>.py) is satisfied. New tests should be
added to test_thinking_defaults.py, not here.
"""
from test_thinking_defaults import *  # noqa: F401,F403
