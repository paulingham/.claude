"""Surfaces resolver-script tests under the TDD-guard expected path.

Tests live in test_thinking_defaults.py — this file re-exports
ResolverEmitsDecisionLine so `tests/test_resolve-thinking.py` exists for the
guard to find.
"""
from test_thinking_defaults import ResolverEmitsDecisionLine  # noqa: F401
