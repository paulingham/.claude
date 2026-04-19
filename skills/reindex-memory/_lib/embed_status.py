"""Status recording for embed_gate — lazy imports keep default path cost-free."""
import datetime


def record_success():
    from embedder import status  # lazy
    status.record_success(_now())


def record_failure(reason):
    from embedder import status  # lazy
    status.record_failure(reason, _now())


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
