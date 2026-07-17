"""Best-of-N gate predicate. Authoritative source for dispatch decision.

Gate: (gear == "PIPELINE" AND budget >= 7 AND critical) OR override_token_present.

The [best-of-n] override token bypasses the gear+budget gate entirely so
operators can force Best-of-N on any gear when the tradeoff is warranted.
"""

_OVERRIDE_TOKEN = "[best-of-n]"


def should_dispatch_bestofn(critical, task_class, budget, request_text="", gear=None):
    if _OVERRIDE_TOKEN in (request_text or "").lower():
        return True
    return gear == "PIPELINE" and budget >= 7 and critical
