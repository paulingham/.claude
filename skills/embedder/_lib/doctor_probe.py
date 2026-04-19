"""Doctor probe: exercise facade and capture EmbedderUnavailable reason."""


def probe_facade():
    """Return (ok, reason). ok=True when encode succeeds."""
    try:
        from embedder.embedder import get_embedder
        get_embedder().encode("probe")
        return True, None
    except Exception as exc:
        return False, str(exc)
