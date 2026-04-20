"""S10: human-readable capture-gate banner for embedder doctor."""
from _lib import embed_presence


def line():
    try:
        return _compute()
    except Exception:
        return "embed: unknown"


def _compute():
    if not embed_presence.models_present():
        return "embed: off (no model — run /project-setup)"
    return "embed: on" if _has_success() else "embed: on (pending first write)"


def _has_success():
    from embedder import status  # lazy
    return bool(status.read().get("last_success_at"))
