"""AC6 — active-work.md is NEVER returned by the injection helper.

For each of the 10 canonical roles, the resolver yields a sub-file list
that does NOT contain 'active-work'. Tests the resolver code (AC15's
hooks/_lib/session_memory_role_resolver.py) — not the docs.
"""
import unittest

from session_memory_role_resolver import resolve_subfiles_for_role

ROLES = (
    "architect",
    "software-engineer",
    "frontend-engineer",
    "database-engineer",
    "infrastructure-engineer",
    "qa-engineer",
    "code-reviewer",
    "security-engineer",
    "product-reviewer",
    "patch-critic",
)


class ResolverExcludesActiveWorkForEveryRole(unittest.TestCase):
    def test_resolver_excludes_active_work_for_every_role(self):
        for role in ROLES:
            subs = resolve_subfiles_for_role(role)
            self.assertNotIn(
                "active-work", subs,
                f"role={role}: active-work must NEVER be injected, got {subs}",
            )

    def test_resolver_returns_list_for_every_role(self):
        for role in ROLES:
            self.assertIsInstance(resolve_subfiles_for_role(role), list)

    def test_resolver_for_session_memory_updater_returns_empty(self):
        # session-memory-updater writes only — no injection.
        self.assertEqual(resolve_subfiles_for_role("session-memory-updater"), [])

    def test_resolver_for_unknown_role_returns_empty(self):
        # Unknown roles inject nothing rather than leaking active-work via fallback.
        self.assertEqual(resolve_subfiles_for_role("not-a-real-role"), [])


if __name__ == "__main__":
    unittest.main()
