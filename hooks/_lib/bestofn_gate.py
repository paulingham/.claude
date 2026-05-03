"""Best-of-N gate predicate. Authoritative source for dispatch decision."""

_OVERRIDE_TOKEN = "[best-of-n]"


def should_dispatch_bestofn(critical, task_class, budget, request_text=""):
    if critical:
        return True
    return _OVERRIDE_TOKEN in (request_text or "").lower()
