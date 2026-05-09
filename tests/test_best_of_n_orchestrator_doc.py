"""Slice C / AC C9: orchestrator/parallel-dispatch-details.md reflects 5-field record.

The Best-of-N tie-breaker file-count split (Slice C) makes
`skills/best-of-n/lib/score.sh::pick_winner` consume a 5-field record
`name|score|changed_files|changed_lines|cost_rank`. The orchestrator dispatch
detail must be rewritten in lockstep — the deferred-follow-up paragraph
("is a follow-up code change, tracked separately and out of scope for this
slice") must be REPLACED, not just appended-to. This regression test pins
the new contract: presence of the 5-field record literal AND the ordering
description AND absence of the deferred-follow-up phrase.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "orchestrator" / "parallel-dispatch-details.md"

FIVE_FIELD_RECORD = "name|score|changed_files|changed_lines|cost_rank"
ORDERING_DESCRIPTION_TOKENS = ("changed_files_asc", "changed_lines_asc", "cost_asc")
DEFERRED_FOLLOW_UP_PHRASE = (
    "is a follow-up code change, tracked separately and out of scope for this slice"
)


class OrchestratorDocReflectsFiveFieldRecord(unittest.TestCase):
    def test_orchestrator_doc_reflects_five_field_record(self):
        body = DOC.read_text()

        self.assertIn(
            FIVE_FIELD_RECORD,
            body,
            "orchestrator dispatch doc must contain the literal 5-field record "
            f"{FIVE_FIELD_RECORD!r} (case-sensitive)",
        )

        for token in ORDERING_DESCRIPTION_TOKENS:
            self.assertIn(
                token,
                body,
                f"ordering description must contain {token!r} (matches "
                "config.json::tie_breaker_order)",
            )

        self.assertNotIn(
            DEFERRED_FOLLOW_UP_PHRASE,
            body,
            "deferred-follow-up phrase must be replaced, not just appended-to "
            "(Slice C IS the follow-up)",
        )


if __name__ == "__main__":
    unittest.main()
