"""Verdict logic: OK | UNAVAILABLE: <reason> | STALE: <N> unembedded."""


def compute(probe_ok, reason, status_payload, unembedded):
    if not probe_ok:
        return f"UNAVAILABLE: {reason}"
    if unembedded > 0:
        return f"STALE: {unembedded} unembedded"
    if not status_payload.get("last_success_at"):
        return "UNAVAILABLE: no success recorded"
    return "OK"
