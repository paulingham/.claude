"""Tier normalisation + default project-hash resolution."""
from __future__ import annotations

import subprocess
import sys

from constants import TIERS


def normalise_tier(model: str) -> str | None:
    low = (model or "").lower()
    for tier in TIERS:
        if tier in low:
            return tier
    warn_unknown(model)
    return None


def warn_unknown(model: str) -> None:
    print(f"WARN: unknown model {model}", file=sys.stderr)


def default_project_hash() -> str:
    cmd = 'source ~/.claude/hooks/_lib/project-hash.sh && _project_hash --fallback local'
    try:
        out = subprocess.check_output(["bash", "-c", cmd], stderr=subprocess.DEVNULL)
        return out.decode().strip() or "local"
    except Exception:
        return "local"
