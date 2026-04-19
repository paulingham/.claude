"""TDD-guard stem alias for embedder/status.py."""
from test_embedder_status_record import (  # noqa: F401
    RecordFailureStampsErrorAndTimestamp,
    RecordPreservesPriorFields,
    RecordSuccessStampsLastSuccessAt,
)
from test_embedder_status import (  # noqa: F401
    StatusWriteAtomic,
    StatusWriteProducesJSON,
)
