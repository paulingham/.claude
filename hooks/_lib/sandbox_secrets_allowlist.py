"""AC3 — opt-in env-var forwarding into the sandbox microVM.

`forward_env(allowlist) -> dict[str, str]`:

- Empty allowlist → empty dict (default-deny is the safety property).
- Non-empty allowlist → only keys present in BOTH allowlist AND os.environ
  are returned. All other host env vars (`GITHUB_PERSONAL_ACCESS_TOKEN`,
  `ANTHROPIC_API_KEY`, ...) are stripped.
- Allowlist entries naming env vars that are unset → silently dropped.

Additive whitelist (not subtractive strip) per architect-context.md
Finding A3: more auditable, no missed deletions.

The allowlist itself is sourced from the project CLAUDE.md
`## Sandbox Secrets` section by the caller — this module is intentionally
unaware of the file format. Single responsibility: forward only what was
explicitly allowed.
"""
from __future__ import annotations

import os
from typing import Iterable


def forward_env(allowlist: Iterable[str]) -> dict[str, str]:
    """Return a dict mapping each allowlisted name to its current env value.

    Unset names are silently dropped. The contract is C3 (plan.md):
    `forward_env(allowlist: list[str]) -> dict[str, str]; empty allowlist
    -> empty dict`.
    """
    result: dict[str, str] = {}
    for name in allowlist:
        value = os.environ.get(name)
        if value is not None:
            result[name] = value
    return result
