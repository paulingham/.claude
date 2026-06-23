"""Model alias SSOT — maps logical role names to concrete Anthropic model IDs.

ALIASES is loaded once at import from models.json (co-located with this file).
Editing models.json re-points every downstream consumer without touching
individual agent cards.

Public API:
  resolve_model_alias(alias: str) -> str
    KNOWN alias  → the concrete model ID from ALIASES.
    UNKNOWN alias → the input unchanged (passthrough contract).
    This passthrough ensures literal concrete IDs (e.g. "claude-opus-4-7" in
    synthetic test fixtures) round-trip cleanly through the resolver.
"""
import json
from pathlib import Path

_MODELS_JSON = Path(__file__).parent / "models.json"

# WHY: loaded once at import so a single dict mutation in tests re-points output.
ALIASES: dict[str, str] = json.loads(_MODELS_JSON.read_text())


def resolve_model_alias(alias: str) -> str:
    """Return the concrete model ID for alias, or alias itself if unknown."""
    return ALIASES.get(alias, alias)
