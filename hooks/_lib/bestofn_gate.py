"""Best-of-N gate predicate. Authoritative source for dispatch decision.

Gate: (tier == "T6" AND budget >= 7 AND critical) OR override_token_present.

The [best-of-n] override token bypasses the tier+budget gate entirely so
operators can force Best-of-N on any tier when the tradeoff is warranted.
"""

_OVERRIDE_TOKEN = "[best-of-n]"


def should_dispatch_bestofn(critical, task_class, budget, request_text="", tier=None):
    if _OVERRIDE_TOKEN in (request_text or "").lower():
        return True
    return tier == "T6" and budget >= 7 and critical
