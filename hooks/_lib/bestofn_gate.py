"""Best-of-N gate predicate. Authoritative source for dispatch decision."""

_FEATURE_BUDGET_THRESHOLD = 5


def should_dispatch_bestofn(critical, task_class, budget):
    if critical:
        return True
    return task_class == "feature" and budget >= _FEATURE_BUDGET_THRESHOLD
